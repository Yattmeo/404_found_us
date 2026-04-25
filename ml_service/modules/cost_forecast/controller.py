"""
Controller for the embedded processing-cost forecast module.

Calls the inference engine directly — no separate container needed.
"""
from __future__ import annotations

import logging

from .models import CostForecastRequest
from .service import get_proc_cost_health, get_proc_cost_monthly_forecast

logger = logging.getLogger(__name__)


async def run_cost_forecast(payload: CostForecastRequest) -> dict:
    """Run processing-cost inference directly (no HTTP call)."""
    logger.info("Running embedded processing-cost forecast for MCC %s", payload.mcc)
    return get_proc_cost_monthly_forecast(payload)


async def get_cost_forecast_health() -> dict:
    """Return artifact status (no HTTP call)."""
    return get_proc_cost_health()
