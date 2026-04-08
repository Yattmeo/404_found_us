"""
Pydantic models for the Huber-based TPV (Total Payment Volume) forecast service.

Mirrors the M9 cost forecast model structure but targets monthly TPV in dollars,
trained in log1p-space with conformal intervals calibrated in dollar space.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ── Request ────────────────────────────────────────────────────────────────

class TpvContextMonth(BaseModel):
    year: int
    month: int = Field(..., ge=1, le=12)
    total_payment_volume: float        # Monthly TPV in dollars
    transaction_count: int = 1
    avg_transaction_value: float = 0.0
    std_txn_amount: float = 0.0
    median_txn_amount: Optional[float] = None  # defaults to avg_transaction_value when None


class TpvForecastRequest(BaseModel):
    context_months: List[TpvContextMonth]
    # log1p-space pool means of KNN peers (use context mean when unknown)
    pool_log_mean_at_context_end: float = 0.0
    knn_pool_log_mean_at_context_end: float = 0.0
    mcc: int
    horizon_months: int = 3
    confidence_interval: float = 0.90


# ── Response ───────────────────────────────────────────────────────────────

class TpvForecastMonth(BaseModel):
    month_index: int
    total_proc_value_mid: float
    total_proc_value_ci_lower: float
    total_proc_value_ci_upper: float


class TpvConformalMetadata(BaseModel):
    half_width_dollars: float
    conformal_mode: str
    pool_size: int
    risk_score: Optional[float] = None


class TpvProcessMetadata(BaseModel):
    context_len_used: int
    context_mean_log_tpv: float
    mcc: int
    model_variant: str = "tpv_v2"
    horizon_months: int
    confidence_interval: float
    generated_at_utc: str
    artifact_trained_at: str


class TpvForecastResponse(BaseModel):
    forecast: List[TpvForecastMonth]
    conformal_metadata: TpvConformalMetadata
    process_metadata: TpvProcessMetadata
