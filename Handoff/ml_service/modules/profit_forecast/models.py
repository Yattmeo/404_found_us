"""
models.py — Pydantic request/response models for the GetProfitForecast module.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .config import DEFAULT_CONFIDENCE_INTERVAL, DEFAULT_N_SIMULATIONS, HORIZON_LEN


# ---------------------------------------------------------------------------
# Upstream service output models (accept the JSON responses as-is)
# ---------------------------------------------------------------------------

class TPVForecastMonth(BaseModel, extra="ignore"):
    month_index: int
    tpv_mid: float
    tpv_ci_lower: Optional[float] = None
    tpv_ci_upper: Optional[float] = None


class TPVConformalMetadata(BaseModel, extra="ignore"):
    half_width_dollars: float
    conformal_mode: str = "unknown"


class TPVProcessMetadata(BaseModel, extra="ignore"):
    context_len_used: int = 0


class TPVServiceOutput(BaseModel, extra="ignore"):
    forecast: List[TPVForecastMonth]
    conformal_metadata: TPVConformalMetadata
    process_metadata: TPVProcessMetadata = TPVProcessMetadata()


class CostForecastMonth(BaseModel, extra="ignore"):
    month_index: int
    proc_cost_pct_mid: float
    proc_cost_pct_ci_lower: Optional[float] = None
    proc_cost_pct_ci_upper: Optional[float] = None


class CostConformalMetadata(BaseModel, extra="ignore"):
    half_width: float
    conformal_mode: str = "unknown"


class CostProcessMetadata(BaseModel, extra="ignore"):
    context_len_used: int = 0


class CostServiceOutput(BaseModel, extra="ignore"):
    forecast: List[CostForecastMonth]
    conformal_metadata: CostConformalMetadata
    process_metadata: CostProcessMetadata = CostProcessMetadata()


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class ProfitForecastRequest(BaseModel):
    tpv_service_output: TPVServiceOutput = Field(
        ..., description="Full JSON response from POST /GetTPVForecast.",
    )
    cost_service_output: CostServiceOutput = Field(
        ..., description="Full JSON response from POST /GetCostForecast.",
    )
    fee_rate: float = Field(
        ..., gt=0.0, lt=1.0,
        description="Merchant fee rate as a fraction of TPV (e.g. 0.029 = 2.9%).",
    )
    fixed_fee_per_tx: float = Field(
        default=0.0, ge=0.0,
        description="Fixed per-transaction fee in dollars (e.g. 0.30). Added deterministically to revenue.",
    )
    avg_ticket: Optional[float] = Field(
        default=None, gt=0.0,
        description="Average transaction amount in dollars. Used to derive tx count from TPV for fixed-fee revenue.",
    )
    mcc: int = Field(..., description="Merchant category code.")
    merchant_id: Optional[str] = Field(default=None)
    confidence_interval: float = Field(
        default=DEFAULT_CONFIDENCE_INTERVAL, gt=0.0, lt=1.0,
    )
    n_simulations: int = Field(
        default=DEFAULT_N_SIMULATIONS, ge=100, le=1_000_000,
    )
    target_margin: Optional[float] = Field(
        default=None,
        description="Optional target profit margin (fee_rate − cost_pct).",
    )


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class ProfitMonth(BaseModel):
    month_index: int
    tpv_mid: float
    cost_pct_mid: float
    revenue_mid: float
    cost_mid: float
    profit_mid: float
    margin_mid: float
    p_profitable: float
    profit_ci_lower: float
    profit_ci_upper: float
    profit_median: float
    profit_std: float
    simulation_mean: float
    p_target_margin_met: Optional[float] = None


class ProfitSummary(BaseModel):
    total_profit_mid: float
    total_revenue_mid: float
    total_cost_mid: float
    avg_p_profitable: float
    min_p_profitable: float
    break_even_fee_rate: float
    suggested_fee_for_target: Optional[float] = None
    avg_p_target_margin_met: Optional[float] = None
    min_p_target_margin_met: Optional[float] = None


class SimulationMetadata(BaseModel):
    fee_rate: float
    n_simulations: int
    confidence_interval: float
    mcc: int
    merchant_id: Optional[str]
    horizon_months: int
    tpv_conformal_mode: str
    cost_conformal_mode: str
    tpv_context_len_used: int
    cost_context_len_used: int
    generated_at_utc: datetime
    target_margin: Optional[float] = None
    correlation_assumed: str = "independent"
    cost_sampling_strategy: str = Field(
        default="ci_shaped_soft_guardrails",
        description=(
            "Cost sampling uses conformal CI as a soft guardrail with explicit tails."
        ),
    )
    cost_ci_tail_probability: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description=(
            "Total probability mass allowed outside cost CI (split across both tails)."
        ),
    )
    cost_ci_hard_clip: bool = Field(
        default=False,
        description="False means samples may exceed CI bounds in tails; no hard clipping.",
    )


class ProfitForecastResponse(BaseModel):
    months: List[ProfitMonth]
    summary: ProfitSummary
    metadata: SimulationMetadata
