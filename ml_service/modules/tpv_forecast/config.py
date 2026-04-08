"""
config.py — GetTPVForecast configuration constants (v2).

Adapted for embedding inside ml_service.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Pipeline constants
# ---------------------------------------------------------------------------
SUPPORTED_CONTEXT_LENS: list[int] = [1, 3, 6]
MAX_CONTEXT_LEN: int = max(SUPPORTED_CONTEXT_LENS)
HORIZON_LEN: int = 3
TARGET_COV: float = 0.90
MIN_POOL: int = 10
KNN_K: int = 10

# ---------------------------------------------------------------------------
# Target column names
# ---------------------------------------------------------------------------
TARGET_COL: str = "total_processing_value"
LOG_TARGET: str = "log_tpv"

# ---------------------------------------------------------------------------
# Guard constants
# ---------------------------------------------------------------------------
_VOL_EPS: float = 1e-6
VOL_MIN_GAIN_ABS: float = 0.05
VOL_MIN_GAIN_REL: float = 0.01
VOL_TEST_COV_SLACK: float = 0.03

# ---------------------------------------------------------------------------
# Stratification schemes
# ---------------------------------------------------------------------------
VOL_BUCKET_SCHEMES: dict[str, list[float]] = {
    "low-mid-high_50_85":          [0.00, 0.50, 0.85, 1.00],
    "low-mid-high_40_80":          [0.00, 0.40, 0.80, 1.00],
    "low-mid-high_60_90":          [0.00, 0.60, 0.90, 1.00],
    "low-mid-high-vhigh_50_75_90": [0.00, 0.50, 0.75, 0.90, 1.00],
    "low-mid-high-vhigh_40_70_88": [0.00, 0.40, 0.70, 0.88, 1.00],
    "low-mid-high-vhigh_60_85_95": [0.00, 0.60, 0.85, 0.95, 1.00],
}

# ---------------------------------------------------------------------------
# Feature names
# ---------------------------------------------------------------------------
MODEL_FEAT_NAMES: list[str] = [
    "context_mean", "context_std", "momentum", "pool_mean",
    "txn_amount_std", "log_txn_count", "avg_median_txn_gap",
    "last_month", "log_avg_txn_val", "momentum_tc", "momentum_atv",
]

RISK_FEAT_NAMES: list[str] = [
    "intra_txn_cov", "avg_median_txn_gap", "log_txn_count",
    "cost_type_hhi", "log_avg_txn_val", "txn_amount_cov",
    "pool_mean_gap_ratio", "ctx_to_knn_gap_ratio", "ctx_cov",
    "tc_cov", "atv_cov",
]

# ---------------------------------------------------------------------------
# GBR risk model hyper-parameters
# ---------------------------------------------------------------------------
GBR_N_ESTIMATORS: int = 120
GBR_LEARNING_RATE: float = 0.05
GBR_MAX_DEPTH: int = 2
GBR_MIN_SAMPLES_LEAF: int = max(20, MIN_POOL)
GBR_SUBSAMPLE: float = 0.8
GBR_RANDOM_STATE: int = 4121

# ---------------------------------------------------------------------------
# Supported MCCs
# ---------------------------------------------------------------------------
SUPPORTED_MCCS: list[int] = [4121, 5411, 5499, 5812]

# ---------------------------------------------------------------------------
# Artifact storage — defaults to a mounted volume path in Docker
# ---------------------------------------------------------------------------
ARTIFACTS_BASE_PATH: Path = Path(
    os.getenv("TPV_ARTIFACTS_BASE_PATH", "/app/artifacts/tpv")
)

# ---------------------------------------------------------------------------
# Hot-reload interval
# ---------------------------------------------------------------------------
ARTIFACT_POLL_INTERVAL_S: float = float(
    os.getenv("ARTIFACT_POLL_INTERVAL_S", "60")
)
