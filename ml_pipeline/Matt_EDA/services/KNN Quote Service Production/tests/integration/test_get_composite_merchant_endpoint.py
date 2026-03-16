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
            for year, months in [(2018, range(1, 13)), (2019, range(1, 10))]:
                for month in months:
                    for day, cost_type in [(5, 1), (15, 2)]:
                        amount = float((merchant_id % 100) + month * 10 + day / 10.0)
                        proc_cost = amount * 0.02 + (merchant_id % 10) * 0.001
                        rows.append(
                            {
                                "transaction_id": tx_id,
                                "date": f"{year}-{month:02d}-{day:02d} 00:00:00",
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


def test_get_composite_merchant_success(client_and_tracker):
    client, tracker = client_and_tracker
    payload = {
        "onboarding_merchant_txn_df": [
            {
                "transaction_date": "2019-01-03",
                "amount": 20.0,
                "cost_type_ID": 1,
                "card_type": "visa",
            },
            {
                "transaction_date": "2019-01-20",
                "amount": 50.0,
                "cost_type_ID": 2,
                "card_type": "visa",
            },
            {
                "transaction_date": "2019-02-03",
                "amount": 25.0,
                "cost_type_ID": 1,
                "card_type": "visa",
            },
            {
                "transaction_date": "2019-02-18",
                "amount": 60.0,
                "cost_type_ID": 2,
                "card_type": "visa",
            },
        ],
        "mcc": 5411,
        "card_types": ["visa"],
    }

    response = client.post("/getCompositeMerchant", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["matching_start_month"] == "2019-01"
    assert data["matching_end_month"] == "2019-02"
    assert data["k"] == 5
    assert len(data["matched_neighbor_merchant_ids"]) == 5
    assert all(1100 < mid < 1200 for mid in data["matched_neighbor_merchant_ids"])

    weekly = data["weekly_features"]
    assert len(weekly) == 104
    sample = weekly[0]
    assert "calendar_year" in sample
    assert "week_of_year" in sample
    assert "weekly_txn_count_mean" in sample
    assert "weekly_txn_count_stdev" in sample
    assert "weekly_total_proc_value_mean" in sample
    assert "weekly_total_proc_value_stdev" in sample
    assert "weekly_avg_txn_value_mean" in sample
    assert "weekly_avg_txn_value_stdev" in sample
    assert "weekly_avg_txn_cost_pct_mean" in sample
    assert "weekly_avg_txn_cost_pct_stdev" in sample
    assert "neighbor_coverage" in sample
    assert "pct_ct_means" in sample
    assert sorted(sample["pct_ct_means"].keys()) == ["pct_ct_1", "pct_ct_2"]
    years = sorted({row["calendar_year"] for row in weekly})
    assert years == [2018, 2019]
    assert weekly[0]["week_of_year"] == 1
    assert weekly[-1]["week_of_year"] == 52

    assert tracker.calls == 1


def test_get_composite_merchant_unknown_mcc_returns_400(client_and_tracker):
    client, _ = client_and_tracker
    payload = {
        "onboarding_merchant_txn_df": [
            {
                "transaction_date": "2019-01-03",
                "amount": 20.0,
                "cost_type_ID": 1,
            }
        ],
        "mcc": 9999,
        "card_types": ["both"],
    }

    response = client.post("/getCompositeMerchant", json=payload)
    assert response.status_code == 400
    assert "No reference transactions" in response.json()["detail"]


def test_get_composite_merchant_requires_onboarding_df(client_and_tracker):
    client, _ = client_and_tracker
    payload = {
        "mcc": 5411,
        "card_types": ["visa"],
    }

    response = client.post("/getCompositeMerchant", json=payload)
    assert response.status_code == 422
