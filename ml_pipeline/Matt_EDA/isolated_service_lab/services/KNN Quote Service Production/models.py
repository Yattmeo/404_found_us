from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class QuoteRequest(BaseModel):
    onboarding_merchant_txn_df: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional transaction records for the onboarding merchant.",
    )
    avg_monthly_txn_count: Optional[int] = Field(default=None, ge=0)
    avg_monthly_txn_value: Optional[float] = Field(default=None, ge=0)
    mcc: int
    card_types: List[str] = Field(
        default_factory=lambda: ["both"],
        description="Card filters, e.g. ['visa'] or ['debit'] or ['both'].",
    )
    as_of_date: Optional[datetime] = None

    @field_validator("card_types")
    @classmethod
    def validate_card_types(cls, value: List[str]) -> List[str]:
        if not value:
            return ["both"]
        normalized = [str(v).strip().lower() for v in value if str(v).strip()]
        return normalized or ["both"]


class NeighborForecast(BaseModel):
    merchant_id: int
    forecast_proc_cost_pct_3m: List[float]


class QuoteResponse(BaseModel):
    neighbor_forecasts: List[NeighborForecast]
    context_len_wk: int
    horizon_len_wk: int
    k: int
    end_month: str


@dataclass
class QuoteComputationResult:
    neighbor_forecasts: List[NeighborForecast]
    context_len_wk: int
    horizon_len_wk: int
    k: int
    end_month: str


class CompositeMerchantRequest(BaseModel):
    onboarding_merchant_txn_df: List[Dict[str, Any]] = Field(
        ...,
        description="Required transaction records for the onboarding merchant.",
        min_length=1,
    )
    mcc: int
    card_types: List[str] = Field(
        default_factory=lambda: ["both"],
        description="Card filters, e.g. ['visa'] or ['debit'] or ['both'].",
    )

    @field_validator("card_types")
    @classmethod
    def validate_card_types(cls, value: List[str]) -> List[str]:
        if not value:
            return ["both"]
        normalized = [str(v).strip().lower() for v in value if str(v).strip()]
        return normalized or ["both"]


class CompositeWeeklyFeature(BaseModel):
    calendar_year: int
    week_of_year: int
    weekly_txn_count_mean: float
    weekly_txn_count_stdev: float
    weekly_total_proc_value_mean: float
    weekly_total_proc_value_stdev: float
    weekly_avg_txn_value_mean: float
    weekly_avg_txn_value_stdev: float
    weekly_avg_txn_cost_pct_mean: float
    weekly_avg_txn_cost_pct_stdev: float
    neighbor_coverage: int
    pct_ct_means: Dict[str, float]


class CompositeMerchantResponse(BaseModel):
    composite_merchant_id: str
    matched_neighbor_merchant_ids: List[int]
    k: int
    matching_start_month: str
    matching_end_month: str
    weekly_features: List[CompositeWeeklyFeature]


@dataclass
class CompositeMerchantComputationResult:
    composite_merchant_id: str
    matched_neighbor_merchant_ids: List[int]
    k: int
    matching_start_month: str
    matching_end_month: str
    weekly_features: List[CompositeWeeklyFeature]
