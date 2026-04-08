"""
Controller for the M9 v2 cost forecast module.

Delegates to the in-process m9_forecast module which loads artifacts
from ml_service/artifacts/m9/.
"""
from __future__ import annotations

import logging

from ..m9_forecast.models import M9ForecastRequest as M9NativeRequest
from ..m9_forecast.service import get_m9_health, run_m9_forecast
from .models import CostForecastRequest

logger = logging.getLogger(__name__)


async def run_cost_forecast(payload: CostForecastRequest) -> dict:
    """Run cost forecast via in-process M9 module."""
    logger.info("Running cost forecast in-process via m9_forecast module")
    native = M9NativeRequest(
        context_months=payload.context_months,
        pool_mean_at_context_end=payload.pool_mean_at_context_end,
        knn_pool_mean_at_context_end=payload.knn_pool_mean_at_context_end,
        peer_merchant_ids=payload.peer_merchant_ids,
        mcc=payload.mcc,
        horizon_months=payload.horizon_months,
        confidence_interval=payload.confidence_interval,
    )
    return run_m9_forecast(native)


async def get_cost_forecast_health() -> dict:
    """Health check for the in-process M9 forecast module."""
    return get_m9_health()
