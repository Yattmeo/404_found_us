"""Controller for the profit forecast module."""
from .models import ProfitForecastRequest, ProfitForecastResponse
from .service import run_profit_forecast


async def run_profit_forecast_async(req: ProfitForecastRequest) -> ProfitForecastResponse:
    return run_profit_forecast(req)
