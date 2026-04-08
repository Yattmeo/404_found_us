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

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from modules.m9_forecast.service import init_m9_cache, start_m9_watcher
from modules.tpv_forecast.service import init_tpv_cache, start_tpv_watcher
from routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    init_db()
    # Load M9 cost forecast artifacts and start hot-reload watcher
    init_m9_cache()
    start_m9_watcher()
    # Load TPV Huber forecast artifacts and start hot-reload watcher
    init_tpv_cache()
    start_tpv_watcher()
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
