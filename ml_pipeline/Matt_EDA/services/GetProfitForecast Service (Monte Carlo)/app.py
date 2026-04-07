"""
app.py — FastAPI entry point for GetProfitForecast Service.

Pure simulation service: accepts pre-computed TPV and AvgProcCost forecast
outputs, then runs Monte Carlo simulation to produce profit analysis.

Endpoints
---------
GET  /health              Liveness check
POST /GetProfitForecast   Run profit forecast
"""

from typing import Any

from fastapi import FastAPI, HTTPException

from config import SERVICE_PORT
from models import ProfitForecastRequest, ProfitForecastResponse
from service import get_profit_forecast


app = FastAPI(
    title="GetProfitForecast Service",
    version="1.0.0",
    description=(
        "Profit-analysis simulation service. Accepts pre-computed outputs "
        "from the TPV and AvgProcCost forecast services, then runs an "
        "independent Monte Carlo simulation to derive probability of profit, "
        "profit CI, and break-even fee rate."
    ),
)


@app.get("/health", summary="Liveness check")
def health() -> dict[str, Any]:
    return {"status": "ok"}


@app.post(
    "/GetProfitForecast",
    response_model=ProfitForecastResponse,
    summary="Run profit forecast via Monte Carlo",
)
def forecast(req: ProfitForecastRequest) -> ProfitForecastResponse:
    try:
        return get_profit_forecast(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=SERVICE_PORT, reload=True)
