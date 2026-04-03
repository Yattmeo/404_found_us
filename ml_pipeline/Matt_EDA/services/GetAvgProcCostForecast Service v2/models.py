from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from config import HORIZON_LEN, MAX_CONTEXT_LEN, SUPPORTED_CONTEXT_LENS, TARGET_COV


# ---------------------------------------------------------------------------
# Request types
# ---------------------------------------------------------------------------

class ContextMonth(BaseModel):
    """One observed month of processing cost history for the onboarding merchant."""

    year: int
    month: int = Field(..., ge=1, le=12)
    avg_proc_cost_pct: float = Field(
        ..., description="Average processing cost as a percentage of transaction value.",
    )
    # ── v2 transaction-level fields (required for v2 model features) ──────────
    std_proc_cost_pct: float = Field(
        default=0.0,
        description="Std dev of per-transaction proc_cost_pct within this month.",
    )
    median_proc_cost_pct: float = Field(
        default=0.0,
        description="Median per-transaction proc_cost_pct within this month.",
    )
    transaction_count: int = Field(
        default=1,
        ge=1,
        description="Number of transactions in this month.",
    )
    avg_transaction_value: float = Field(
        default=0.0,
        description="Average transaction amount (dollars) this month.",
    )
    std_txn_amount: float = Field(
        default=0.0,
        description="Std dev of transaction amounts this month.",
    )
    cost_type_pcts: Optional[Dict[str, float]] = Field(
        default=None,
        description=(
            "Optional dict mapping cost_type_N_pct column names to their values "
            "for this month.  Used to compute cost_type_hhi risk feature."
        ),
    )


class M9ForecastRequest(BaseModel):
    """
    Input for POST /GetM9MonthlyCostForecast.

    context_months              — observed monthly costs for the onboarding merchant.
                                  Length must be between 1 and MAX_CONTEXT_LEN.
    pool_mean_at_context_end    — flat peer pool mean at the end of the context window.
    knn_pool_mean_at_context_end — kNN-based pool mean (cosine similarity neighbours).
    peer_merchant_ids           — IDs of the merchant's kNN neighbors.  Used to look up
                                  local conformal calibration residuals.
    """

    context_months: List[ContextMonth] = Field(
        ...,
        min_length=1,
        max_length=MAX_CONTEXT_LEN,
        description=(
            f"Observed monthly processing costs (1–{MAX_CONTEXT_LEN} months). "
            f"Supported context lengths for stratification: {SUPPORTED_CONTEXT_LENS}."
        ),
    )
    pool_mean_at_context_end: float = Field(
        ...,
        description=(
            "Flat peer pool mean for this merchant at the context window end-date."
        ),
    )
    knn_pool_mean_at_context_end: float = Field(
        ...,
        description=(
            "kNN peer pool mean (cosine-similarity neighbours) at context end-date."
        ),
    )
    peer_merchant_ids: Optional[List[int]] = Field(
        default=None,
        description=(
            "kNN neighbor merchant IDs used to collect local conformal residuals. "
            "Pass [] or omit to use vol-stratified or global fallback."
        ),
    )
    merchant_id: Optional[str] = Field(
        default=None,
        description="Opaque merchant identifier carried through for traceability.",
    )
    mcc: int = Field(..., description="Merchant category code; must be in SUPPORTED_MCCS.")
    horizon_months: int = Field(
        default=HORIZON_LEN,
        ge=1,
        le=HORIZON_LEN,
        description="Number of months to forecast.",
    )
    confidence_interval: float = Field(
        default=TARGET_COV,
        gt=0.0,
        lt=1.0,
        description="Coverage probability for the conformal prediction interval.",
    )


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
