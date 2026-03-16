from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .config import DEFAULT_CONFIDENCE_INTERVAL, DEFAULT_FORECAST_HORIZON_WKS


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


class VolumeForecastRequest(BaseModel):
    composite_weekly_features: List[CompositeWeeklyFeature] = Field(..., min_length=1)
    onboarding_merchant_txn_df: List[Dict[str, Any]] = Field(default_factory=list)
    composite_merchant_id: Optional[str] = None
    mcc: Optional[int] = None
    forecast_horizon_wks: int = Field(default=DEFAULT_FORECAST_HORIZON_WKS, ge=1, le=104)
    confidence_interval: float = Field(default=DEFAULT_CONFIDENCE_INTERVAL, gt=0.0, lt=1.0)
    use_optimised_sarima: bool = False
    use_exogenous_sarimax: bool = False
    use_guarded_calibration: bool = True


class ForecastWeek(BaseModel):
    forecast_week_index: int
    total_proc_value_mid: float
    total_proc_value_ci_lower: float
    total_proc_value_ci_upper: float


class SarimaMetadata(BaseModel):
    seasonal_length: int
    use_optimised_sarima: bool
    use_exogenous_sarimax: bool
    exogenous_feature_names: List[str]
    selected_order: List[int]
    selected_seasonal_order: List[int]
    aic: Optional[float]
    fit_status: str
    optimisation_attempted: bool
    optimisation_time_ms: Optional[float]
    optimisation_candidates_evaluated: int


class ProcessMetadata(BaseModel):
    context_window_weeks_count: int
    matched_calibration_points: int
    calibration_mode: str
    is_fallback: bool
    fallback_reason: Optional[str]
    fallback_mean_total_proc_value: Optional[float] = None
    context_window_mean_total_proc_value: Optional[float] = None
    generated_at_utc: datetime
    forecast_horizon_wks: int
    confidence_interval: float
    used_guarded_calibration: bool
    calibration_successful: bool
    calibration_mae: Optional[float] = None
    calibration_rmse: Optional[float] = None
    calibration_r2: Optional[float] = None


class VolumeForecastResponse(BaseModel):
    process_metadata: ProcessMetadata
    sarima_metadata: SarimaMetadata
    is_guarded_sarima: bool
    forecast: List[ForecastWeek]
    context_sarima_fitted: List[Optional[float]] = Field(default_factory=list)
