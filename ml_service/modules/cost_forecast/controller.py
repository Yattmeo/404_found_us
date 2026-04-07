"""
Controller for the M9 v2 cost forecast module.

Proxies requests to the standalone m9-forecast-service container.
Replaces the previous SARIMA-based controller.
"""
from __future__ import annotations

import logging

import httpx

from .config import M9_FORECAST_SERVICE_URL, M9_PROXY_TIMEOUT
from .models import CostForecastRequest

logger = logging.getLogger(__name__)


async def run_cost_forecast(payload: CostForecastRequest) -> dict:
    """POST the validated request to the M9 v2 container and return its JSON."""
    url = f"{M9_FORECAST_SERVICE_URL}/GetM9MonthlyCostForecast"
    logger.info("Proxying cost forecast to M9 service: %s", url)
    async with httpx.AsyncClient(timeout=M9_PROXY_TIMEOUT) as client:
        resp = await client.post(url, json=payload.model_dump())
        resp.raise_for_status()
        return resp.json()


async def get_cost_forecast_health() -> dict:
    """GET the health endpoint of the M9 v2 container."""
    url = f"{M9_FORECAST_SERVICE_URL}/health"
    async with httpx.AsyncClient(timeout=M9_PROXY_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
