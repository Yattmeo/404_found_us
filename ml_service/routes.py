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
import math
from collections import defaultdict
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from modules.cost_forecast.controller import get_cost_forecast_health, run_cost_forecast
from modules.cost_forecast.models import CostForecastRequest, ContextMonth
from modules.knn_rate_quote.controller import run_get_composite_merchant, run_get_quote, run_knn_rate_quote
from modules.knn_rate_quote.schemas import CompositeMerchantRequest, QuoteRequest
from modules.profit_forecast.controller import run_profit_forecast
from modules.profit_forecast.models import ProfitForecastRequest
from modules.rate_optimisation.controller import run_rate_optimisation
from modules.tpv_forecast.controller import run_tpv_forecast
from modules.tpv_forecast.models import TPVForecastRequest
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


@router.get("/cost-forecast/health", tags=["Cost Forecast Service (M9 v2)"])
async def cost_forecast_health_endpoint():
    """Health check for the M9 v2 cost forecast container."""
    try:
        return await get_cost_forecast_health()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"M9 service unreachable: {exc}")


# ── Weekly → Monthly translation for legacy pipeline callers ──────────────────

def _weekly_features_to_m9_request(body: dict) -> CostForecastRequest:
    """
    Convert old pipeline format (composite_weekly_features + onboarding rows)
    to an M9 v2 CostForecastRequest.

    The backend's MerchantQuoteService.run_ml_forecast_pipeline still sends
    the legacy SARIMA-era payload shape.  This function bridges the gap so
    the M9 container can serve those requests transparently.
    """
    weekly_features = body.get("composite_weekly_features", [])
    mcc = int(body.get("mcc", 5411))

    # Group weekly rows into (year, month) buckets
    monthly_buckets: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for wf in weekly_features:
        year = int(wf["calendar_year"])
        week = int(wf["week_of_year"])
        # Approximate calendar month from ISO week
        month = min(12, max(1, math.ceil(week * 7 / 30.44)))
        monthly_buckets[(year, month)].append(wf)

    context_months: list[ContextMonth] = []
    for (year, month), weeks in sorted(monthly_buckets.items()):
        n = len(weeks)
        avg_cost = sum(w["weekly_avg_txn_cost_pct_mean"] for w in weeks) / n
        # Root-mean-square of weekly stdevs → monthly stdev proxy
        std_cost = (sum(w.get("weekly_avg_txn_cost_pct_stdev", 0.0) ** 2 for w in weeks) / n) ** 0.5
        avg_txn_value = sum(w.get("weekly_avg_txn_value_mean", 0.0) for w in weeks) / n
        std_txn_amount = (sum(w.get("weekly_avg_txn_value_stdev", 0.0) ** 2 for w in weeks) / n) ** 0.5
        txn_count = max(1, int(sum(w.get("weekly_txn_count_mean", 1.0) for w in weeks)))

        # Aggregate cost-type percentages across weeks
        pct_ct: dict[str, list[float]] = defaultdict(list)
        for w in weeks:
            for k, v in (w.get("pct_ct_means") or {}).items():
                pct_ct[k].append(float(v))
        cost_type_pcts = {k: sum(v) / len(v) for k, v in pct_ct.items()} if pct_ct else None

        context_months.append(ContextMonth(
            year=year,
            month=month,
            avg_proc_cost_pct=avg_cost,
            std_proc_cost_pct=std_cost,
            median_proc_cost_pct=avg_cost,  # best approximation from weekly means
            transaction_count=txn_count,
            avg_transaction_value=avg_txn_value,
            std_txn_amount=std_txn_amount,
            cost_type_pcts=cost_type_pcts,
        ))

    # Limit to supported context lengths (keep most recent)
    if len(context_months) > 6:
        context_months = context_months[-6:]

    # Use real knn_pool_mean from TPV forecast when available; otherwise
    # fall back to the merchant's own context average (degraded mode).
    knn_pool_mean = body.get("knn_pool_mean")
    flat_pool_mean = body.get("flat_pool_mean")
    peer_ids = body.get("peer_merchant_ids")

    if knn_pool_mean is None or flat_pool_mean is None:
        # Degraded: derive pool means from the context itself (best available proxy)
        all_costs = [cm.avg_proc_cost_pct for cm in context_months]
        fallback_mean = sum(all_costs) / len(all_costs) if all_costs else 0.0
        if knn_pool_mean is None:
            knn_pool_mean = fallback_mean
        if flat_pool_mean is None:
            flat_pool_mean = fallback_mean

    return CostForecastRequest(
        context_months=context_months,
        pool_mean_at_context_end=flat_pool_mean,
        knn_pool_mean_at_context_end=knn_pool_mean,
        peer_merchant_ids=peer_ids,
        mcc=mcc,
    )


