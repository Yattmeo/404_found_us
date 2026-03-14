from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

import app as app_module
from repository import SQLiteMerchantRepository
from service import ProductionQuoteService


class TrackingProcessingCostProvider:
    def __init__(self) -> None:
        self.calls = 0

    def enrich(self, txn_df: pd.DataFrame) -> pd.DataFrame:
        self.calls += 1
        enriched = txn_df.copy()
        amount = pd.to_numeric(enriched.get("amount"), errors="coerce").fillna(0.0)
        if "proc_cost" not in enriched.columns:
            enriched["proc_cost"] = amount * 0.02 + 0.05
        else:
            enriched["proc_cost"] = pd.to_numeric(
                enriched["proc_cost"], errors="coerce"
            ).fillna(amount * 0.02 + 0.05)
        return enriched


def _seed_test_db(db_path: Path) -> None:
    rows = []
    tx_id = 1

    visa_merchants = [1101, 1102, 1103, 1104, 1105, 1106]
    mc_merchants = [2101, 2102, 2103, 2104, 2105, 2106]

    def add_rows(merchant_ids: list[int], brand: str, card_type: str) -> None:
        nonlocal tx_id
        for merchant_id in merchant_ids:
            for month in range(1, 10):
                for day, cost_type in [(5, 1), (15, 2)]:
                    amount = float((merchant_id % 100) + month * 10 + day / 10.0)
                    proc_cost = amount * 0.02 + (merchant_id % 10) * 0.001
                    rows.append(
                        {
                            "transaction_id": tx_id,
                            "date": f"2019-{month:02d}-{day:02d} 00:00:00",
                            "amount": amount,
                            "merchant_id": merchant_id,
                            "mcc": 5411,
                            "card_brand": brand,
                            "card_type": card_type,
                            "cost_type_ID": cost_type,
                            "proc_cost": proc_cost,
                        }
                    )
                    tx_id += 1

    add_rows(visa_merchants, "visa", "credit")
    add_rows(mc_merchants, "mastercard", "debit")

    # Non-target MCC rows for filter validation.
    rows.append(
        {
            "transaction_id": tx_id,
            "date": "2019-06-01 00:00:00",
            "amount": 99.0,
            "merchant_id": 9999,
            "mcc": 5812,
            "card_brand": "visa",
            "card_type": "credit",
            "cost_type_ID": 1,
            "proc_cost": 2.5,
        }
    )

    transactions = pd.DataFrame(rows)
    cost_type_ref = pd.DataFrame({"cost_type_ID": [1, 2]})

    with sqlite3.connect(db_path) as conn:
        transactions.to_sql("transactions", conn, if_exists="replace", index=False)
        cost_type_ref.to_sql("cost_type_ref", conn, if_exists="replace", index=False)


@pytest.fixture
def client_and_tracker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test_rate_quote.sqlite"
    _seed_test_db(db_path)

    tracker = TrackingProcessingCostProvider()
    service = ProductionQuoteService(
        repository=SQLiteMerchantRepository(db_path=db_path),
        processing_cost_provider=tracker,
        k=5,
        context_len_months=1,
        horizon_len_months=3,
    )

    monkeypatch.setattr(app_module, "service", service)
    client = TestClient(app_module.app)
    return client, tracker


def test_health(client_and_tracker):
    client, _ = client_and_tracker
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_quote_with_onboarding_df_returns_expected_shape(client_and_tracker):
    client, tracker = client_and_tracker
    payload = {
        "onboarding_merchant_txn_df": [
            {
                "transaction_date": "2019-06-01",
                "amount": 52.1,
                "cost_type_ID": 2,
                "card_type": "visa",
            },
            {
                "transaction_date": "2019-06-02",
                "amount": 22.0,
                "cost_type_ID": 1,
                "card_type": "visa",
            },
            {
                "transaction_date": "2019-06-12",
                "amount": 17.0,
                "cost_type_ID": 2,
                "card_type": "visa",
            },
        ],
        "avg_monthly_txn_count": 200,
        "avg_monthly_txn_value": 30.0,
        "mcc": 5411,
        "card_types": ["both"],
        "as_of_date": "2019-06-30T00:00:00",
    }

    response = client.post("/getQuote", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["context_len_wk"] == 4
    assert data["horizon_len_wk"] == 12
    assert data["k"] == 5
    assert data["end_month"] == "2019-06"

    neighbors = data["neighbor_forecasts"]
    assert len(neighbors) == 5
    for row in neighbors:
        assert isinstance(row["merchant_id"], int)
        assert len(row["forecast_proc_cost_pct_3m"]) == 3
        assert all(isinstance(v, float) for v in row["forecast_proc_cost_pct_3m"])

    assert tracker.calls == 1


def test_get_quote_metrics_only_works(client_and_tracker):
    client, _ = client_and_tracker
    payload = {
        "avg_monthly_txn_count": 150,
        "avg_monthly_txn_value": 45.0,
        "mcc": 5411,
        "card_types": ["visa"],
        "as_of_date": "2019-06-30T00:00:00",
    }

    response = client.post("/getQuote", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert len(data["neighbor_forecasts"]) == 5
    assert all(
        1100 < row["merchant_id"] < 1200 for row in data["neighbor_forecasts"]
    )


def test_get_quote_missing_metrics_without_df_returns_400(client_and_tracker):
    client, _ = client_and_tracker
    payload = {
        "mcc": 5411,
        "card_types": ["visa"],
        "as_of_date": "2019-06-30T00:00:00",
    }

    response = client.post("/getQuote", json=payload)
    assert response.status_code == 400
    assert "avg_monthly_txn_count" in response.json()["detail"]


def test_get_quote_unknown_mcc_returns_400(client_and_tracker):
    client, _ = client_and_tracker
    payload = {
        "avg_monthly_txn_count": 150,
        "avg_monthly_txn_value": 45.0,
        "mcc": 9999,
        "card_types": ["both"],
        "as_of_date": "2019-06-30T00:00:00",
    }

    response = client.post("/getQuote", json=payload)
    assert response.status_code == 400
    assert "No reference transactions" in response.json()["detail"]


def test_get_quote_card_type_filtering_mastercard_pool(client_and_tracker):
    client, _ = client_and_tracker
    payload = {
        "avg_monthly_txn_count": 150,
        "avg_monthly_txn_value": 45.0,
        "mcc": 5411,
        "card_types": ["mastercard"],
        "as_of_date": "2019-06-30T00:00:00",
    }

    response = client.post("/getQuote", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert len(data["neighbor_forecasts"]) == 5
    assert all(
        2100 < row["merchant_id"] < 2200 for row in data["neighbor_forecasts"]
    )


def test_get_quote_card_type_filtering_credit_type_pool(client_and_tracker):
    client, _ = client_and_tracker
    payload = {
        "avg_monthly_txn_count": 150,
        "avg_monthly_txn_value": 45.0,
        "mcc": 5411,
        "card_types": ["credit"],
        "as_of_date": "2019-06-30T00:00:00",
    }

    response = client.post("/getQuote", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert len(data["neighbor_forecasts"]) == 5
    # In seeded data, only visa cohort is credit.
    assert all(
        1100 < row["merchant_id"] < 1200 for row in data["neighbor_forecasts"]
    )
