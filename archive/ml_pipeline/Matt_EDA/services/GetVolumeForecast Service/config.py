# ---------------------------------------------------------------------------
# GetVolumeForecast Service — Configuration Constants
# ---------------------------------------------------------------------------

# SARIMA fixed orders
SARIMA_D_FIXED: int = 1
SARIMA_D_SEASONAL_FIXED: int = 1
SARIMA_SEASONAL_PERIOD: int = 13

# SARIMA optimisation grid
SARIMA_P_CANDIDATES: list[int] = [0, 1]
SARIMA_Q_CANDIDATES: list[int] = [0, 1]
SARIMA_P_SEASONAL_CANDIDATES: list[int] = [0, 1]
SARIMA_Q_SEASONAL_CANDIDATES: list[int] = [0, 1]
SARIMA_OPTIMISATION_TIMEOUT_S: float = 20.0

# SARIMA defaults
SARIMA_DEFAULT_P: int = 1
SARIMA_DEFAULT_Q: int = 1
SARIMA_DEFAULT_P_SEASONAL: int = 1
SARIMA_DEFAULT_Q_SEASONAL: int = 1

# Exogenous features for volume forecasting
EXOGENOUS_FEATURE_COLUMNS: list[str] = [
    "weekly_txn_count_mean",
    "weekly_txn_count_stdev",
    "weekly_avg_txn_value_mean",
    "weekly_avg_txn_value_stdev",
    "weekly_total_proc_value_stdev",
    "weekly_avg_txn_cost_pct_mean",
    "weekly_avg_txn_cost_pct_stdev",
    "neighbor_coverage",
]

# Calibration guardrails
CALIBRATION_MIN_MATCHED_POINTS: int = 2
CALIBRATION_MIN_PRED_STD: float = 1e-4
CALIBRATION_MAX_ABS_SLOPE: float = 10.0
CALIBRATION_MAX_ABS_INTERCEPT: float = 50.0
CALIBRATION_MAX_ABS_INTERCEPT_RELATIVE_TO_CONTEXT_MEAN: float = 2.0

# Fallback
FALLBACK_MIN_HISTORY_WEEKS: int = 4

# Forecast defaults
DEFAULT_FORECAST_HORIZON_WKS: int = 12
DEFAULT_CONFIDENCE_INTERVAL: float = 0.95
