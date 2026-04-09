"""
ML Microservice — FastAPI entry point.

Engines exposed under /ml/:
  POST /ml/process          ← called automatically by backend (BackgroundTask)

Individual engine endpoints (for direct testing / future use):
  POST /ml/rate-optimisation
  POST /ml/tpv-prediction
  POST /ml/knn-rate-quote
  POST /ml/getQuote
  POST /ml/getCompositeMerchant
  POST /ml/GetCostForecast
  POST /ml/GetVolumeForecast
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    init_db()

    # Initialize M9 cost forecast artifacts (graceful — warns if missing)
    try:
        from modules.cost_forecast.service import initialize as init_m9
        init_m9()
    except Exception as exc:
        logger.warning("[M9Cost] Initialization skipped: %s", exc)

    # Initialize TPV forecast artifacts (graceful — does not crash if missing)
    try:
        from modules.tpv_forecast.service import initialize as init_tpv, set_repository
        from modules.tpv_forecast.repository import SQLAlchemyMerchantRepository

        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://pguser:pgpassword@postgres:5432/mldb",
        )
        repo = SQLAlchemyMerchantRepository(connection_string=db_url)
        set_repository(repo)
        init_tpv()
        print("[TPV] Initialization complete", flush=True)
    except Exception as exc:
        import traceback
        print(f"[TPV] Initialization FAILED: {exc}", flush=True)
        traceback.print_exc()

    yield


app = FastAPI(
    title="ML Microservice",
    version="0.1.0",
    description=(
        "Handles Rate Optimisation, TPV Prediction, "
        "and KNN Rate Quote for the 404_Found_Us platform."
    ),
    lifespan=lifespan,
    # Serve docs under /ml/ so they work through the nginx proxy
    docs_url="/ml/docs",
    redoc_url="/ml/redoc",
    openapi_url="/ml/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
