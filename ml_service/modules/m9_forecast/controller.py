"""
Thin proxy controller for the standalone M9 forecast service container.

The M9 v2 service runs as its own container (m9-forecast-service:8092)
because it needs artifact files and a custom lifespan. This controller
forwards validated requests via httpx.
"""
from __future__ import annotations

import logging
import os

import httpx

from .models import M9ForecastRequest

logger = logging.getLogger(__name__)

M9_SERVICE_URL = os.getenv("M9_FORECAST_SERVICE_URL", "http://m9-forecast-service:8092")
_TIMEOUT = 30.0


async def run_m9_forecast(payload: M9ForecastRequest) -> dict:
    """POST the validated request to the M9 v2 container and return its JSON."""
    url = f"{M9_SERVICE_URL}/GetM9MonthlyCostForecast"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=payload.model_dump())
        resp.raise_for_status()
        return resp.json()


async def get_m9_health() -> dict:
    """GET the health endpoint of the M9 v2 container."""
    url = f"{M9_SERVICE_URL}/health"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
