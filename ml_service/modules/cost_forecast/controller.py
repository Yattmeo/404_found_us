from __future__ import annotations

from .models import CostForecastRequest
from .service import get_cost_forecast


def run_cost_forecast(payload: CostForecastRequest) -> dict:
    return get_cost_forecast(payload).model_dump()
