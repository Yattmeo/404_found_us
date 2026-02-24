"""
ML Microservice routes.

── API ENDPOINTS ─────────────────────────────────────────────────────────────
POST /ml/process
    Primary entry point. Called automatically by the backend after every
    /calculations/transaction-costs request. Runs all 4 engines in sequence.
    ── WHERE TO EDIT: this file, process() function below.

POST /ml/rate-optimisation
POST /ml/tpv-prediction
POST /ml/cluster-generation
POST /ml/cluster-assignment
    Individual engine endpoints. Useful for testing engines in isolation.
    ── WHERE TO EDIT: each engine's controller.py (see modules/).
"""
from __future__ import annotations

import io
import logging
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from modules.cluster_assignment.controller import run_cluster_assignment
from modules.cluster_generation.controller import run_cluster_generation
from modules.rate_optimisation.controller import run_rate_optimisation
from modules.tpv_prediction.controller import run_tpv_prediction

router = APIRouter(prefix="/ml")
logger = logging.getLogger(__name__)


# ── Shared CSV parser ─────────────────────────────────────────────────────────

def _parse_csv(upload: UploadFile) -> pd.DataFrame:
    contents = upload.file.read()
    return pd.read_csv(io.BytesIO(contents))


# ── Primary orchestration endpoint ───────────────────────────────────────────

@router.post("/process", tags=["ML Orchestration"])
async def process(
    # ── Inputs from backend CostCalculationService ───────────────────────────
    enriched_csv:           UploadFile       = File(...),
    mcc:                    int              = Form(...),
    total_cost:             float            = Form(...),
    total_payment_volume:   float            = Form(...),
    effective_rate:         float            = Form(...),
    slope:                  Optional[str]    = Form(None),
    cost_variance:          Optional[str]    = Form(None),
    db:                     Session          = Depends(get_db),
):
    """
    Orchestrates all 4 ML engines in sequence:
      1. Rate Optimisation Engine
      2. TPV Prediction Engine
      3. Cluster Generation Engine
      4. Cluster Assignment Engine

    Inputs (all outputs from /calculations/transaction-costs):
      • enriched_csv          — CSV file with original columns + cost columns
      • mcc                   — Merchant Category Code
      • total_cost            — sum of all card + network fees
      • total_payment_volume  — sum of all transaction amounts
      • effective_rate        — totalCost / totalPaymentVolume × 100
      • slope                 — linear regression slope of weekly costs
      • cost_variance         — weekly cost variance

    ── WHERE TO EDIT ─────────────────────────────────────────────────────────
    Individual engine logic lives in ml_service/modules/<engine>/service.py.
    This function wires them together — change the call order here if needed.
    """
    # Parse slope / cost_variance (sent as strings from Form, may be empty)
    _slope         = float(slope)         if slope         else None
    _cost_variance = float(cost_variance) if cost_variance else None

    try:
        df = _parse_csv(enriched_csv)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse enriched CSV: {exc}")

    metrics = dict(
        mcc=mcc,
        total_cost=total_cost,
        total_payment_volume=total_payment_volume,
        effective_rate=effective_rate,
        slope=_slope,
        cost_variance=_cost_variance,
    )

    logger.info("ML /process received — MCC %s, %d rows", mcc, len(df))

    # 1. Rate Optimisation ───────────────────────────────────────────────────
    rate_result = run_rate_optimisation(df=df, metrics=metrics, db=db)

    # 2. TPV Prediction ──────────────────────────────────────────────────────
    tpv_result = run_tpv_prediction(df=df, metrics=metrics, db=db)

    # 3. Cluster Generation ──────────────────────────────────────────────────
    cluster_gen_result = run_cluster_generation(df=df, metrics=metrics, db=db)

    # 4. Cluster Assignment ──────────────────────────────────────────────────
    cluster_assign_result = run_cluster_assignment(df=df, metrics=metrics, db=db)

    return {
        "status":           "success",
        "mcc":              mcc,
        "rate_optimisation":  rate_result,
        "tpv_prediction":     tpv_result,
        "cluster_generation": cluster_gen_result,
        "cluster_assignment": cluster_assign_result,
    }


