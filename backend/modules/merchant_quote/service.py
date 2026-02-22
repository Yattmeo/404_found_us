from __future__ import annotations

from datetime import datetime

from .schemas import MerchantQuoteRequest, MerchantQuoteResponse, QuoteChargeItem, QuoteSummary


class MerchantQuoteService:
    @staticmethod
    def _format_rate_range(lower: float, upper: float) -> str:
        return f"{lower:.1f}-{upper:.1f}%"

    @staticmethod
    def generate_quote(payload: MerchantQuoteRequest) -> MerchantQuoteResponse:
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
