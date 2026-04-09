"""
Pydantic models mirroring the M9 v2 service's request/response contracts.

These are kept here so that ml_service can validate payloads before proxying
to the standalone m9-forecast-service container.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── Request ────────────────────────────────────────────────────────────────

class ContextMonth(BaseModel):
    year: int
    month: int = Field(..., ge=1, le=12)
    avg_proc_cost_pct: float
    std_proc_cost_pct: float = 0.0
    median_proc_cost_pct: float = 0.0
    transaction_count: int = 1
    avg_transaction_value: float = 0.0
    std_txn_amount: float = 0.0
    cost_type_pcts: Optional[Dict[str, float]] = None


class M9ForecastRequest(BaseModel):
    context_months: List[ContextMonth]
    pool_mean_at_context_end: float
    knn_pool_mean_at_context_end: float
    peer_merchant_ids: Optional[List[int]] = None
    merchant_id: Optional[str] = None
    mcc: int
    horizon_months: int = 3
    confidence_interval: float = 0.90


# ── Response ───────────────────────────────────────────────────────────────

class ForecastMonth(BaseModel):
    month_index: int
    proc_cost_pct_mid: float
    proc_cost_pct_ci_lower: float
    proc_cost_pct_ci_upper: float


class ConformalMetadata(BaseModel):
    half_width: float
    conformal_mode: str
    pool_size: int
    risk_score: Optional[float] = None
    strat_scheme: Optional[str] = None


class ProcessMetadata(BaseModel):
    context_len_used: int
    context_mean: float
    context_std: float
    momentum: float
    pool_mean_used: float
    mcc: int
    model_variant: str = "m9_v2"
    horizon_months: int
    confidence_interval: float
    generated_at_utc: str
    artifact_trained_at: str
    strat_enabled: bool


class M9ForecastResponse(BaseModel):
    forecast: List[ForecastMonth]
    conformal_metadata: ConformalMetadata
    process_metadata: ProcessMetadata
