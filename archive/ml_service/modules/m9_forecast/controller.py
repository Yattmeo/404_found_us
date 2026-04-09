"""
M9 forecast controller — in-process artifact-based inference.

Previously a thin httpx proxy to a separate m9-forecast-service container.
Now delegates to the local service module which loads artifacts from
ml_service/artifacts/m9/{mcc}/{ctx_len}/.
"""
from __future__ import annotations

import logging

from .models import M9ForecastRequest
from .service import get_m9_health, init_m9_cache, run_m9_forecast, start_m9_watcher

logger = logging.getLogger(__name__)

__all__ = [
    "run_m9_forecast",
    "get_m9_health",
    "init_m9_cache",
    "start_m9_watcher",
]
