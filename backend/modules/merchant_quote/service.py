from __future__ import annotations

import logging
import os
import re
from math import erf, sqrt
from datetime import datetime, timedelta, timezone

import httpx

from .schemas import (
    MLForecastBand,
    MerchantQuoteInsights,
    MerchantQuoteRequest,
    MerchantQuoteResponse,
    QuoteChargeItem,
    QuoteSummary,
)

logger = logging.getLogger(__name__)

_ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://ml-service:8001")


class MerchantQuoteService:

    @staticmethod
    def _safe_float(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _format_rate_range(lower: float, upper: float) -> str:
        return f"{lower:.1f}-{upper:.1f}%"

    @staticmethod
    def _extract_mcc(industry: str) -> int | None:
        """Extract the 4-digit MCC from a string like '5411 - General Grocery Stores'."""
        match = re.match(r"^\s*(\d{4})", industry)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _card_type_from_brands(brands: list[str]) -> str:
        """Map payment brand list to KNN card_type parameter."""
        normalised = {b.lower() for b in brands}
        if "visa" in normalised and "mastercard" in normalised:
            return "both"
        if "visa" in normalised:
            return "visa"
        if "mastercard" in normalised:
            return "mastercard"
        return "both"

    @staticmethod
    def _card_types_from_brands(brands: list[str]) -> list[str]:
        # The production KNN service supports both card-brand and card-type filters.
        # Keep a permissive fallback to avoid empty pools with sparse historical data.
        card_type = MerchantQuoteService._card_type_from_brands(brands)
        return [card_type] if card_type != "both" else ["both"]

    @staticmethod
    def _build_onboarding_rows(
        avg_ticket: float,
        monthly_txn_count: int,
        brands: list[str],
        effective_rate_pct: float,
    ) -> list[dict]:
        rows: list[dict] = []
        today = datetime.now(timezone.utc).date()
        safe_rate = max(effective_rate_pct / 100.0, 0.005)
        card_type = MerchantQuoteService._card_type_from_brands(brands)
        for week_idx in range(8):
            day = today - timedelta(days=(7 * (7 - week_idx)))
            rows.append(
                {
                    "transaction_date": day.isoformat(),
                    "amount": round(avg_ticket, 2),
                    "proc_cost": round(avg_ticket * safe_rate, 4),
                    "cost_type_ID": 1,
                    "card_type": card_type,
                    "monthly_txn_count": monthly_txn_count,
                }
            )
        return rows

    @staticmethod
    def build_onboarding_rows_from_transactions(
        transactions: list[dict],
        card_type: str,
        effective_rate_pct: float,
    ) -> list[dict]:
        rows: list[dict] = []
        safe_rate = max(effective_rate_pct / 100.0, 0.0)

        for tx in transactions:
            amount = MerchantQuoteService._safe_float(tx.get("amount"), 0.0)
            if amount <= 0:
                continue

            transaction_date = (
                tx.get("transaction_date")
                or tx.get("date")
                or tx.get("txn_date")
                or datetime.now(timezone.utc).date().isoformat()
            )

            rows.append(
                {
                    "transaction_date": str(transaction_date),
                    "amount": round(amount, 2),
                    "proc_cost": round(amount * safe_rate, 6),
                    "cost_type_ID": int(tx.get("cost_type_ID") or tx.get("cost_type_id") or 1),
                    "card_type": card_type,
                }
            )

        return rows

    @staticmethod
    def run_ml_forecast_pipeline(
        mcc: int,
        card_types: list[str],
        onboarding_rows: list[dict],
    ) -> dict | None:
        if not onboarding_rows:
            return None

        try:
            with httpx.Client(timeout=20.0) as client:
                composite_resp = client.post(
                    f"{_ML_SERVICE_URL}/ml/getCompositeMerchant",
                    json={
                        "onboarding_merchant_txn_df": onboarding_rows,
                        "mcc": mcc,
                        "card_types": card_types,
                    },
                )
                composite_resp.raise_for_status()
                composite_payload = composite_resp.json()

                weekly_features = composite_payload.get("weekly_features", [])
                if not weekly_features:
                    return None

                cost_resp = client.post(
                    f"{_ML_SERVICE_URL}/ml/GetCostForecast",
                    json={
                        "composite_weekly_features": weekly_features,
                        "onboarding_merchant_txn_df": onboarding_rows,
                        "mcc": mcc,
                    },
                )
                cost_resp.raise_for_status()
                cost_payload = cost_resp.json()

                volume_resp = client.post(
                    f"{_ML_SERVICE_URL}/ml/GetVolumeForecast",
                    json={
                        "composite_weekly_features": weekly_features,
                        "onboarding_merchant_txn_df": onboarding_rows,
                        "mcc": mcc,
                    },
                )
                volume_resp.raise_for_status()
                volume_payload = volume_resp.json()
        except Exception as exc:
            logger.warning("ML insights pipeline failed: %s", exc)
            return None

        return {
            "composite": composite_payload,
            "cost": cost_payload,
            "volume": volume_payload,
        }

    @staticmethod
    def normal_cdf(x: float, mean: float, std_dev: float) -> float:
        safe_std = max(std_dev, 1e-9)
        z = (x - mean) / (safe_std * sqrt(2.0))
        return 0.5 * (1.0 + erf(z))

    @staticmethod
    def _extract_rate_bounds_from_forecast(quote_payload: dict) -> tuple[float, float] | None:
        forecast = quote_payload.get("forecast_proc_cost", [])
        if not forecast:
            return None

        all_values_pct: list[float] = []
        for value in forecast:
            try:
                all_values_pct.append(float(value) * 100.0)
            except (TypeError, ValueError):
                continue
        if not all_values_pct:
            return None

        low_pct = min(all_values_pct) + 0.30
        high_pct = max(all_values_pct) + 0.30
        return round(low_pct, 1), round(high_pct, 1)

    @staticmethod
    def _rates_from_knn(
        avg_ticket: float,
        monthly_txn_count: int,
        mcc: int,
        card_type: str,
    ) -> tuple[float, float] | None:
        """
        Call the ML service's KNN Rate Quote endpoint and return
        (in_person_lower, in_person_upper) as percentage values (1 d.p.),
        already including the 30 bps margin.

        Returns None if the call fails or avg_ticket is zero.
        """
        if avg_ticket <= 0:
            return None

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(
                    f"{_ML_SERVICE_URL}/ml/knn-rate-quote",
                    data={
                        "mcc": str(mcc),
                        "card_type": card_type,
                        "monthly_txn_count": str(monthly_txn_count),
                        "avg_amount": str(avg_ticket),
                        "as_of_date": today_str,
                    },
                )
            response.raise_for_status()
            result = response.json()
        except Exception as exc:
            logger.warning("KNN knn-rate-quote call failed: %s", exc)
            return None
        return MerchantQuoteService._extract_rate_bounds_from_forecast(result)

    @staticmethod
    def _fetch_ml_insights(
        mcc: int,
        card_types: list[str],
        onboarding_rows: list[dict],
    ) -> MerchantQuoteInsights | None:
        pipeline = MerchantQuoteService.run_ml_forecast_pipeline(
            mcc=mcc,
            card_types=card_types,
            onboarding_rows=onboarding_rows,
        )
        if pipeline is None:
            return None

        composite_payload = pipeline["composite"]
        cost_payload = pipeline["cost"]
        volume_payload = pipeline["volume"]

        cost_week1 = None
        if cost_payload.get("forecast"):
            first = cost_payload["forecast"][0]
            cost_week1 = MLForecastBand(
                mid=float(first.get("proc_cost_pct_mid", 0.0)),
                lower=float(first.get("proc_cost_pct_ci_lower", 0.0)),
                upper=float(first.get("proc_cost_pct_ci_upper", 0.0)),
            )

        volume_week1 = None
        if volume_payload.get("forecast"):
            first = volume_payload["forecast"][0]
            volume_week1 = MLForecastBand(
                mid=float(first.get("total_proc_value_mid", 0.0)),
                lower=float(first.get("total_proc_value_ci_lower", 0.0)),
                upper=float(first.get("total_proc_value_ci_upper", 0.0)),
            )

        return MerchantQuoteInsights(
            knn_neighbor_count=int(composite_payload.get("k", 0)),
            knn_end_month=str(composite_payload.get("matching_end_month", "")),
            cost_forecast_week_1=cost_week1,
            volume_forecast_week_1=volume_week1,
        )

    @staticmethod
    def _placeholder_rates(monthly_volume: float) -> tuple[float, float]:
        """Fallback placeholder rate range when KNN is unavailable."""
        base = 2.5
        if monthly_volume > 100_000:
            base -= 0.3
        elif monthly_volume > 50_000:
            base -= 0.2
        elif monthly_volume > 10_000:
            base -= 0.1
        base = max(base, 1.5)
        return round(max(1.5, base - 0.1), 1), round(base + 0.1, 1)

    @staticmethod
    def generate_quote(payload: MerchantQuoteRequest) -> MerchantQuoteResponse:
        avg_ticket      = payload.average_transaction_value
        monthly_txns    = payload.monthly_transactions
        monthly_volume  = avg_ticket * monthly_txns

        mcc      = MerchantQuoteService._extract_mcc(payload.industry)
        card_type = MerchantQuoteService._card_type_from_brands(payload.payment_brands_accepted)
        card_types = MerchantQuoteService._card_types_from_brands(payload.payment_brands_accepted)

        # Try KNN-backed rates; fall back to placeholder if unavailable
        knn_rates = None
        if mcc is not None:
            knn_rates = MerchantQuoteService._rates_from_knn(
                avg_ticket, monthly_txns, mcc, card_type
            )

        if knn_rates is not None:
            in_person_lower, in_person_upper = knn_rates
        else:
            in_person_lower, in_person_upper = MerchantQuoteService._placeholder_rates(monthly_volume)

        # Online / phone rates are always in-person + 0.1 pp
        online_lower = round(in_person_lower + 0.1, 1)
        online_upper = round(in_person_upper + 0.1, 1)

        potential_charges = [
            QuoteChargeItem(name="Chargeback Fee", value=25.0),
            QuoteChargeItem(name="Refund Processing Fee", value=0.5),
        ]

        monthly_charges = [
            QuoteChargeItem(name="Point-of-sale terminal (per terminal)", value=25.0),
            QuoteChargeItem(name="Gateway Charge", value=16.0, waived=monthly_txns >= 1000),
        ]

        quote_summary = QuoteSummary(
            payment_brands_accepted=payload.payment_brands_accepted,
            business_name=payload.business_name,
            industry=payload.industry,
            average_ticket_size=round(avg_ticket, 2),
            monthly_transactions=monthly_txns,
            quote_date=datetime.now(timezone.utc).strftime("%a, %d %b %Y"),
        )

        ml_insights = None
        if mcc is not None:
            onboarding_rows = MerchantQuoteService._build_onboarding_rows(
                avg_ticket=avg_ticket,
                monthly_txn_count=monthly_txns,
                brands=payload.payment_brands_accepted,
                effective_rate_pct=max(in_person_lower, 0.1),
            )
            ml_insights = MerchantQuoteService._fetch_ml_insights(
                mcc=mcc,
                card_types=card_types,
                onboarding_rows=onboarding_rows,
            )

        return MerchantQuoteResponse(
            in_person_rate_range=MerchantQuoteService._format_rate_range(in_person_lower, in_person_upper),
            online_rate_range=MerchantQuoteService._format_rate_range(online_lower, online_upper),
            other_potential_transaction_charges=potential_charges,
            other_monthly_charges=monthly_charges,
            quote_summary=quote_summary,
            ml_insights=ml_insights,
        )
