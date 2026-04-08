"""Pydantic models for the in-process Monte Carlo profit forecast module."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ── Upstream service output shapes (extras ignored) ───────────────────────

class CostForecastMonthInput(BaseModel, extra="ignore"):
    month_index: int = 0
    proc_cost_pct_mid: float
    proc_cost_pct_ci_lower: Optional[float] = None
    proc_cost_pct_ci_upper: Optional[float] = None


class CostConformalInput(BaseModel, extra="ignore"):
    half_width: float = 0.005
    conformal_mode: str = "unknown"


class CostProcessInput(BaseModel, extra="ignore"):
    context_len_used: int = 0


class CostServiceInput(BaseModel, extra="ignore"):
    forecast: List[CostForecastMonthInput]
    conformal_metadata: Optional[CostConformalInput] = None
    process_metadata: Optional[CostProcessInput] = None


class VolumeForecastWeekInput(BaseModel, extra="ignore"):
    forecast_week_index: int = 0
    total_proc_value_mid: float
    total_proc_value_ci_lower: Optional[float] = None
    total_proc_value_ci_upper: Optional[float] = None


class VolumeServiceInput(BaseModel, extra="ignore"):
    forecast: List[VolumeForecastWeekInput]


# ── Request ───────────────────────────────────────────────────────────────

class ProfitForecastRequest(BaseModel):
    cost_service_output: CostServiceInput
    volume_service_output: VolumeServiceInput
    fee_rate: float = Field(..., gt=0.0, lt=1.0)
    mcc: int = 5411
    confidence_interval: float = Field(default=0.90, gt=0.0, lt=1.0)
    n_simulations: int = Field(default=10_000, ge=100, le=1_000_000)
    target_margin: Optional[float] = None
    rate_grid_pct: Optional[List[float]] = None


# ── Response ──────────────────────────────────────────────────────────────

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


class ProfitabilityCurvePoint(BaseModel):
    rate_pct: float
    probability_pct: float
    profitability_pct: float = 0.0


class ProfitSummary(BaseModel):
    total_profit_mid: float
    total_revenue_mid: float
    total_cost_mid: float
    avg_p_profitable: float
    min_p_profitable: float
    break_even_fee_rate: float
    estimated_profit_min: float
    estimated_profit_max: float
    profitability_curve: List[ProfitabilityCurvePoint]


class ProfitForecastResponse(BaseModel):
    months: List[ProfitMonth]
    summary: ProfitSummary
