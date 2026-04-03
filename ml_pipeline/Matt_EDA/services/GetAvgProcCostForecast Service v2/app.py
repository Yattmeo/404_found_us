"""
app.py — FastAPI entry point for GetM9MonthlyCostForecast Service (v2).

Endpoints
---------
GET  /health                        Liveness + artifact status
POST /GetM9MonthlyCostForecast      Run M9 v2 monthly cost forecast
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from config import SUPPORTED_MCCS
from models import M9ForecastRequest, M9ForecastResponse
from service import _ARTIFACT_CACHE, _init_cache, get_monthly_cost_forecast, start_artifact_watcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load artifacts synchronously at startup; fail hard if none exist."""
    _init_cache()
    if not _ARTIFACT_CACHE:
        raise RuntimeError(
            "No artifact bundles loaded at startup. Run train.py first."
        )
    start_artifact_watcher()
    yield


app = FastAPI(
    title="GetM9MonthlyCostForecast Service",
    version="2.0.0",
    description=(
        "Monthly merchant processing-cost forecast using the M9 v2 pipeline "
        "(kNN pool mean + HuberRegressor + GBR risk-stratified split-conformal intervals). "
        "Supports variable context lengths {1, 3, 6}."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@app.get("/health", summary="Liveness + artifact status")
def health() -> dict[str, Any]:
    loaded: list[dict[str, Any]] = []
    for (mcc, ctx_len), bundle in _ARTIFACT_CACHE.items():
        loaded.append(
            {
                "mcc": mcc,
                "ctx_len": ctx_len,
                "trained_at": bundle.trained_at,
                "strat_enabled": bundle.strat_enabled,
                "strat_scheme": bundle.strat_scheme,
            }
        )
    return {
        "status": "ok",
        "supported_mccs": SUPPORTED_MCCS,
        "loaded_bundles": loaded,
    }


# ---------------------------------------------------------------------------
# Forecast endpoint
# ---------------------------------------------------------------------------

@app.post(
    "/GetM9MonthlyCostForecast",
    response_model=M9ForecastResponse,
    summary="Run M9 v2 monthly cost forecast",
)
def forecast(req: M9ForecastRequest) -> M9ForecastResponse:
    if req.mcc not in SUPPORTED_MCCS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"MCC {req.mcc} is not supported. "
                f"Supported MCCs: {SUPPORTED_MCCS}."
            ),
        )
    try:
        return get_monthly_cost_forecast(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8092, reload=False)
