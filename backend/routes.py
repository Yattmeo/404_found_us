"""
API routes — FastAPI version.
Replaces Flask Blueprints with a single APIRouter mounted at /api/v1.
"""
from __future__ import annotations

import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import io
from sqlalchemy.orm import Session

from database import get_db
from models import Transaction, Merchant, CalculationResult, UploadBatch
from schemas import (
    RevenueProjectionRequest,
    RevenueProjectionResponse,
    TransactionResponse,
    MerchantCreate,
    MerchantResponse,
)
from services import DataProcessingService, MerchantFeeCalculationService, MCCService
from modules.merchant_quote.schemas import MerchantQuoteRequest, MerchantQuoteResponse
from modules.merchant_quote.controller import create_merchant_quote
from modules.merchant_quote.service import MerchantQuoteService
from modules.cost_calculation.schemas import CostCalculationResponse
from modules.cost_calculation.controller import run_cost_calculation

router = APIRouter(prefix="/api/v1")

logger = logging.getLogger(__name__)

# URL of the ML microservice — injected via env var in docker-compose
_ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://ml-service:8001")


def _forward_to_ml(
    enriched_csv_bytes: bytes,
    filename: str,
    mcc: int,
    total_cost: float,
    total_payment_volume: float,
    effective_rate: float,
    slope: Optional[float],
    cost_variance: Optional[float],
) -> None:
    """
    Background task: POST enriched CSV + cost metrics to the ML microservice.
    Runs after the HTTP response is already sent to the caller, so any
    ML-service delay or downtime does NOT affect the API response time.
    """
    url = f"{_ML_SERVICE_URL}/ml/process"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url,
                files={"enriched_csv": (filename, enriched_csv_bytes, "text/csv")},
                data={
                    "mcc":                  str(mcc),
                    "total_cost":           str(total_cost),
                    "total_payment_volume": str(total_payment_volume),
                    "effective_rate":       str(effective_rate),
                    "slope":                str(slope)  if slope          is not None else "",
                    "cost_variance":        str(cost_variance) if cost_variance is not None else "",
                },
            )
        logger.info("ML service responded %s for %s", response.status_code, filename)
    except Exception as exc:  # ML service may not be up yet — never crash the backend
        logger.warning("Could not reach ML service at %s: %s", url, exc)


# ── Revenue Projections ────────────────────────────────────────────────────────

_CLUSTER_LABELS: dict[int, str] = {
    0: "High-Volume Grocery",
    1: "Mid-Market Retail",
    2: "Food & Beverage",
    3: "Professional Services",
    4: "E-Commerce",
}


@router.post(
    "/projections/revenue",
    response_model=RevenueProjectionResponse,
    tags=["Projections"],
    summary="Calculate ML-driven revenue projection for a merchant",
)
def calculate_revenue_projection(
    # for Matthew/Denzel to edit 
    payload: RevenueProjectionRequest,
    db: Session = Depends(get_db),
):
    """
    Accepts merchant transaction data and returns a TPV estimate,
    projected net revenue, and a pgvector-based cluster assignment.
    The cluster assignment will be replaced with a real model inference
    call once the ML pipeline is wired up.
    """
    effective_rate = payload.current_rate if payload.current_rate is not None else 0.0175
    tpv = payload.transaction_volume
    tx_count = tpv / payload.avg_ticket_size
    projected_revenue = round(
        tpv * effective_rate - (payload.fixed_fee or 0.30) * tx_count, 2
    )
    # TODO: replace with pgvector nearest-neighbour lookup against merchant embeddings
    cluster_id = abs(hash(payload.mcc_code)) % 5
    return RevenueProjectionResponse(
        merchant_id=payload.merchant_id,
        tpv_estimate=round(tpv, 2),
        projected_revenue=projected_revenue,
        cluster_assignment=cluster_id,
        cluster_label=_CLUSTER_LABELS.get(cluster_id, "Unknown"),
        confidence_score=round(0.70 + random.uniform(0, 0.25), 4),
        period_start=payload.period_start,
        period_end=payload.period_end,
    )


# ── Transactions ───────────────────────────────────────────────────────────────

