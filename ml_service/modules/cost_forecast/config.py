"""
Configuration for the M9 v2 cost forecast module.

The M9 service runs as a standalone container; this config holds
the URL and supported parameters for the proxy layer.
"""
from __future__ import annotations

import os

# URL of the standalone M9 forecast container (set via docker-compose env)
M9_FORECAST_SERVICE_URL: str = os.getenv(
    "M9_FORECAST_SERVICE_URL", "http://m9-forecast-service:8092"
)

# Proxy timeout (seconds)
M9_PROXY_TIMEOUT: float = 30.0

# Supported context lengths in the M9 v2 pipeline
SUPPORTED_CONTEXT_LENS: list[int] = [1, 3, 6]

# Default forecast horizon (months)
DEFAULT_HORIZON_MONTHS: int = 3

# Default confidence interval for conformal prediction intervals
DEFAULT_CONFIDENCE_INTERVAL: float = 0.90

# Supported MCCs
SUPPORTED_MCCS: list[int] = [5411]
