"""
ML Microservice routes.

── API ENDPOINTS ─────────────────────────────────────────────────────────────
POST /ml/process
    Primary entry point. Called automatically by the backend after every
    /calculations/transaction-costs request. Runs Rate Optimisation, TPV
    Prediction, and KNN Rate Quote engines in sequence.
    ── WHERE TO EDIT: this file, process() function below.

POST /ml/rate-optimisation
POST /ml/tpv-prediction
POST /ml/knn-rate-quote
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
from modules.cost_forecast.controller import run_cost_forecast
from modules.cost_forecast.models import CostForecastRequest
from modules.knn_rate_quote.controller import run_get_composite_merchant, run_get_quote, run_knn_rate_quote
from modules.knn_rate_quote.schemas import CompositeMerchantRequest, QuoteRequest
from modules.rate_optimisation.controller import run_rate_optimisation
from modules.tpv_prediction.controller import run_tpv_prediction
from modules.volume_forecast.controller import run_volume_forecast
from modules.volume_forecast.models import VolumeForecastRequest

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
    card_type:              Optional[str]    = Form(None),
    monthly_txn_count:      Optional[int]    = Form(None),
    avg_amount:             Optional[float]  = Form(None),
    as_of_date:             Optional[str]    = Form(None),
    db:                     Session          = Depends(get_db),
):
    """
    Orchestrates ML engines in sequence:
      1. Rate Optimisation Engine
      2. TPV Prediction Engine
      3. KNN Rate Quote Engine

    Inputs (all outputs from /calculations/transaction-costs):
      • enriched_csv          — CSV file with original columns + cost columns
      • mcc                   — Merchant Category Code
      • total_cost            — sum of all card + network fees
      • total_payment_volume  — sum of all transaction amounts
      • effective_rate        — totalCost / totalPaymentVolume × 100
      • slope                 — linear regression slope of weekly costs
      • cost_variance         — weekly cost variance
      • card_type             — "visa" | "mastercard" | "both" (KNN)
      • monthly_txn_count     — override monthly transaction count (KNN)
      • avg_amount            — override average transaction amount (KNN)
      • as_of_date            — ISO date string for KNN context end (KNN)

    ── WHERE TO EDIT ─────────────────────────────────────────────────────────
    Individual engine logic lives in ml_service/modules/<engine>/service.py.
    This function wires them together — change the call order here if needed.
    """
    # Parse optional form strings
    _slope         = float(slope)         if slope         else None
    _cost_variance = float(cost_variance) if cost_variance else None
    _as_of_date    = pd.Timestamp(as_of_date).date() if as_of_date else None

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

    # 1. Rate Optimisation
    rate_result = run_rate_optimisation(df=df, metrics=metrics, db=db)

    # 2. TPV Prediction
    tpv_result = run_tpv_prediction(df=df, metrics=metrics, db=db)

    # 3. KNN Rate Quote
    knn_result = run_knn_rate_quote(
        df=df,
        mcc=mcc,
        card_type=card_type,
        monthly_txn_count=monthly_txn_count,
        avg_amount=avg_amount,
        as_of_date=_as_of_date,
    )

    return {
        "status":           "success",
        "mcc":              mcc,
        "rate_optimisation":  rate_result,
        "tpv_prediction":     tpv_result,
        "knn_rate_quote":     knn_result,
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


@router.post("/knn-rate-quote", tags=["KNN Rate Quote Engine"])
async def knn_rate_quote_endpoint(
    mcc:                int              = Form(...),
    card_type:          Optional[str]    = Form(None),
    monthly_txn_count:  Optional[int]    = Form(None),
    avg_amount:         Optional[float]  = Form(None),
    as_of_date:         Optional[str]    = Form(None),
    enriched_csv:       Optional[UploadFile] = File(None),
):
    """
    KNN Rate Quote Engine — standalone endpoint.

    Supply either `enriched_csv` (transaction-level CSV with columns
    transaction_date, amount, cost_type_ID) OR the metrics-only mode by
    providing `monthly_txn_count`, `avg_amount`, and `as_of_date` without a
    CSV file.  Both modes may be combined.

    ── WHERE TO EDIT: ml_service/modules/knn_rate_quote/service.py
    """
    df = _parse_csv(enriched_csv) if enriched_csv is not None else None
    _as_of_date = pd.Timestamp(as_of_date).date() if as_of_date else None
    return run_knn_rate_quote(
        df=df,
        mcc=mcc,
        card_type=card_type,
        monthly_txn_count=monthly_txn_count,
        avg_amount=avg_amount,
        as_of_date=_as_of_date,
    )


@router.post("/getQuote", tags=["KNN Quote Service"])
async def get_quote_endpoint(payload: QuoteRequest):
    try:
        return run_get_quote(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/getCompositeMerchant", tags=["KNN Quote Service"])
async def get_composite_merchant_endpoint(payload: CompositeMerchantRequest):
    try:
        return run_get_composite_merchant(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/GetCostForecast", tags=["Cost Forecast Service"])
async def get_cost_forecast_endpoint(payload: CostForecastRequest):
    try:
        return run_cost_forecast(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/GetVolumeForecast", tags=["Volume Forecast Service"])
async def get_volume_forecast_endpoint(payload: VolumeForecastRequest):
    try:
        return run_volume_forecast(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