# for Justin to edit 
# THIS IS FOR SALES
@router.post("/transactions/upload", tags=["Transactions"])
async def upload_transactions(
    file: UploadFile = File(...),
    merchant_id: Optional[str] = Form("default"),
    db: Session = Depends(get_db),
):
    """Upload transactions from a CSV or Excel file."""
    allowed = {"csv", "xlsx", "xls"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(allowed)}",
        )

    contents = await file.read()
    batch_id = f"batch_{uuid.uuid4().hex[:8]}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    if ext == "csv":
        headers, rows, errors = DataProcessingService.parse_csv_file(contents)
    else:
        headers, rows, errors = DataProcessingService.parse_excel_file(contents, file.filename)

    if headers is None:
        raise HTTPException(
            status_code=400,
            detail={"message": "Failed to parse file", "errors": errors},
        )

    batch = UploadBatch(
        batch_id=batch_id,
        filename=file.filename,
        file_type=ext,
        merchant_id=merchant_id if merchant_id != "default" else None,
        record_count=len(rows),
        error_count=len(errors),
        status="SUCCESS" if not errors else "PARTIAL",
    )

    stored_count = 0
    parse_errors = list(errors)
    for i, row in enumerate(rows):
        try:
            raw_transaction_date = row.get("transaction_date")
            parsed_transaction_date = None

            for date_format in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    parsed_transaction_date = datetime.strptime(
                        str(raw_transaction_date), date_format
                    ).date()
                    break
                except (TypeError, ValueError):
                    continue

            if parsed_transaction_date is None:
                raise ValueError(
                    "transaction_date must be in DD/MM/YYYY or YYYY-MM-DD format"
                )

            tx = Transaction(
                transaction_id=row.get("transaction_id"),
                transaction_date=parsed_transaction_date,
                merchant_id=row.get("merchant_id"),
                amount=Decimal(str(row.get("amount", 0))),
                transaction_type=row.get("transaction_type"),
                card_type=row.get("card_type"),
                batch_id=batch_id,
            )
            db.add(tx)
            stored_count += 1
        except Exception as exc:
            parse_errors.append({"row": i + 2, "error": str(exc)})

    try:
        db.add(batch)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")

    return {
        "status": "success",
        "batch_id": batch_id,
        "filename": file.filename,
        "total_records": len(rows),
        "stored_records": stored_count,
        "error_count": len(parse_errors),
        "errors": parse_errors or None,
        "preview": rows[:10],
    }


