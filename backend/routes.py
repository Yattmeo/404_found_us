"""
API routes — FastAPI version.
Replaces Flask Blueprints with a single APIRouter mounted at /api/v1.
"""
from __future__ import annotations

import logging
import os
import random
import uuid
from datetime import datetime
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
            tx = Transaction(
                transaction_id=row.get("transaction_id"),
                transaction_date=datetime.strptime(
                    row.get("transaction_date"), "%d/%m/%Y"
                ).date(),
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
    transactions = data.get("transactions", [])
    mcc = data.get("mcc")
    if not mcc:
        raise HTTPException(status_code=400, detail="MCC code required")
    if not transactions:
        raise HTTPException(status_code=400, detail="Transactions array required")

    result = MerchantFeeCalculationService.calculate_current_rates(
        transactions, mcc, data.get("current_rate"), data.get("fixed_fee", 0.30)
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

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
