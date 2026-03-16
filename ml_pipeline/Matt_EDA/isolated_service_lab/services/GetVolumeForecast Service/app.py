from __future__ import annotations

from fastapi import FastAPI, HTTPException

from models import VolumeForecastRequest, VolumeForecastResponse
from service import get_volume_forecast

app = FastAPI(title="GetVolumeForecast API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/GetVolumeForecast", response_model=VolumeForecastResponse)
def volume_forecast(req: VolumeForecastRequest) -> VolumeForecastResponse:
    try:
        return get_volume_forecast(req)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