@router.get("/transactions", response_model=list[TransactionResponse], tags=["Transactions"])
def list_transactions(
    merchant_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List transactions, optionally filtered by merchant."""
    query = db.query(Transaction)
    if merchant_id:
        query = query.filter(Transaction.merchant_id == merchant_id)
    return query.offset(offset).limit(min(limit, 100)).all()


@router.get(
    "/transactions/{transaction_id}",
    response_model=TransactionResponse,
    tags=["Transactions"],
)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


# ── Calculations ───────────────────────────────────────────────────────────────

@router.post("/calculations/merchant-fee", tags=["Calculations"])
def calculate_merchant_fee(data: dict, db: Session = Depends(get_db)):
    """Calculate fees based on current interchange rates."""
    mcc = data.get("mcc")
    if not mcc:
        raise HTTPException(status_code=400, detail="MCC code required")

    transactions = data.get("transactions", [])
    avg_transaction_value = data.get("average_transaction_value")
    monthly_transactions = data.get("monthly_transactions")

    use_aggregate_inputs = avg_transaction_value is not None and monthly_transactions is not None

    if use_aggregate_inputs:
        try:
            avg_ticket = float(avg_transaction_value)
            txn_count = int(monthly_transactions)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="average_transaction_value must be numeric and monthly_transactions must be an integer",
            )

        if avg_ticket <= 0 or txn_count <= 0:
            raise HTTPException(
                status_code=400,
                detail="average_transaction_value and monthly_transactions must both be greater than zero",
            )

        fixed_fee_raw = data.get("fixed_fee")
        minimum_fee_raw = data.get("minimum_fee")
        fixed_fee = 0.30 if fixed_fee_raw is None else float(fixed_fee_raw)
        minimum_fee = 0.0 if minimum_fee_raw is None else float(minimum_fee_raw)
        base_cost_rate = MerchantFeeCalculationService.estimate_base_cost_rate(
            mcc,
            avg_ticket=avg_ticket,
            monthly_txn_count=txn_count,
        )
        if base_cost_rate is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to derive base cost rate from cost structure JSON for MCC {mcc}",
            )

        current_rate = data.get("current_rate")
        if current_rate is None:
            current_rate = float(base_cost_rate) + MerchantFeeCalculationService.DEFAULT_QUOTE_MARGIN_RATE
        else:
            try:
                current_rate = float(current_rate)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="current_rate must be numeric")

        total_volume = avg_ticket * txn_count
        per_tx_fee = max((avg_ticket * current_rate) + fixed_fee, minimum_fee)
        total_fees = per_tx_fee * txn_count
        effective_rate = (total_fees / total_volume) if total_volume > 0 else 0.0
        margin_rate = current_rate - float(base_cost_rate)

        result = {
            "success": True,
            "transaction_count": txn_count,
            "total_volume": float(total_volume),
            "total_fees": float(total_fees),
            "effective_rate": float(effective_rate),
            "average_ticket": float(avg_ticket),
            "mcc": mcc,
            "base_cost_rate": float(base_cost_rate),
            "applied_rate": float(current_rate),
            "margin_rate": float(margin_rate),
            "margin_bps": int(round(margin_rate * 10000)),
            "fixed_fee": float(fixed_fee),
            "minimum_fee": float(minimum_fee),
        }
    else:
        if not transactions:
            raise HTTPException(
                status_code=400,
                detail="Provide either transactions or (average_transaction_value + monthly_transactions)",
            )

        fixed_fee_raw = data.get("fixed_fee")
        minimum_fee_raw = data.get("minimum_fee")
        fixed_fee = 0.30 if fixed_fee_raw is None else float(fixed_fee_raw)
        minimum_fee = 0.0 if minimum_fee_raw is None else float(minimum_fee_raw)

        result = MerchantFeeCalculationService.calculate_current_rates(
            transactions,
            mcc,
            data.get("current_rate"),
            fixed_fee,
            minimum_fee,
        )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    result["input_mode"] = "aggregate" if use_aggregate_inputs else "transactions"

    calc = CalculationResult(
        calculation_type="MERCHANT_FEE",
        mcc=mcc,
        transaction_count=result["transaction_count"],
        total_volume=Decimal(str(result["total_volume"])),
        total_fees=Decimal(str(result["total_fees"])),
        effective_rate=Decimal(str(result["effective_rate"])),
        applied_rate=Decimal(str(result["applied_rate"])),
    )
    db.add(calc)
    db.commit()
    return {"status": "success", "data": result}


@router.post("/calculations/desired-margin", tags=["Calculations"])
def calculate_desired_margin(data: dict, db: Session = Depends(get_db)):
    """Calculate the rate required to hit a desired profit margin."""
    transactions = data.get("transactions", [])
    mcc = data.get("mcc")
    if not mcc:
        raise HTTPException(status_code=400, detail="MCC code required")
    if not transactions:
        raise HTTPException(status_code=400, detail="Transactions array required")

    result = MerchantFeeCalculationService.calculate_desired_margin(
        transactions, mcc, data.get("desired_margin", 0.015)
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    calc = CalculationResult(
        calculation_type="DESIRED_MARGIN",
        mcc=mcc,
        transaction_count=result["transaction_count"],
        total_volume=Decimal(str(result["total_volume"])),
        desired_margin=Decimal(str(result["desired_margin"])),
        recommended_rate=Decimal(str(result["recommended_rate"])),
    )
    db.add(calc)
    db.commit()
    return {"status": "success", "data": result}


@router.post("/calculations/desired-margin-details", tags=["Calculations"])
def calculate_desired_margin_details(data: dict, db: Session = Depends(get_db)):
    """
    Dedicated aggregator endpoint for the Rates Quotation tool.

    Reuses backend orchestration to call 3 ML endpoints:
      1) /ml/getCompositeMerchant
      2) /ml/GetCostForecast
      3) /ml/GetVolumeForecast
    """
    transactions = data.get("transactions", [])
    mcc = data.get("mcc")
    if not mcc:
        raise HTTPException(status_code=400, detail="MCC code required")

    try:
        mcc_int = int(mcc)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="MCC must be an integer")

    desired_margin = float(data.get("desired_margin", 0.015) or 0.015)
    current_rate_raw = data.get("current_rate")
    current_rate: float | None = None
    if current_rate_raw is not None:
        try:
            parsed_rate = float(current_rate_raw)
            current_rate = parsed_rate / 100.0 if parsed_rate > 1.0 else parsed_rate
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="current_rate must be numeric")

    def _base_rate_for_mcc(code: int) -> float:
        derived = MerchantFeeCalculationService.estimate_base_cost_rate(
            code,
            transactions=transactions if transactions else None,
            avg_ticket=avg_transaction_value,
            monthly_txn_count=monthly_transactions,
        )
        if derived is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to derive base cost rate from cost structure JSON for MCC {code}",
            )
        return float(derived)
    avg_transaction_value = data.get("average_transaction_value")
    monthly_transactions = data.get("monthly_transactions")

    use_aggregate_inputs = avg_transaction_value is not None and monthly_transactions is not None

    if use_aggregate_inputs:
        try:
            avg_ticket = float(avg_transaction_value)
            txn_count = int(monthly_transactions)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="average_transaction_value must be numeric and monthly_transactions must be an integer",
            )

        if avg_ticket <= 0 or txn_count <= 0:
            raise HTTPException(
                status_code=400,
                detail="average_transaction_value and monthly_transactions must both be greater than zero",
            )

        total_volume = avg_ticket * txn_count
        fixed_fee_raw = data.get("fixed_fee")
        minimum_fee = 0.0 if fixed_fee_raw is None else float(fixed_fee_raw)
        base_cost_rate = _base_rate_for_mcc(mcc_int)
        if current_rate is not None:
            recommended_rate = current_rate
            desired_margin = recommended_rate - base_cost_rate
        else:
            recommended_rate = base_cost_rate + desired_margin
        estimated_fees = (total_volume * recommended_rate) + (minimum_fee * txn_count)
        estimated_effective_rate = estimated_fees / total_volume if total_volume > 0 else 0.0

        result = {
            "success": True,
            "transaction_count": txn_count,
            "total_volume": float(total_volume),
            "average_ticket": float(avg_ticket),
            "desired_margin": float(desired_margin),
            "base_cost_rate": float(base_cost_rate),
            "recommended_rate": float(recommended_rate),
            "estimated_total_fees": float(estimated_fees),
            "estimated_effective_rate": float(estimated_effective_rate),
            "mcc": mcc_int,
            "minimum_fee": minimum_fee,
            "input_current_rate": float(current_rate) if current_rate is not None else None,
        }
    else:
        if not transactions:
            raise HTTPException(
                status_code=400,
                detail="Provide either transactions or (average_transaction_value + monthly_transactions)",
            )

        base_cost_rate = _base_rate_for_mcc(mcc_int)
        desired_margin_for_calc = (
            (current_rate - base_cost_rate) if current_rate is not None else desired_margin
        )

        fixed_fee_raw = data.get("fixed_fee")
        minimum_fee = 0.0 if fixed_fee_raw is None else float(fixed_fee_raw)

        result = MerchantFeeCalculationService.calculate_desired_margin(
            transactions,
            mcc_int,
            desired_margin_for_calc,
            minimum_fee,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        result["input_current_rate"] = float(current_rate) if current_rate is not None else None

    calc = CalculationResult(
        calculation_type="DESIRED_MARGIN",
        mcc=mcc_int,
        transaction_count=result["transaction_count"],
        total_volume=Decimal(str(result["total_volume"])),
        desired_margin=Decimal(str(result["desired_margin"])),
        recommended_rate=Decimal(str(result["recommended_rate"])),
    )
    db.add(calc)
    db.commit()

    recommended_rate = float(result.get("recommended_rate") or 0.0)
    card_type = str(data.get("card_type") or "both").strip().lower() or "both"

    card_types = data.get("card_types")
    if not isinstance(card_types, list) or not card_types:
        card_types = [card_type] if card_type != "both" else ["both"]
    else:
        card_types = [str(v).strip().lower() for v in card_types if str(v).strip()]
        if not card_types:
            card_types = ["both"]

    if use_aggregate_inputs:
        onboarding_rows = MerchantQuoteService._build_onboarding_rows(
            avg_ticket=result["average_ticket"],
            monthly_txn_count=result["transaction_count"],
            brands=["visa", "mastercard"],
            effective_rate_pct=recommended_rate * 100.0,
        )
    else:
        onboarding_rows = MerchantQuoteService.build_onboarding_rows_from_transactions(
            transactions=transactions,
            card_type=card_type,
            effective_rate_pct=recommended_rate * 100.0,
        )

    pipeline = MerchantQuoteService.run_ml_forecast_pipeline(
        mcc=mcc_int,
        card_types=card_types,
        onboarding_rows=onboarding_rows,
    )

    def _safe_float(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _week_label(index: int) -> str:
        base = datetime.now(timezone.utc).date()
        day = base + timedelta(days=(7 * (index - 1)))
        return f"W{index} ({day.isoformat()})"

    transaction_dates = []
    merchant_id = data.get("merchant_id")
    for tx in transactions:
        raw = tx.get("transaction_date") or tx.get("date") or tx.get("txn_date")
        if raw:
            transaction_dates.append(str(raw))
        if not merchant_id:
            merchant_id = tx.get("merchant_id") or tx.get("merchantId")

    tx_summary = {
        "merchant_id": str(merchant_id) if merchant_id is not None else None,
        "transaction_count": int(result.get("transaction_count") or 0),
        "total_volume": _safe_float(result.get("total_volume"), 0.0),
        "average_ticket": _safe_float(result.get("average_ticket"), 0.0),
        "mcc": mcc_int,
        "start_date": min(transaction_dates) if transaction_dates else None,
        "end_date": max(transaction_dates) if transaction_dates else None,
    }

    cost_series = []
    volume_series = []
    profitability_curve = []
    estimated_profit_min = None
    estimated_profit_max = None
    summary_profitability_pct = None
    ml_context = None

    if pipeline is not None:
        composite_payload = pipeline.get("composite", {})
        cost_payload = pipeline.get("cost", {})
        volume_payload = pipeline.get("volume", {})
        cost_forecast = cost_payload.get("forecast", [])
        volume_forecast = volume_payload.get("forecast", [])

        for item in cost_forecast:
            idx = int(item.get("forecast_week_index") or 0)
            cost_series.append(
                {
                    "week_index": idx,
                    "label": _week_label(idx),
                    "mid": _safe_float(item.get("proc_cost_pct_mid"), 0.0),
                    "lower": _safe_float(item.get("proc_cost_pct_ci_lower"), 0.0),
                    "upper": _safe_float(item.get("proc_cost_pct_ci_upper"), 0.0),
                }
            )

        for item in volume_forecast:
            idx = int(item.get("forecast_week_index") or 0)
            volume_series.append(
                {
                    "week_index": idx,
                    "label": _week_label(idx),
                    "mid": _safe_float(item.get("total_proc_value_mid"), 0.0),
                    "lower": _safe_float(item.get("total_proc_value_ci_lower"), 0.0),
                    "upper": _safe_float(item.get("total_proc_value_ci_upper"), 0.0),
                }
            )

        paired_len = min(len(cost_series), len(volume_series))
        if paired_len > 0:
            low_total = 0.0
            high_total = 0.0
            mid_total_revenue = 0.0
            mid_total_profit = 0.0
            for idx in range(paired_len):
                c = cost_series[idx]
                v = volume_series[idx]
                # Cost percentages cannot be negative; clip forecast bands before profitability math.
                c_lower = max(0.0, c["lower"])
                c_upper = max(c_lower, c["upper"])
                c_mid = max(0.0, c["mid"])
                low_total += v["lower"] * (recommended_rate - c_upper)
                high_total += v["upper"] * (recommended_rate - c_lower)
                mid_total_profit += v["mid"] * (recommended_rate - c_mid)
                mid_total_revenue += v["mid"] * recommended_rate

            # Keep summary range consistent with curve economics by including
            # fixed-fee contribution across the same forecast horizon.
            fixed_fee_per_txn = _safe_float(result.get("minimum_fee"), 0.0)
            total_txn_count = _safe_float(result.get("transaction_count"), 0.0)
            weekly_txn_count = total_txn_count / 4.345 if total_txn_count > 0 else 0.0
            horizon_fixed_fee = fixed_fee_per_txn * weekly_txn_count * paired_len
            low_total += horizon_fixed_fee
            high_total += horizon_fixed_fee
            mid_total_profit += horizon_fixed_fee
            mid_total_revenue += horizon_fixed_fee

            estimated_profit_min = min(low_total, high_total)
            estimated_profit_max = max(low_total, high_total)

            if mid_total_revenue > 0:
                summary_profitability_pct = max(-100.0, min(100.0, (mid_total_profit / mid_total_revenue) * 100.0))

            default_rate_grid = [
                1.50, 1.75, 2.00, 2.25, 2.35, 2.50, 2.75, 3.00, 3.25, 3.50,
            ]
            recommended_rate_pct = round(recommended_rate * 100.0, 2)
            user_grid = data.get("rate_grid_pct")
            if isinstance(user_grid, list) and user_grid:
                rate_grid = []
                for value in user_grid:
                    try:
                        rate_grid.append(float(value))
                    except (TypeError, ValueError):
                        continue
                if not rate_grid:
                    rate_grid = default_rate_grid
            else:
                rate_grid = default_rate_grid

            # Keep the chart interpretable by always plotting the exact suggested rate.
            if recommended_rate_pct not in rate_grid:
                rate_grid.append(recommended_rate_pct)
            rate_grid = sorted(set(rate_grid))

            for rate_pct in rate_grid:
                rate_decimal = rate_pct / 100.0
                low_total_rate = 0.0
                high_total_rate = 0.0
                mid_total_rate = 0.0
                total_mid_volume = 0.0
                total_mid_revenue = 0.0

                for idx in range(paired_len):
                    c = cost_series[idx]
                    v = volume_series[idx]
                    c_lower = max(0.0, c["lower"])
                    c_mid = max(0.0, c["mid"])
                    c_upper = max(c_lower, c["upper"])

                    low_total_rate += v["lower"] * (rate_decimal - c_upper)
                    high_total_rate += v["upper"] * (rate_decimal - c_lower)
                    mid_total_rate += v["mid"] * (rate_decimal - c_mid)
                    total_mid_volume += max(0.0, v["mid"])
                    total_mid_revenue += max(0.0, v["mid"]) * rate_decimal

                # Include fixed-fee contribution so curve matches front-card economics.
                fixed_fee_per_txn = _safe_float(result.get("minimum_fee"), 0.0)
                total_txn_count = _safe_float(result.get("transaction_count"), 0.0)
                weekly_txn_count = total_txn_count / 4.345 if total_txn_count > 0 else 0.0
                horizon_fixed_fee = fixed_fee_per_txn * weekly_txn_count * paired_len

                low_total_rate += horizon_fixed_fee
                high_total_rate += horizon_fixed_fee
                mid_total_rate += horizon_fixed_fee
                total_mid_revenue += horizon_fixed_fee

                # Avoid probability saturation at exactly 0/100 by introducing a
                # minimum uncertainty band tied to projected revenue.
                spread_band = max(
                    (high_total_rate - low_total_rate) / 2.0,
                    total_mid_revenue * 0.08,
                    1e-9,
                )
                probability_pct = MerchantQuoteService.normal_cdf(mid_total_rate, 0.0, spread_band) * 100.0

                profitability_pct = 0.0
                if total_mid_volume > 0:
                    profitability_pct = (mid_total_rate / total_mid_volume) * 100.0

                profitability_curve.append(
                    {
                        "rate_pct": round(rate_pct, 2),
                        "probability_pct": round(max(0.0, min(100.0, probability_pct)), 2),
                        "profitability_pct": round(profitability_pct, 2),
                    }
                )

        ml_context = {
            "k": int(composite_payload.get("k") or 0),
            "composite_merchant_id": composite_payload.get("composite_merchant_id"),
            "matching_start_month": composite_payload.get("matching_start_month"),
            "matching_end_month": composite_payload.get("matching_end_month"),
            "matched_neighbor_merchant_ids": composite_payload.get("matched_neighbor_merchant_ids", []),
            "sarima_cost": cost_payload.get("sarima_metadata"),
            "sarima_volume": volume_payload.get("sarima_metadata"),
        }

    if not profitability_curve:
        # Fallback curve when ML pipeline is unavailable (e.g., timeout on very large inputs).
        # This keeps UX usable and avoids "Pending backend calculation" for profitability %.
        default_rate_grid = [
            1.50, 1.75, 2.00, 2.25, 2.35, 2.50, 2.75, 3.00, 3.25, 3.50,
        ]
        # Anchor around the recommended rate so fallback probability remains shaped
        # and monotonic rather than flattening at 100% for all quoted rates.
        anchor_rate = _safe_float(result.get("recommended_rate"), recommended_rate)
        std_dev = 0.0045  # 45 bps spread around anchor rate
        for rate_pct in default_rate_grid:
            rate_decimal = rate_pct / 100.0
            probability = MerchantQuoteService.normal_cdf(rate_decimal, anchor_rate, std_dev)
            profitability_curve.append(
                {
                    "rate_pct": round(rate_pct, 2),
                    "probability_pct": round(max(0.0, min(1.0, probability)) * 100.0, 2),
                }
            )

    fallback_profit = _safe_float(result.get("estimated_total_fees"), 0.0)
    if summary_profitability_pct is None:
        base_rate = _safe_float(result.get("base_cost_rate"), 0.0)
        total_volume = _safe_float(result.get("total_volume"), 0.0)
        total_fees = _safe_float(result.get("estimated_total_fees"), 0.0)
        fallback_profitability = (recommended_rate - base_rate) * total_volume
        fallback_profitability += _safe_float(result.get("minimum_fee"), 0.0) * _safe_float(result.get("transaction_count"), 0.0)
        if total_fees > 0:
            summary_profitability_pct = max(-100.0, min(100.0, (fallback_profitability / total_fees) * 100.0))

    if (
        estimated_profit_max is not None
        and fallback_profit > 0
        and estimated_profit_max < (0.05 * fallback_profit)
    ):
        # Guardrail: if forecast-based profit is orders of magnitude below the
        # deterministic fee baseline, keep results on a realistic business scale.
        estimated_profit_min = fallback_profit * 0.75
        estimated_profit_max = fallback_profit * 1.25

    base_rate_for_summary = _safe_float(result.get("base_cost_rate"), _base_rate_for_mcc(mcc_int))
    margin_rate_for_summary = recommended_rate - base_rate_for_summary
    summary = {
        "suggested_rate_pct": round(recommended_rate * 100.0, 2),
        "margin_bps": int(round(margin_rate_for_summary * 10000.0)),
        "estimated_profit_min": round(estimated_profit_min if estimated_profit_min is not None else fallback_profit, 2),
        "estimated_profit_max": round(estimated_profit_max if estimated_profit_max is not None else fallback_profit, 2),
        "profitability_pct": round(summary_profitability_pct, 2) if summary_profitability_pct is not None else None,
    }

    return {
        "status": "success",
        "data": {
            "summary": summary,
            "transaction_summary": tx_summary,
            "cost_forecast": cost_series,
            "volume_forecast": volume_series,
            "profitability_curve": profitability_curve,
            "ml_context": ml_context,
            "calculation": result,
        },
    }


# ── Merchants ──────────────────────────────────────────────────────────────────

@router.get("/merchants", response_model=list[MerchantResponse], tags=["Merchants"])
def list_merchants(
    limit: int = 20, offset: int = 0, db: Session = Depends(get_db)
):
    return db.query(Merchant).offset(offset).limit(min(limit, 100)).all()


@router.get("/merchants/{merchant_id}", response_model=MerchantResponse, tags=["Merchants"])
def get_merchant(merchant_id: str, db: Session = Depends(get_db)):
    merchant = db.query(Merchant).filter(Merchant.merchant_id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return merchant


@router.post("/merchants", response_model=MerchantResponse, status_code=201, tags=["Merchants"])
def create_or_update_merchant(payload: MerchantCreate, db: Session = Depends(get_db)):
    merchant = db.query(Merchant).filter(Merchant.merchant_id == payload.merchant_id).first()
    if merchant:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(merchant, field, value)
    else:
        merchant = Merchant(**payload.model_dump())
        db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant


# ── MCC Codes ──────────────────────────────────────────────────────────────────

@router.get("/mcc-codes", tags=["MCC"])
def list_mccs():
    return {"status": "success", "data": MCCService.get_all_mccs()}


@router.get("/mcc-codes/search", tags=["MCC"])
def search_mccs(q: str):
    if len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")
    results = MCCService.search_mccs(q.strip())
    return {"status": "success", "data": results, "count": len(results)}


@router.get("/mcc-codes/{mcc_code}", tags=["MCC"])
def get_mcc(mcc_code: str):
    mcc = MCCService.get_mcc_by_code(mcc_code)
    if not mcc:
        raise HTTPException(status_code=404, detail="MCC code not found")
    return {"status": "success", "data": mcc}


# ── Cost Calculation ──────────────────────────────────────────────────────────

@router.post(
    "/calculations/transaction-costs",
    tags=["Calculations"],
    summary="Calculate interchange + network costs from a transaction file",
    response_class=StreamingResponse,
)
async def calculate_transaction_costs(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV or Excel file of transactions"),
    mcc: int = Query(..., description="Merchant Category Code (e.g. 5499)"),
):
    """
    Accepts a CSV/Excel transaction file and an MCC query param.

    Response body:    enriched CSV file (original columns + card_cost,
                      network_cost, total_cost, match_found, etc.)

    Response headers: 6 cost metric headers
        X-Total-Cost, X-Total-Payment-Volume, X-Effective-Rate,
        X-Slope, X-Cost-Variance, X-Weekly-Cost-Variance

    After returning the response the enriched CSV and metrics are forwarded
    to the ML microservice as a background task.

    This endpoint must be called BEFORE quotation calculations.
    """
    allowed = {"csv", "xlsx", "xls"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(allowed)}",
        )
    try:
        contents = await file.read()
        result, enriched_csv_bytes = run_cost_calculation(contents, file.filename, mcc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cost calculation failed: {exc}")

    # Fire-and-forget: forward enriched CSV + metrics to ML microservice.
    # BackgroundTasks ensures the caller gets the response immediately even
    # if the ML service is slow or temporarily unavailable.
    background_tasks.add_task(
        _forward_to_ml,
        enriched_csv_bytes=enriched_csv_bytes,
        filename=file.filename,
        mcc=mcc,
        total_cost=result.totalCost,
        total_payment_volume=result.totalPaymentVolume,
        effective_rate=result.effectiveRate,
        slope=result.slope,
        cost_variance=result.costVariance,
    )

    base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
    output_filename = f"{base_name}_enriched.csv"

    return StreamingResponse(
        io.BytesIO(enriched_csv_bytes),
        media_type="text/csv",
        headers={
            "Content-Disposition":           f'attachment; filename="{output_filename}"',
            "X-Total-Cost":                  str(result.totalCost),
            "X-Total-Payment-Volume":        str(result.totalPaymentVolume),
            "X-Effective-Rate":              str(result.effectiveRate),
            "X-Slope":                       str(result.slope)              if result.slope              is not None else "null",
            "X-Cost-Variance":               str(result.costVariance)       if result.costVariance       is not None else "null",
            "X-Weekly-Cost-Variance":        str(result.weeklyCostVariance) if result.weeklyCostVariance is not None else "null",
            "Access-Control-Expose-Headers": (
                "X-Total-Cost, X-Total-Payment-Volume, X-Effective-Rate, "
                "X-Slope, X-Cost-Variance, X-Weekly-Cost-Variance"
            ),
        },
    )


# ── Merchant Quote ─────────────────────────────────────────────────────────────

# Merchant Quote endpoint for sales tool - Justin to edit logic in service.py
@router.post(
    "/merchant-quote",
    response_model=MerchantQuoteResponse,
    tags=["Merchant Quote"],
    summary="Generate merchant quote details for frontend tool",
)
def generate_merchant_quote(payload: MerchantQuoteRequest):
    return create_merchant_quote(payload)
