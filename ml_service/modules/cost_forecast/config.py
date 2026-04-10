"""
Configuration for the embedded M9 v2 cost forecast module.

All pipeline constants mirror those used at training time so inference
and training always share the same values.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Artifact storage — override via env var for Docker usage
# ---------------------------------------------------------------------------
M9_ARTIFACTS_BASE_PATH: Path = Path(
    os.getenv("M9_ARTIFACTS_BASE_PATH", str(Path(__file__).parent.parent.parent / "artifacts" / "m9"))
)

# ---------------------------------------------------------------------------
# Pipeline constants — must be identical to those used when train.py ran
# ---------------------------------------------------------------------------
SUPPORTED_CONTEXT_LENS: list[int] = [1, 3, 6]
HORIZON_LEN: int = 3
TARGET_COV: float = 0.90
MIN_POOL: int = 10
KNN_K: int = 10
_VOL_EPS: float = 1e-6

# Default forecast horizon (months)
DEFAULT_HORIZON_MONTHS: int = 3

# Default confidence interval for conformal prediction intervals
DEFAULT_CONFIDENCE_INTERVAL: float = 0.90

# Supported MCCs
SUPPORTED_MCCS: list[int] = [4121, 5411, 5499, 5812]

# ---------------------------------------------------------------------------
# Hot-reload
# ---------------------------------------------------------------------------
ARTIFACT_POLL_INTERVAL_S: float = float(
    os.getenv("ARTIFACT_POLL_INTERVAL_S", "60")
)
