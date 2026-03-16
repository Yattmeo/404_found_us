from __future__ import annotations

from fastapi import FastAPI, HTTPException

from models import CostForecastRequest, CostForecastResponse
from service import get_cost_forecast

app = FastAPI(title="GetCostForecast API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/GetCostForecast", response_model=CostForecastResponse)
def cost_forecast(req: CostForecastRequest) -> CostForecastResponse:
    try:
        return get_cost_forecast(req)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
