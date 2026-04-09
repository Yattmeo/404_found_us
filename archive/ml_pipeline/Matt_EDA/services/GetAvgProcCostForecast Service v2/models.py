from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from config import HORIZON_LEN, TARGET_COV


# ---------------------------------------------------------------------------
# Request types
# ---------------------------------------------------------------------------

class M9ForecastRequest(BaseModel):
    """
    Input for POST /GetM9MonthlyCostForecast.

    The caller provides raw transaction records for the onboarding merchant
    and basic forecast parameters.  The service handles all feature
    engineering, pool-mean computation, and kNN peer discovery internally.
    """

    onboarding_merchant_txn_df: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        description=(
            "Raw transaction records for the onboarding merchant.  "
            "Each dict must contain at least: transaction_date, amount, proc_cost.  "
            "Optional fields: cost_type_ID, card_type."
        ),
    )
    mcc: int = Field(..., description="Merchant category code; must be in SUPPORTED_MCCS.")
    merchant_id: Optional[str] = Field(
        default=None,
        description="Opaque merchant identifier for traceability.",
    )
    horizon_months: int = Field(
        default=HORIZON_LEN, ge=1, le=HORIZON_LEN,
        description="Number of months to forecast (1–3).",
    )
    confidence_interval: float = Field(
        default=TARGET_COV, gt=0.0, lt=1.0,
        description="Coverage probability for the conformal prediction interval.",
    )
    card_types: List[str] = Field(
        default_factory=lambda: ["both"],
        description="Card filters for reference pool, e.g. ['visa'] or ['debit'] or ['both'].",
    )

    @field_validator("card_types")
    @classmethod
    def validate_card_types(cls, value: List[str]) -> List[str]:
        if not value:
            return ["both"]
        normalized = [str(v).strip().lower() for v in value if str(v).strip()]
        return normalized or ["both"]


# ---------------------------------------------------------------------------
# Response types
# ---------------------------------------------------------------------------

class ForecastMonth(BaseModel):
    """One forecast month with a conformal prediction interval."""

    month_index: int = Field(
        ...,
        description="1-based index after the context window (1 = first forecast month).",
    )
    proc_cost_pct_mid: float = Field(..., description="Point forecast (model midpoint).")
    proc_cost_pct_ci_lower: float = Field(
        ..., description="Lower bound of the conformal prediction interval.",
    )
    proc_cost_pct_ci_upper: float = Field(
        ..., description="Upper bound of the conformal prediction interval.",
    )


class ConformalMetadata(BaseModel):
    """Explains how the prediction interval was constructed."""

    half_width: float = Field(
        ...,
        description=(
            "Conformal half-width applied symmetrically around the point forecast."
        ),
    )
    conformal_mode: str = Field(
        ...,
        description=(
            "How the half-width was determined: "
            "'local' (peer residuals ≥ MIN_POOL), "
            "'stratified' (GBR-based risk-bucket q90), or "
            "'global_fallback' (entire calibration set)."
        ),
    )
    pool_size: int = Field(
        ..., description="Number of calibration residuals in the peer pool used.",
    )
    risk_score: Optional[float] = Field(
        default=None,
        description="GBR-predicted risk score (max across horizon steps).",
    )
    strat_scheme: Optional[str] = Field(
        default=None,
        description="Name of the stratification scheme applied, if any.",
    )


class ProcessMetadata(BaseModel):
    """Execution details and derived feature values for transparency."""

    context_len_used: int = Field(
        ..., description="Number of context months actually used.",
    )
    context_mean: float = Field(..., description="Mean of the context avg_proc_cost_pct.")
    context_std: float = Field(..., description="Std dev of the context avg_proc_cost_pct.")
    momentum: float = Field(
        ...,
        description="Last context value minus context mean (velocity signal).",
    )
    pool_mean_used: float = Field(
        ..., description="kNN pool mean used as a model feature.",
    )
    mcc: int
    model_variant: str = Field(default="m9_v2", description="Pipeline version identifier.")
    horizon_months: int
    confidence_interval: float
    generated_at_utc: datetime
    artifact_trained_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp from config_snapshot.json indicating when the model was last trained.",
    )
    strat_enabled: bool = Field(
        default=False,
        description="Whether risk-score-based stratification passed the deployment guard for this context length.",
    )


class M9ForecastResponse(BaseModel):
    """Full response from POST /GetM9MonthlyCostForecast."""

    forecast: List[ForecastMonth] = Field(
        ..., description="One entry per horizon month (length == horizon_months)."
    )
    conformal_metadata: ConformalMetadata
    process_metadata: ProcessMetadata
