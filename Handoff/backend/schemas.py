"""
Pydantic v2 schemas for request/response validation.

Strict typing keeps the FastAPI auto-docs accurate and prevents bad data
from reaching the ML pipeline or the database.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# ── Revenue Projection ─────────────────────────────────────────────────────────

class RevenueProjectionRequest(BaseModel):
    """Payload sent by the client to request an ML revenue projection."""

    merchant_id: str = Field(
        ..., examples=["merch_001"], description="Unique merchant identifier"
    )
    transaction_volume: float = Field(
        ..., gt=0, description="Total transaction volume for the period (USD)"
    )
    avg_ticket_size: float = Field(
        ..., gt=0, description="Average transaction ticket size (USD)"
    )
    mcc_code: str = Field(
        ..., min_length=4, max_length=4, description="4-digit Merchant Category Code"
    )
    period_start: date = Field(..., description="Projection period start date")
    period_end: date = Field(..., description="Projection period end date")
    current_rate: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Current interchange rate as a decimal (0–1)"
    )
    fixed_fee: Optional[float] = Field(
        0.30, ge=0.0, description="Per-transaction fixed fee (USD)"
    )


class RevenueProjectionResponse(BaseModel):
    """ML model output returned to the client."""

    merchant_id: str
    tpv_estimate: float = Field(..., description="Total Payment Volume estimate (USD)")
    projected_revenue: float = Field(..., description="Projected net revenue (USD)")
    cluster_assignment: int = Field(..., description="ML cluster ID for the merchant segment")
    cluster_label: str = Field(..., description="Human-readable cluster segment label")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")
    period_start: date
    period_end: date


# ── Transaction ────────────────────────────────────────────────────────────────

class TransactionBase(BaseModel):
    transaction_id: str
    transaction_date: date
    merchant_id: str
    amount: float = Field(..., gt=0)
    transaction_type: str = Field(..., pattern="^(Sale|Refund|Void)$")
    card_type: str = Field(..., pattern="^(Visa|Mastercard|Amex|Discover)$")


class TransactionCreate(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    id: int
    batch_id: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Merchant ───────────────────────────────────────────────────────────────────

class MerchantBase(BaseModel):
    merchant_id: str
    merchant_name: str
    mcc: str = Field(..., min_length=4, max_length=4)
    industry: Optional[str] = None
    annual_volume: Optional[float] = None
    average_ticket: Optional[float] = None
    current_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    fixed_fee: Optional[float] = Field(0.30, ge=0.0)


class MerchantCreate(MerchantBase):
    pass


class MerchantResponse(MerchantBase):
    id: int

    model_config = {"from_attributes": True}


# ── Generic wrappers ───────────────────────────────────────────────────────────

class SuccessResponse(BaseModel):
    status: str = "success"
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    detail: Optional[str] = None