def _m9_response_to_legacy(m9_resp: dict) -> dict:
    """
    Translate M9 v2 monthly response → 12 weekly legacy format.

    Each of the 3 monthly forecasts is expanded into 4 weekly points
    via linear interpolation, matching the old SARIMA 12-week horizon.
    """
    monthly = sorted(
        m9_resp.get("forecast", []),
        key=lambda fm: fm.get("month_index", 0),
    )

    weekly_forecast = []
    week_idx = 1
    for i, fm in enumerate(monthly):
        mid = fm.get("proc_cost_pct_mid", 0.0)
        lo  = fm.get("proc_cost_pct_ci_lower", 0.0)
        hi  = fm.get("proc_cost_pct_ci_upper", 0.0)

        if i + 1 < len(monthly):
            n_mid = monthly[i + 1]["proc_cost_pct_mid"]
            n_lo  = monthly[i + 1]["proc_cost_pct_ci_lower"]
            n_hi  = monthly[i + 1]["proc_cost_pct_ci_upper"]
        else:
            n_mid, n_lo, n_hi = mid, lo, hi

        for w in range(4):
            t = w / 4.0
            weekly_forecast.append({
                "forecast_week_index": week_idx,
                "proc_cost_pct_mid":      mid + t * (n_mid - mid),
                "proc_cost_pct_ci_lower": lo  + t * (n_lo  - lo),
                "proc_cost_pct_ci_upper": hi  + t * (n_hi  - hi),
            })
            week_idx += 1

    return {
        "forecast": weekly_forecast,
        "conformal_metadata": m9_resp.get("conformal_metadata"),
        "process_metadata":   m9_resp.get("process_metadata"),
    }


def _cost_forecast_fallback_from_weekly(body: dict) -> dict | None:
    """
    Simple fallback cost forecast derived from the backend's base cost rate
    (from cost-structure JSONs) when M9 v2 has no trained artifacts.

    If a base_cost_rate is supplied by the caller it is used directly,
    giving a realistic ~1-3 % cost percentage.  Otherwise falls back to
    the composite weekly features' avg txn cost ratio (which may be
    inflated when the underlying proc_cost data includes aggregated fee
    layers).
    """
    weekly_features = body.get("composite_weekly_features", [])
    if not weekly_features:
        return None

    # Prefer the authoritative base_cost_rate from the backend's
    # cost-structure JSON calculation (a decimal, e.g. 0.0141 = 1.41%).
    base_cost_rate = body.get("base_cost_rate")

    if base_cost_rate is not None and base_cost_rate > 0:
        avg_cost = float(base_cost_rate)
        # Use a small uncertainty band (±15 % of the rate) for CI.
        avg_stdev = avg_cost * 0.15
    else:
        # Fallback: derive from composite weekly features.
        recent = sorted(
            weekly_features,
            key=lambda w: (w.get("calendar_year", 0), w.get("week_of_year", 0)),
        )[-12:]

        cost_means = [
            w.get("weekly_avg_txn_cost_pct_mean", 0.0)
            for w in recent if w.get("weekly_avg_txn_cost_pct_mean")
        ]
        cost_stdevs = [
            w.get("weekly_avg_txn_cost_pct_stdev", 0.0)
            for w in recent if w.get("weekly_avg_txn_cost_pct_stdev")
        ]
        if not cost_means:
            return None

        avg_cost = sum(cost_means) / len(cost_means)
        avg_stdev = (sum(cost_stdevs) / len(cost_stdevs)) if cost_stdevs else avg_cost * 0.1

    # Add realistic time variation: slight upward drift with widening
    # confidence intervals, mimicking increasing uncertainty further out.
    drift_factors = [0.97, 1.00, 1.03]
    ci_widening   = [0.85, 1.00, 1.20]

    forecast = []
    week_idx = 1
    for i in range(3):
        d  = drift_factors[i]
        cw = ci_widening[i]
        mid  = avg_cost * d
        half = avg_stdev * cw

        if i + 1 < 3:
            n_mid  = avg_cost * drift_factors[i + 1]
            n_half = avg_stdev * ci_widening[i + 1]
        else:
            n_mid, n_half = mid, half

        for wk in range(4):
            t = wk / 4.0
            interp_mid  = mid  + t * (n_mid  - mid)
            interp_half = half + t * (n_half - half)
            forecast.append({
                "forecast_week_index": week_idx,
                "proc_cost_pct_mid":      round(interp_mid, 6),
                "proc_cost_pct_ci_lower": round(max(0.0, interp_mid - interp_half), 6),
                "proc_cost_pct_ci_upper": round(interp_mid + interp_half, 6),
            })
            week_idx += 1

    return {
        "forecast": forecast,
        "conformal_metadata": None,
        "process_metadata": {"source": "base_cost_rate_fallback" if base_cost_rate else "knn_neighbour_mean_fallback"},
    }


