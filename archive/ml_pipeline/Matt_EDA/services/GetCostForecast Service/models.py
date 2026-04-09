from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config import DEFAULT_CONFIDENCE_INTERVAL, DEFAULT_FORECAST_HORIZON_WKS


# ---------------------------------------------------------------------------
# Composite weekly feature row
# Mirrors the weekly_features items returned by /getCompositeMerchant.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class CostForecastRequest(BaseModel):
    """
    Input for POST /GetCostForecast.

    composite_weekly_features   — weekly history produced by /getCompositeMerchant.
    onboarding_merchant_txn_df  — raw transaction rows for the onboarding merchant,
                                  used to build the calibration window.
                                  Each row must contain 'amount' and 'proc_cost'.
                                  The date field may be named 'date' or
                                  'transaction_date'.
    """

    composite_weekly_features: List[CompositeWeeklyFeature] = Field(
        ...,
        min_length=1,
        description="Weekly composite feature history from /getCompositeMerchant.",
    )
    onboarding_merchant_txn_df: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Raw onboarding transactions used for calibration alignment.  "
            "Rows without 'proc_cost' are silently skipped."
        ),
    )
    composite_merchant_id: Optional[str] = Field(
        default=None,
        description="Identifier from /getCompositeMerchant; carried through for traceability.",
    )
    mcc: Optional[int] = Field(
        default=None,
        description="Merchant category code; carried through for traceability.",
    )
    forecast_horizon_wks: int = Field(
        default=DEFAULT_FORECAST_HORIZON_WKS,
        ge=1,
        le=104,
        description="Number of weeks to forecast ahead.",
    )
    confidence_interval: float = Field(
        default=DEFAULT_CONFIDENCE_INTERVAL,
        gt=0.0,
        lt=1.0,
        description="Coverage probability for the forecast confidence interval.",
    )
    use_optimised_sarima: bool = Field(
        default=False,
        description=(
            "If True, run an AIC-guided grid search to select SARIMA orders.  "
            "Bounded by SARIMA_OPTIMISATION_TIMEOUT_S in config."
        ),
    )
    use_exogenous_sarimax: bool = Field(
        default=False,
        description=(
            "If True, fit SARIMAX with exogenous variables derived from core "
            "composite weekly features.  Future exogenous values are carried "
            "forward from the last observed week."
        ),
    )
    use_guarded_calibration: bool = Field(
        default=True,
        description=(
            "If True, fit a guarded linear calibrator on aligned onboarding actuals "
            "and apply it to the SARIMA forecast midpoint."
        ),
    )


# ---------------------------------------------------------------------------
# Response — forecast items
# ---------------------------------------------------------------------------

class ForecastWeek(BaseModel):
    forecast_week_index: int = Field(
        ..., description="Week index after calibration window (e.g., if context has 4 weeks, forecast starts at week 5)."
    )
    proc_cost_pct_mid: float
    proc_cost_pct_ci_lower: float
    proc_cost_pct_ci_upper: float


# ---------------------------------------------------------------------------
# Response — SARIMA metadata
# ---------------------------------------------------------------------------

class SarimaMetadata(BaseModel):
    seasonal_length: int = Field(..., description="Seasonal period used (s).")
    use_optimised_sarima: bool
    use_exogenous_sarimax: bool
    exogenous_feature_names: List[str]
    selected_order: List[int] = Field(..., description="[p, d, q]")
    selected_seasonal_order: List[int] = Field(..., description="[P, D, Q, s]")
    aic: Optional[float]
    fit_status: str = Field(
        ...,
        description="One of: ok | failed | fallback",
    )
    optimisation_attempted: bool
    optimisation_time_ms: Optional[float]
    optimisation_candidates_evaluated: int


# ---------------------------------------------------------------------------
# Response — process metadata
# ---------------------------------------------------------------------------

class ProcessMetadata(BaseModel):
    context_window_weeks_count: int = Field(
        ...,
        description=(
            "Number of distinct weeks in the onboarding df.  "
            "Determines how many calibration alignment points are possible."
        ),
    )
    matched_calibration_points: int = Field(
        ...,
        description=(
            "Number of onboarding weeks whose (calendar_year, week_of_year) key "
            "matched a row in the composite history and had a non-NaN SARIMA "
            "fitted value."
        ),
    )
    calibration_mode: str = Field(
        ...,
        description=(
            "One of: guarded_linear | skipped_insufficient_data | "
            "skipped_flat_predictions | skipped_linalg_error | "
            "skipped_no_improvement | skipped_disabled | not_applicable"
        ),
    )
    is_fallback: bool = Field(
        ...,
        description=(
            "True when SARIMA could not be fit and the response is a flat "
            "constant forecast equal to the onboarding mean."
        ),
    )
    fallback_reason: Optional[str]
    fallback_mean_proc_cost_pct: Optional[float] = Field(
        default=None,
        description="Constant proc_cost_pct used for all forecast weeks in fallback mode.",
    )
    context_window_mean_proc_cost_pct: Optional[float] = Field(
        default=None,
        description="Mean proc_cost_pct across all onboarding calibration weeks.",
    )
    generated_at_utc: datetime
    forecast_horizon_wks: int
    confidence_interval: float
    used_guarded_calibration: bool
    calibration_successful: bool = Field(
        ...,
        description="True when guarded calibration was actually fitted and applied.",
    )
    calibration_mae: Optional[float] = Field(
        default=None,
        description="MAE on calibration alignment points after guarded calibration.",
    )
    calibration_rmse: Optional[float] = Field(
        default=None,
        description="RMSE on calibration alignment points after guarded calibration.",
    )
    calibration_r2: Optional[float] = Field(
        default=None,
        description="R² on calibration alignment points after guarded calibration.",
    )


# ---------------------------------------------------------------------------
# Response — top level
# ---------------------------------------------------------------------------

class CostForecastResponse(BaseModel):
    process_metadata: ProcessMetadata
    sarima_metadata: SarimaMetadata
    is_guarded_sarima: bool = Field(
        ...,
        description="True when guarded linear calibration was successfully applied.",
    )
    forecast: List[ForecastWeek]
    context_sarima_fitted: List[Optional[float]] = Field(
        default_factory=list,
        description=(
            "SARIMA generated values aligned to the onboarding context window, one "
            "entry per onboarding week in chronological order.  None where the week "
            "had no matching composite key or no valid generated value."
        ),
    )