# ── Individual engine endpoints (direct / testing) ────────────────────────────

@router.post("/rate-optimisation", tags=["Rate Optimisation Engine"])
async def rate_optimisation_endpoint(
    enriched_csv:           UploadFile    = File(...),
    mcc:                    int           = Form(...),
    total_cost:             float         = Form(...),
    total_payment_volume:   float         = Form(...),
    effective_rate:         float         = Form(...),
    slope:                  Optional[str] = Form(None),
    cost_variance:          Optional[str] = Form(None),
    db:                     Session       = Depends(get_db),
):
    """
    Rate Optimisation Engine — standalone endpoint.
    ── WHERE TO EDIT: ml_service/modules/rate_optimisation/service.py
    """
    df = _parse_csv(enriched_csv)
    metrics = dict(
        mcc=mcc, total_cost=total_cost, total_payment_volume=total_payment_volume,
        effective_rate=effective_rate,
        slope=float(slope) if slope else None,
        cost_variance=float(cost_variance) if cost_variance else None,
    )
    return run_rate_optimisation(df=df, metrics=metrics, db=db)


@router.post("/tpv-prediction", tags=["TPV Prediction Engine"])
async def tpv_prediction_endpoint(
    enriched_csv:           UploadFile    = File(...),
    mcc:                    int           = Form(...),
    total_cost:             float         = Form(...),
    total_payment_volume:   float         = Form(...),
    effective_rate:         float         = Form(...),
    slope:                  Optional[str] = Form(None),
    cost_variance:          Optional[str] = Form(None),
    db:                     Session       = Depends(get_db),
):
    """
    TPV Prediction Engine — standalone endpoint.
    ── WHERE TO EDIT: ml_service/modules/tpv_prediction/service.py
    """
    df = _parse_csv(enriched_csv)
    metrics = dict(
        mcc=mcc, total_cost=total_cost, total_payment_volume=total_payment_volume,
        effective_rate=effective_rate,
        slope=float(slope) if slope else None,
        cost_variance=float(cost_variance) if cost_variance else None,
    )
    return run_tpv_prediction(df=df, metrics=metrics, db=db)


@router.post("/cluster-generation", tags=["Cluster Generation Engine"])
async def cluster_generation_endpoint(
    enriched_csv:           UploadFile    = File(...),
    mcc:                    int           = Form(...),
    total_cost:             float         = Form(...),
    total_payment_volume:   float         = Form(...),
    effective_rate:         float         = Form(...),
    slope:                  Optional[str] = Form(None),
    cost_variance:          Optional[str] = Form(None),
    db:                     Session       = Depends(get_db),
):
    """
    Cluster Generation Engine — standalone endpoint.
    ── WHERE TO EDIT: ml_service/modules/cluster_generation/service.py
    """
    df = _parse_csv(enriched_csv)
    metrics = dict(
        mcc=mcc, total_cost=total_cost, total_payment_volume=total_payment_volume,
        effective_rate=effective_rate,
        slope=float(slope) if slope else None,
        cost_variance=float(cost_variance) if cost_variance else None,
    )
    return run_cluster_generation(df=df, metrics=metrics, db=db)


@router.post("/cluster-assignment", tags=["Cluster Assignment Engine"])
async def cluster_assignment_endpoint(
    enriched_csv:           UploadFile    = File(...),
    mcc:                    int           = Form(...),
    total_cost:             float         = Form(...),
    total_payment_volume:   float         = Form(...),
    effective_rate:         float         = Form(...),
    slope:                  Optional[str] = Form(None),
    cost_variance:          Optional[str] = Form(None),
    db:                     Session       = Depends(get_db),
):
    """
    Cluster Assignment Engine — standalone endpoint.
    ── WHERE TO EDIT: ml_service/modules/cluster_assignment/service.py
    """
    df = _parse_csv(enriched_csv)
    metrics = dict(
        mcc=mcc, total_cost=total_cost, total_payment_volume=total_payment_volume,
        effective_rate=effective_rate,
        slope=float(slope) if slope else None,
        cost_variance=float(cost_variance) if cost_variance else None,
    )
    return run_cluster_assignment(df=df, metrics=metrics, db=db)
