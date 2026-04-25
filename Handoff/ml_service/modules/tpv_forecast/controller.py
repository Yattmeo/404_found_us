"""Controller for the GetTPVForecast module."""

from __future__ import annotations

from .models import TPVForecastRequest, TPVForecastResponse
from .service import get_tpv_forecast


def run_tpv_forecast(req: TPVForecastRequest) -> dict:
    result: TPVForecastResponse = get_tpv_forecast(req)
    return result.model_dump()
