# ---------------------------------------------------------------------------
# GetM9MonthlyCostForecast Service — Configuration Constants  (v2)
#
# All pipeline constants live here.  The training script (train.py) imports
# these directly so the service and batch job always share the same values.
# ---------------------------------------------------------------------------

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Pipeline constants — must be identical to those used when train.py ran
# ---------------------------------------------------------------------------
SUPPORTED_CONTEXT_LENS: list[int] = [1, 3, 6]  # all accepted context lengths
MAX_CONTEXT_LEN: int = max(SUPPORTED_CONTEXT_LENS)
HORIZON_LEN: int = 3       # months to forecast (t+1 … t+HORIZON_LEN)
TARGET_COV: float = 0.90   # desired conformal coverage probability
MIN_POOL: int = 10          # minimum residuals / bucket members for conformal
KNN_K: int = 10             # k for kNN pool mean computation in train.py

# ---------------------------------------------------------------------------
# Guard against zero division for near-constant series
# ---------------------------------------------------------------------------
_VOL_EPS: float = 1e-6

# ---------------------------------------------------------------------------
# Stratification guard (matches notebook production values)
# ---------------------------------------------------------------------------
VOL_MIN_GAIN_ABS: float = 0.05           # absolute minimum width gain (pp)
VOL_MIN_GAIN_REL: float = 0.01           # relative gain factor × flat_avg_hw
VOL_TEST_COV_SLACK: float = 0.03         # coverage floor = TARGET_COV − this

# ---------------------------------------------------------------------------
# Candidate stratification schemes (auto‑selected at training time)
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
# Feature names (v2 pipeline)
# ---------------------------------------------------------------------------
MODEL_FEAT_NAMES: list[str] = [
    "context_mean", "context_std", "momentum", "pool_mean",
    "intra_std", "log_txn_count", "mean_median_gap",
]

RISK_FEAT_NAMES: list[str] = [
    "intra_cov", "mean_median_gap", "log_txn_count",
    "cost_type_hhi", "log_avg_txn_val", "txn_amount_cov",
    "pool_mean_gap_ratio", "ctx_to_knn_gap_ratio", "ctx_cov",
]

# ---------------------------------------------------------------------------
# GBR risk model hyper-parameters (shared with train.py)
# ---------------------------------------------------------------------------
GBR_N_ESTIMATORS: int = 120
GBR_LEARNING_RATE: float = 0.05
GBR_MAX_DEPTH: int = 2
GBR_MIN_SAMPLES_LEAF: int = max(20, MIN_POOL)
GBR_SUBSAMPLE: float = 0.8
GBR_RANDOM_STATE: int = 4121

# ---------------------------------------------------------------------------
# Supported MCCs
# Artifacts must exist under ARTIFACTS_BASE_PATH/{mcc}/{ctx_len}/ for each entry.
# ---------------------------------------------------------------------------
SUPPORTED_MCCS: list[int] = [5411]

# ---------------------------------------------------------------------------
# Artifact storage (local filesystem for PoC)
# Override via env-var ARTIFACTS_BASE_PATH for Docker / CI usage.
# ---------------------------------------------------------------------------
ARTIFACTS_BASE_PATH: Path = Path(
    os.getenv("ARTIFACTS_BASE_PATH", str(Path(__file__).parent / "artifacts"))
)

# ---------------------------------------------------------------------------
# Hot-reload
# Service background thread polls config_snapshot.json mtime every N seconds.
# ---------------------------------------------------------------------------
ARTIFACT_POLL_INTERVAL_S: float = float(
    os.getenv("ARTIFACT_POLL_INTERVAL_S", "60")
)

# ---------------------------------------------------------------------------
# Training defaults (used by train.py CLI)
# ---------------------------------------------------------------------------
DEFAULT_WINDOW_YEARS: int = 3   # rolling training window length

# ---------------------------------------------------------------------------
# v2 CSV columns required for transaction-level features
# ---------------------------------------------------------------------------
V2_REQUIRED_COLS: list[str] = [
    "std_proc_cost_pct", "iqr_proc_cost_pct", "std_txn_amount",
    "median_txn_amount", "n_unique_cost_types", "median_proc_cost_pct",
]

COST_TYPE_COLS: list[str] = [f"cost_type_{i}_pct" for i in range(1, 62)]

# ---------------------------------------------------------------------------
# Reference database (same schema as KNN Quote Service Production)
#   DB_CONNECTION_STRING  — SQLAlchemy URL for an external DB (preferred)
#   TRANSACTIONS_DB_PATH  — path to a local SQLite file (fallback)
# Tables required: transactions, cost_type_ref
# ---------------------------------------------------------------------------
DB_CONNECTION_STRING: str = os.getenv("DB_CONNECTION_STRING", "").strip()
TRANSACTIONS_DB_PATH: str = os.getenv(
    "TRANSACTIONS_AND_COST_TYPE_DB_PATH", ""
).strip()
