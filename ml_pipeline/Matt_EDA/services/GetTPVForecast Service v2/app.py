"""
app.py — FastAPI entry point for GetTPVForecast Service (v2).

Endpoints
---------
GET  /health            Liveness + artifact status
POST /GetTPVForecast    Run TPV forecast
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from config import DB_CONNECTION_STRING, SUPPORTED_MCCS, TRANSACTIONS_DB_PATH
from models import TPVForecastRequest, TPVForecastResponse
from repository import MerchantRepository, SQLAlchemyMerchantRepository, SQLiteMerchantRepository
from service import _ARTIFACT_CACHE, _init_cache, get_tpv_forecast, set_repository, start_artifact_watcher


def _build_repository() -> MerchantRepository:
    if DB_CONNECTION_STRING:
        return SQLAlchemyMerchantRepository(connection_string=DB_CONNECTION_STRING)
    if TRANSACTIONS_DB_PATH:
        return SQLiteMerchantRepository(db_path=Path(TRANSACTIONS_DB_PATH))
    raise RuntimeError(
        "No database configured. Set DB_CONNECTION_STRING (SQLAlchemy URL) "
        "or TRANSACTIONS_AND_COST_TYPE_DB_PATH for a local SQLite file."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    repo = _build_repository()
    set_repository(repo)
    _init_cache()
    if not _ARTIFACT_CACHE:
        raise RuntimeError(
            "No artifact bundles loaded at startup. Run train.py first."
        )
    start_artifact_watcher()
    yield


app = FastAPI(
    title="GetTPVForecast Service",
    version="1.0.0",
    description=(
        "Monthly merchant total-processing-value forecast using "
        "dollar-weighted HuberRegressor in log-space with dollar-space "
        "split-conformal prediction intervals. "
        "Supports variable context lengths {1, 3, 6}."
    ),
    lifespan=lifespan,
)


@app.get("/health", summary="Liveness + artifact status")
def health() -> dict[str, Any]:
    loaded: list[dict[str, Any]] = []
    for (mcc, ctx_len), bundle in _ARTIFACT_CACHE.items():
        loaded.append({
            "mcc": mcc,
            "ctx_len": ctx_len,
            "trained_at": bundle.trained_at,
            "strat_enabled": bundle.strat_enabled,
            "strat_scheme": bundle.strat_scheme,
        })
    return {
        "status": "ok",
        "supported_mccs": SUPPORTED_MCCS,
        "loaded_bundles": loaded,
    }


@app.post(
    "/GetTPVForecast",
    response_model=TPVForecastResponse,
    summary="Run TPV forecast",
)
def forecast(req: TPVForecastRequest) -> TPVForecastResponse:
    if req.mcc not in SUPPORTED_MCCS:
        raise HTTPException(
            status_code=422,
            detail=f"MCC {req.mcc} is not supported. Supported MCCs: {SUPPORTED_MCCS}.",
        )
    try:
        return get_tpv_forecast(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8093, reload=True)