@router.post("/GetCostForecast", tags=["Cost Forecast Service (M9 v2)"])
async def get_cost_forecast_endpoint(request: Request):
    """
    Monthly processing-cost forecast (M9 v2).

    Accepts BOTH:
      • M9 v2 native format  (context_months, pool_mean_at_context_end, …)
      • Legacy pipeline format (composite_weekly_features, onboarding_merchant_txn_df, mcc)

    When the legacy format is detected the weekly features are aggregated
    into monthly buckets and forwarded to the M9 container.  The response
    is then re-mapped to the legacy field names so the backend routes work
    without changes.

    Falls back to a simple KNN-neighbour-mean estimate when M9 has no
    trained artifacts (degraded mode).

    ── WHERE TO EDIT: ml_pipeline/Matt_EDA/services/GetAvgProcCostForecast Service v2/
    """
    body = await request.json()
    is_legacy = "composite_weekly_features" in body

    try:
        if is_legacy:
            m9_request = _weekly_features_to_m9_request(body)
        else:
            m9_request = CostForecastRequest(**body)

        m9_result = await run_cost_forecast(m9_request)

        # Return monthly forecast directly (3 months, no weekly expansion)
        return m9_result
    except Exception as exc:
        # If M9 is in degraded mode, fall back to KNN-neighbour-mean cost estimate
        if is_legacy:
            fallback = _cost_forecast_fallback_from_weekly(body)
            if fallback is not None:
                return fallback
        raise HTTPException(status_code=400, detail=str(exc))


# ── Weekly → Monthly translation for TPV Huber forecast ───────────────────────

_WEEKS_PER_MONTH = 52.0 / 12.0  # ≈ 4.333


def _weekly_features_to_tpv_request(body: dict) -> dict:
    """
    Convert legacy weekly-features payload → TpvForecastRequest (monthly context).

    Groups the composite_weekly_features rows into calendar-month buckets
    (same approximation used by the M9 converter) and computes:
      • total_payment_volume  = mean(weekly TPV) × 4.33  [monthly dollar estimate]
      • transaction_count     = round(mean(weekly txn count) × 4.33)
      • avg_transaction_value = mean(weekly avg txn value)
      • std_txn_amount        = mean(weekly avg txn value stdev)

    Pool log-mean is derived from the context itself (no runtime KNN lookup).
    """
    weekly_features = body.get("composite_weekly_features", [])
    mcc = int(body.get("mcc", 5411))

    monthly_buckets: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for wf in weekly_features:
        year = int(wf["calendar_year"])
        week = int(wf["week_of_year"])
        month = min(12, max(1, math.ceil(week * 7 / 30.44)))
        monthly_buckets[(year, month)].append(wf)

    context_months: list[TpvContextMonth] = []
    for (year, month), weeks in sorted(monthly_buckets.items()):
        n = len(weeks)
        mean_weekly_tpv = sum(w.get("weekly_total_proc_value_mean", 0.0) for w in weeks) / n
        monthly_tpv = mean_weekly_tpv * _WEEKS_PER_MONTH

        mean_weekly_tc = sum(w.get("weekly_txn_count_mean", 1.0) for w in weeks) / n
        monthly_tc = max(1, round(mean_weekly_tc * _WEEKS_PER_MONTH))

        avg_txn_val = sum(w.get("weekly_avg_txn_value_mean", 0.0) for w in weeks) / n
        std_txn = (sum(w.get("weekly_avg_txn_value_stdev", 0.0) ** 2 for w in weeks) / n) ** 0.5

        context_months.append({
            "year": year,
            "month": month,
            "total_payment_volume": monthly_tpv,
            "transaction_count": monthly_tc,
            "avg_transaction_value": avg_txn_val,
            "std_txn_amount": std_txn,
        })

    if len(context_months) > 6:
        context_months = context_months[-6:]

    # Return onboarding_merchant_txn_df compatible with the new TPVForecastRequest
    # by flattening the monthly buckets into synthetic transaction rows.
    synthetic_rows = []
    for cm in context_months:
        for _ in range(cm["transaction_count"]):
            synthetic_rows.append({
                "transaction_date": f"{cm['year']}-{cm['month']:02d}-15",
                "amount": round(cm["avg_transaction_value"], 2),
            })

    return {"onboarding_merchant_txn_df": synthetic_rows, "mcc": mcc}


@router.post("/GetTPVForecast", tags=["TPV Forecast Service (v2)"])
async def get_tpv_forecast_endpoint(payload: TPVForecastRequest):
    """
    Monthly TPV forecast with conformal prediction intervals.

    Accepts raw transaction records and produces a 1–3 month forecast.
    When trained artifacts are available, uses HuberRegressor in log-space
    with dollar-space conformal intervals. Falls back to simple
    extrapolation when artifacts are not yet trained.
    """
    try:
        return run_tpv_forecast(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/GetVolumeForecast", tags=["Volume Forecast Service"])
async def get_volume_forecast_endpoint(payload: VolumeForecastRequest):
    try:
        return run_volume_forecast(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/GetProfitForecast", tags=["Profit Forecast Service (Monte Carlo)"])
async def get_profit_forecast_endpoint(payload: ProfitForecastRequest):
    """
    Monte Carlo profit simulation.

    Accepts pre-computed TPV and cost forecast outputs, runs independent
    Monte Carlo sampling, and returns per-month profit distributions
    with summary statistics (break-even rate, suggested fee, etc.).
    """
    try:
        return run_profit_forecast(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
