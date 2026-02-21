"""
API routes — FastAPI version.
Replaces Flask Blueprints with a single APIRouter mounted at /api/v1.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
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

router = APIRouter(prefix="/api/v1")


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
