"""
ORM models — SQLAlchemy 2.x (no Flask-SQLAlchemy dependency).
All models inherit from the shared Base defined in database.py.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String

from database import Base


class Transaction(Base):
    """Payment transaction record."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    transaction_id = Column(String(100), unique=True, nullable=False, index=True)
    transaction_date = Column(Date, nullable=False)
    merchant_id = Column(String(100), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    transaction_type = Column(String(20), nullable=False)   # Sale | Refund | Void
    card_type = Column(String(20), nullable=False)          # Visa | Mastercard | Amex | Discover
    batch_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Transaction {self.transaction_id}>"


class Merchant(Base):
    """Merchant profile."""

    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True)
    merchant_id = Column(String(100), unique=True, nullable=False, index=True)
    merchant_name = Column(String(255), nullable=False)
    mcc = Column(String(4), nullable=False, index=True)         # Merchant Category Code
    industry = Column(String(100), nullable=True)
    annual_volume = Column(Numeric(15, 2), nullable=True)
    average_ticket = Column(Numeric(10, 2), nullable=True)
    current_rate = Column(Numeric(5, 4), nullable=True)         # Current interchange rate
    fixed_fee = Column(Numeric(6, 2), nullable=True, default=0.30)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Merchant {self.merchant_id}: {self.merchant_name}>"


class CalculationResult(Base):
    """Audit log of fee / margin calculations."""

    __tablename__ = "calculation_results"

    id = Column(Integer, primary_key=True)
    calculation_type = Column(String(50), nullable=False)   # MERCHANT_FEE | DESIRED_MARGIN
    merchant_id = Column(String(100), nullable=True, index=True)
    mcc = Column(String(4), nullable=True)
    transaction_count = Column(Integer, nullable=False)
    total_volume = Column(Numeric(15, 2), nullable=False)
    total_fees = Column(Numeric(12, 2), nullable=True)
    effective_rate = Column(Numeric(6, 4), nullable=True)
    applied_rate = Column(Numeric(5, 4), nullable=True)
    desired_margin = Column(Numeric(6, 4), nullable=True)
    recommended_rate = Column(Numeric(5, 4), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return f"<CalculationResult {self.id}: {self.calculation_type}>"


class UploadBatch(Base):
    """Tracks bulk file-upload operations."""

    __tablename__ = "upload_batches"

    id = Column(Integer, primary_key=True)
    batch_id = Column(String(100), unique=True, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)          # csv | xlsx
    merchant_id = Column(String(100), nullable=True)
    record_count = Column(Integer, nullable=False)
    status = Column(String(20), default="PROCESSING")       # PROCESSING | SUCCESS | FAILED | PARTIAL
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<UploadBatch {self.batch_id}: {self.status}>"
