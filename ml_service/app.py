"""
ML Microservice — FastAPI entry point.

Engines exposed under /ml/:
  POST /ml/process          ← called automatically by backend (BackgroundTask)

Individual engine endpoints (for direct testing / future use):
  POST /ml/rate-optimisation
  POST /ml/tpv-prediction
  POST /ml/cluster-generation
  POST /ml/cluster-assignment
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (including pgvector ones) on startup
    init_db()
    yield


app = FastAPI(
    title="ML Microservice",
    version="0.1.0",
    description=(
        "Handles Rate Optimisation, TPV Prediction, "
        "Cluster Generation, and Cluster Assignment for the 404_Found_Us platform."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
