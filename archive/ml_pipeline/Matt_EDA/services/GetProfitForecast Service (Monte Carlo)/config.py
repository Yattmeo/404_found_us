"""config.py - Configuration for the GetProfitForecast service."""

import os

# ── Monte Carlo defaults ─────────────────────────────────────────────────────
DEFAULT_N_SIMULATIONS: int = int(os.getenv("DEFAULT_N_SIMULATIONS", "10000"))
DEFAULT_CONFIDENCE_INTERVAL: float = 0.90
HORIZON_LEN: int = 3

# ── Service ───────────────────────────────────────────────────────────────────
SERVICE_PORT: int = int(os.getenv("SERVICE_PORT", "8094"))
