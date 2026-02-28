from __future__ import annotations

import logging
import os
import re
from datetime import datetime

import httpx

from .schemas import MerchantQuoteRequest, MerchantQuoteResponse, QuoteChargeItem, QuoteSummary

logger = logging.getLogger(__name__)

_ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://ml-service:8001")


class MerchantQuoteService:

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

        today_str = datetime.utcnow().strftime("%Y-%m-%d")

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
            logger.warning("KNN rate-quote call failed: %s", exc)
            return None

        forecast: list[float] = result.get("forecast_proc_cost", [])
        if not forecast:
            logger.warning("KNN returned empty forecast_proc_cost")
            return None

        # Compute rate: proc_cost / avg_ticket → percentage, then add 30 bps
        low_pct  = (min(forecast) / avg_ticket) * 100 + 0.30
        high_pct = (max(forecast) / avg_ticket) * 100 + 0.30

        return round(low_pct, 1), round(high_pct, 1)

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
            QuoteChargeItem(name="Gateway Charge", value=16.0),
        ]
        if monthly_txns >= 1000:
            monthly_charges.append(QuoteChargeItem(name="Gateway Charge Waiver", value=-16.0))

        quote_summary = QuoteSummary(
            payment_brands_accepted=payload.payment_brands_accepted,
            business_name=payload.business_name,
            industry=payload.industry,
            average_ticket_size=round(avg_ticket, 2),
            monthly_transactions=monthly_txns,
            quote_date=datetime.utcnow().strftime("%a, %d %b %Y"),
        )

        return MerchantQuoteResponse(
            in_person_rate_range=MerchantQuoteService._format_rate_range(in_person_lower, in_person_upper),
            online_rate_range=MerchantQuoteService._format_rate_range(online_lower, online_upper),
            other_potential_transaction_charges=potential_charges,
            other_monthly_charges=monthly_charges,
            quote_summary=quote_summary,
        )

        monthly_volume = payload.average_transaction_value * payload.monthly_transactions

        base_rate = 2.5
        if monthly_volume > 100000:
            base_rate -= 0.3
        elif monthly_volume > 50000:
            base_rate -= 0.2
        elif monthly_volume > 10000:
            base_rate -= 0.1

        base_rate = max(base_rate, 1.5)

        in_person_lower = max(1.5, base_rate - 0.1)
        in_person_upper = base_rate + 0.1
        online_lower = in_person_lower + 0.2
        online_upper = in_person_upper + 0.2

        potential_charges = [
            QuoteChargeItem(name="Chargeback Fee", value=25.0),
            QuoteChargeItem(name="Refund Processing Fee", value=0.5),
        ]

        monthly_charges = [
            QuoteChargeItem(name="Point-of-sale terminal (per terminal)", value=25.0),
            QuoteChargeItem(name="Gateway Charge", value=16.0),
        ]

        if payload.monthly_transactions >= 1000:
            monthly_charges.append(QuoteChargeItem(name="Gateway Charge Waiver", value=-16.0))

        quote_summary = QuoteSummary(
            payment_brands_accepted=payload.payment_brands_accepted,
            business_name=payload.business_name,
            industry=payload.industry,
            average_ticket_size=round(payload.average_transaction_value, 2),
            monthly_transactions=payload.monthly_transactions,
            quote_date=datetime.utcnow().strftime("%a, %d %b %Y"),
        )

        return MerchantQuoteResponse(
            in_person_rate_range=MerchantQuoteService._format_rate_range(in_person_lower, in_person_upper),
            online_rate_range=MerchantQuoteService._format_rate_range(online_lower, online_upper),
            other_potential_transaction_charges=potential_charges,
            other_monthly_charges=monthly_charges,
            quote_summary=quote_summary,
        )
