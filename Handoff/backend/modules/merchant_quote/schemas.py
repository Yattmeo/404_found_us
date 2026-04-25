from __future__ import annotations

from pydantic import BaseModel, Field


class QuoteChargeItem(BaseModel):
    name: str
    value: float
    waived: bool = False


class QuoteSummary(BaseModel):
    payment_brands_accepted: list[str]
    business_name: str
    industry: str
    average_ticket_size: float
    monthly_transactions: int
    quote_date: str


class MLForecastBand(BaseModel):
    mid: float
    lower: float
    upper: float


class MerchantQuoteInsights(BaseModel):
    knn_neighbor_count: int
    knn_end_month: str
    cost_forecast_week_1: MLForecastBand | None = None
    volume_forecast_week_1: MLForecastBand | None = None


class MerchantQuoteRequest(BaseModel):
    business_name: str = Field(..., min_length=1)
    industry: str = Field(..., min_length=1)
    average_transaction_value: float = Field(..., ge=0)
    monthly_transactions: int = Field(..., ge=0)
    payment_brands_accepted: list[str] = Field(..., min_length=1)


class MerchantQuoteResponse(BaseModel):
    in_person_rate_range: str
    online_rate_range: str
    other_potential_transaction_charges: list[QuoteChargeItem]
    other_monthly_charges: list[QuoteChargeItem]
    quote_summary: QuoteSummary
    ml_insights: MerchantQuoteInsights | None = None
