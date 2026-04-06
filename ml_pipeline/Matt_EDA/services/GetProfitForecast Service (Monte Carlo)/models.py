"""
models.py — Pydantic request/response models for the GetProfitForecast Service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config import DEFAULT_CONFIDENCE_INTERVAL, DEFAULT_N_SIMULATIONS, HORIZON_LEN


# ---------------------------------------------------------------------------
# Upstream service output models (accept the JSON responses as-is)
# ---------------------------------------------------------------------------

class TPVForecastMonth(BaseModel, extra="ignore"):
    month_index: int
    tpv_mid: float


class TPVConformalMetadata(BaseModel, extra="ignore"):
    half_width_dollars: float
    conformal_mode: str = "unknown"


class TPVProcessMetadata(BaseModel, extra="ignore"):
    context_len_used: int = 0


class TPVServiceOutput(BaseModel, extra="ignore"):
    """
    The full JSON response from GetTPVForecast.
    Pass it directly — extra fields are ignored.
    """
    forecast: List[TPVForecastMonth]
    conformal_metadata: TPVConformalMetadata
    process_metadata: TPVProcessMetadata = TPVProcessMetadata()


class CostForecastMonth(BaseModel, extra="ignore"):
    month_index: int
    proc_cost_pct_mid: float


class CostConformalMetadata(BaseModel, extra="ignore"):
    half_width: float
    conformal_mode: str = "unknown"


class CostProcessMetadata(BaseModel, extra="ignore"):
    context_len_used: int = 0


class CostServiceOutput(BaseModel, extra="ignore"):
    """
    The full JSON response from GetM9MonthlyCostForecast.
    Pass it directly — extra fields are ignored.
    """
    forecast: List[CostForecastMonth]
    conformal_metadata: CostConformalMetadata
    process_metadata: CostProcessMetadata = CostProcessMetadata()


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class ProfitForecastRequest(BaseModel):
    """
    Input for POST /GetProfitForecast.

    The caller (orchestrator) provides:
      - The full JSON response from the TPV forecast service
      - The full JSON response from the AvgProcCost forecast service
      - The merchant fee rate

    This service does NOT call the upstream services. The orchestrator
    is responsible for calling them and passing the outputs here.
    """

    tpv_service_output: TPVServiceOutput = Field(
        ...,
        description=(
            "Full JSON response from POST /GetTPVForecast. "
            "Extra fields are ignored — just pass the response as-is."
        ),
    )
    cost_service_output: CostServiceOutput = Field(
        ...,
        description=(
            "Full JSON response from POST /GetM9MonthlyCostForecast. "
            "Extra fields are ignored — just pass the response as-is."
        ),
    )
    fee_rate: float = Field(
        ...,
        gt=0.0,
        lt=1.0,
        description=(
            "Merchant fee rate as a fraction of TPV (e.g. 0.029 = 2.9%). "
            "This is what the acquirer charges the merchant per dollar processed."
        ),
    )
    mcc: int = Field(..., description="Merchant category code.")
    merchant_id: Optional[str] = Field(
        default=None,
        description="Opaque merchant identifier for traceability.",
    )
    confidence_interval: float = Field(
        default=DEFAULT_CONFIDENCE_INTERVAL,
        gt=0.0,
        lt=1.0,
        description="Coverage probability for the profit CI percentiles.",
    )
    n_simulations: int = Field(
        default=DEFAULT_N_SIMULATIONS,
        ge=100,
        le=1_000_000,
        description="Number of Monte Carlo samples for the profit distribution.",
    )


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class ProfitMonth(BaseModel):
    """Profit analysis for one forecast month."""

    month_index: int = Field(
        ..., description="1-based index (1 = first forecast month).",
    )

    # ── Upstream point forecasts ──────────────────────────────────────────────
    tpv_mid: float = Field(
        ..., description="TPV point forecast (dollars).",
    )
    cost_pct_mid: float = Field(
        ..., description="avg_proc_cost_pct point forecast.",
    )

    # ── Profit ────────────────────────────────────────────────────────────────
    revenue_mid: float = Field(
        ..., description="Expected revenue = tpv_mid × fee_rate.",
    )
    cost_mid: float = Field(
        ..., description="Expected cost = tpv_mid × cost_pct_mid.",
    )
    profit_mid: float = Field(
        ..., description="Expected profit = revenue_mid − cost_mid.",
    )
    margin_mid: float = Field(
        ..., description="Profit margin = (fee_rate − cost_pct_mid). Can be negative.",
    )

    # ── Monte Carlo distribution ──────────────────────────────────────────────
    p_profitable: float = Field(
        ..., description="P(profit > 0) from Monte Carlo simulation.",
    )
    profit_ci_lower: float = Field(
        ..., description="Lower percentile of the profit distribution (dollars).",
    )
    profit_ci_upper: float = Field(
        ..., description="Upper percentile of the profit distribution (dollars).",
    )
    profit_median: float = Field(
        ..., description="Median profit from Monte Carlo (dollars).",
    )
    profit_std: float = Field(
        ..., description="Standard deviation of profit distribution (dollars).",
    )


class ProfitSummary(BaseModel):
    """Aggregate across all horizon months."""

    total_profit_mid: float = Field(
        ..., description="Sum of profit_mid across all forecast months.",
    )
    total_revenue_mid: float = Field(
        ..., description="Sum of revenue_mid across all forecast months.",
    )
    total_cost_mid: float = Field(
        ..., description="Sum of cost_mid across all forecast months.",
    )
    avg_p_profitable: float = Field(
        ..., description="Average P(profitable) across months.",
    )
    min_p_profitable: float = Field(
        ..., description="Worst-case P(profitable) across months.",
    )
    break_even_fee_rate: float = Field(
        ...,
        description=(
            "Minimum fee_rate needed for the worst-month cost CI upper bound. "
            "Setting fee_rate ≥ this value gives ~95% confidence of profitability."
        ),
    )


class SimulationMetadata(BaseModel):
    """Transparency about simulation parameters and upstream calls."""

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
    correlation_assumed: str = Field(
        default="independent",
        description="'independent' — ρ ≈ 0.14, below 0.15 threshold.",
    )


class ProfitForecastResponse(BaseModel):
    """Full response from POST /GetProfitForecast."""

    months: List[ProfitMonth] = Field(
        ..., description="Per-month profit analysis.",
    )
    summary: ProfitSummary
    metadata: SimulationMetadata
