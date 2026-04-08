"""
models.py — Pydantic request/response models for GetTPVForecast (v2).

Adapted for embedding inside ml_service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from .config import HORIZON_LEN, TARGET_COV


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class TPVForecastRequest(BaseModel):
    onboarding_merchant_txn_df: List[Dict[str, Any]] = Field(
        ..., min_length=1,
        description="Raw transaction records (transaction_date, amount required; cost_type_ID, card_type optional).",
    )
    mcc: int = Field(..., description="Merchant category code.")
    merchant_id: Optional[str] = Field(default=None)
    horizon_months: int = Field(default=HORIZON_LEN, ge=1, le=HORIZON_LEN)
    confidence_interval: float = Field(default=TARGET_COV, gt=0.0, lt=1.0)
    card_types: List[str] = Field(
        default_factory=lambda: ["both"],
        description="Card filters for reference pool.",
    )

    @field_validator("card_types")
    @classmethod
    def validate_card_types(cls, value: List[str]) -> List[str]:
        if not value:
            return ["both"]
        normalized = [str(v).strip().lower() for v in value if str(v).strip()]
        return normalized or ["both"]


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class ForecastMonth(BaseModel):
    month_index: int
    tpv_mid: float
    tpv_ci_lower: float
    tpv_ci_upper: float


class ConformalMetadata(BaseModel):
    half_width_dollars: float
    conformal_mode: str
    pool_size: int
    risk_score: Optional[float] = None
    strat_scheme: Optional[str] = None


class ProcessMetadata(BaseModel):
    context_len_used: int
    context_mean_log_tpv: float
    context_mean_dollar: float
    momentum: float
    pool_mean_used: float
    mcc: int
    model_variant: str = "tpv_v1"
    horizon_months: int
    confidence_interval: float
    generated_at_utc: datetime
    artifact_trained_at: Optional[str] = None
    strat_enabled: bool = False


class TPVForecastResponse(BaseModel):
    forecast: List[ForecastMonth]
    conformal_metadata: ConformalMetadata
    process_metadata: ProcessMetadata
