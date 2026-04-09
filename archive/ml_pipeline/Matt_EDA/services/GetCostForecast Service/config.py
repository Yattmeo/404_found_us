# ---------------------------------------------------------------------------
# GetCostForecast Service — Configuration Constants
#
# All tunable parameters are collected here so they can be reviewed and
# changed without hunting through service logic.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# SARIMA fixed orders
# d and D are fixed to enforce stationarity / seasonal differencing.
# ---------------------------------------------------------------------------
SARIMA_D_FIXED: int = 1          # non-seasonal differencing order (always 1)
SARIMA_D_SEASONAL_FIXED: int = 1  # seasonal differencing order (always 1)
SARIMA_SEASONAL_PERIOD: int = 13  # weeks in one seasonal cycle

# ---------------------------------------------------------------------------
# SARIMA optimisation grid
# When use_optimised_sarima=True the service performs an AIC-guided grid
# search over the Cartesian product of these candidate values.
# Keep the grid small — the sub-30 s response budget limits how many SARIMAX
# fits can run.  Adding a single element roughly doubles search time.
# ---------------------------------------------------------------------------
SARIMA_P_CANDIDATES: list[int] = [0, 1]   # non-seasonal AR candidates
SARIMA_Q_CANDIDATES: list[int] = [0, 1]   # non-seasonal MA candidates
SARIMA_P_SEASONAL_CANDIDATES: list[int] = [0, 1]  # seasonal AR candidates
SARIMA_Q_SEASONAL_CANDIDATES: list[int] = [0, 1]  # seasonal MA candidates

# Maximum wall-clock time (seconds) allowed for the entire grid search.
# If the budget is exceeded the best model found so far is kept.
SARIMA_OPTIMISATION_TIMEOUT_S: float = 20.0

# ---------------------------------------------------------------------------
# SARIMA default (non-optimised) order
# Used when use_optimised_sarima=False or as the starting candidate.
# ---------------------------------------------------------------------------
SARIMA_DEFAULT_P: int = 1
SARIMA_DEFAULT_Q: int = 1
SARIMA_DEFAULT_P_SEASONAL: int = 1
SARIMA_DEFAULT_Q_SEASONAL: int = 1

# ---------------------------------------------------------------------------
# Exogenous SARIMAX features
# Used when use_exogenous_sarimax=True.
# ---------------------------------------------------------------------------
EXOGENOUS_FEATURE_COLUMNS: list[str] = [
    "weekly_txn_count_mean",
    "weekly_total_proc_value_mean",
    "weekly_avg_txn_value_mean",
    "weekly_txn_count_stdev",
    "weekly_total_proc_value_stdev",
    "weekly_avg_txn_value_stdev",
    "weekly_avg_txn_cost_pct_stdev",
    "neighbor_coverage",
]

# ---------------------------------------------------------------------------
# Calibration guardrails
# Applied when use_guarded_calibration=True to prevent the linear
# calibrator from extrapolating wildly.
# ---------------------------------------------------------------------------
CALIBRATION_MIN_MATCHED_POINTS: int = 2    # minimum aligned calibration points required
CALIBRATION_MIN_PRED_STD: float = 1e-4     # minimum std-dev of SARIMA predictions in
                                            # the calibration window before calibration
                                            # is skipped (prevents near-constant series)
CALIBRATION_MAX_ABS_SLOPE: float = 10.0    # clamp calibrator slope to ±this value
CALIBRATION_MAX_ABS_INTERCEPT: float = 0.05  # absolute minimum intercept clamp
CALIBRATION_MAX_ABS_INTERCEPT_RELATIVE_TO_CONTEXT_MEAN: float = 2.0
# Final intercept clamp is:
# max(CALIBRATION_MAX_ABS_INTERCEPT,
#     CALIBRATION_MAX_ABS_INTERCEPT_RELATIVE_TO_CONTEXT_MEAN * |context_mean|)

# ---------------------------------------------------------------------------
# Fallback behaviour
# When the service cannot produce a reliable SARIMA-calibrated forecast it
# falls back to the onboarding mean as a flat (constant) forecast.
# ---------------------------------------------------------------------------
FALLBACK_MIN_HISTORY_WEEKS: int = 4   # minimum composite history rows needed
                                       # to attempt SARIMA at all

# ---------------------------------------------------------------------------
# Forecast defaults
# Callers can override both values in the request body; these are the
# server-side defaults applied when the fields are omitted.
# ---------------------------------------------------------------------------
DEFAULT_FORECAST_HORIZON_WKS: int = 12    # forecast weeks ahead
DEFAULT_CONFIDENCE_INTERVAL: float = 0.95  # CI coverage (0 < value < 1)
