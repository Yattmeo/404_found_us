"""
Controller for the embedded M9 v2 cost forecast module.

Calls the inference engine directly — no separate container needed.
"""
from __future__ import annotations

import logging

from .models import CostForecastRequest
from .service import get_m9_health, get_m9_monthly_cost_forecast

logger = logging.getLogger(__name__)


async def run_cost_forecast(payload: CostForecastRequest) -> dict:
    """Run M9 v2 inference directly (no HTTP call)."""
    logger.info("Running embedded M9 cost forecast for MCC %s", payload.mcc)
    return get_m9_monthly_cost_forecast(payload)


async def get_cost_forecast_health() -> dict:
    """Return artifact status (no HTTP call)."""
    return get_m9_health()
