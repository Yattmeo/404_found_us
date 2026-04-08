"""Controller for the GetProfitForecast module."""

from __future__ import annotations

from .models import ProfitForecastRequest, ProfitForecastResponse
from .service import get_profit_forecast


def run_profit_forecast(req: ProfitForecastRequest) -> dict:
    result: ProfitForecastResponse = get_profit_forecast(req)
    return result.model_dump()
