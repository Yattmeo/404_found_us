"""
Database models for the application
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy  # noqa: F401

db = SQLAlchemy()


class Transaction(db.Model):
    """Transaction model for storing transaction data"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    transaction_date = db.Column(db.Date, nullable=False)
    merchant_id = db.Column(db.String(100), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # 'Sale', 'Refund', 'Void'
    card_type = db.Column(db.String(20), nullable=False)  # 'Visa', 'Mastercard', 'Amex', 'Discover'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    batch_id = db.Column(db.String(100), nullable=True, index=True)  # Reference to upload batch
    
    def __repr__(self):
        return f'<Transaction {self.transaction_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'transaction_id': self.transaction_id,
            'transaction_date': self.transaction_date.isoformat(),
            'merchant_id': self.merchant_id,
            'amount': float(self.amount),
            'transaction_type': self.transaction_type,
            'card_type': self.card_type,
            'created_at': self.created_at.isoformat(),
        }


class Merchant(db.Model):
    """Merchant model for storing merchant profile data"""
    __tablename__ = 'merchants'
    
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    merchant_name = db.Column(db.String(255), nullable=False)
    mcc = db.Column(db.String(4), nullable=False, index=True)  # Merchant Category Code
    industry = db.Column(db.String(100), nullable=True)
    annual_volume = db.Column(db.Numeric(15, 2), nullable=True)
    average_ticket = db.Column(db.Numeric(10, 2), nullable=True)
    current_rate = db.Column(db.Numeric(5, 4), nullable=True)  # Current interchange rate
    fixed_fee = db.Column(db.Numeric(6, 2), nullable=True, default=0.30)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Merchant {self.merchant_id}: {self.merchant_name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'merchant_id': self.merchant_id,
            'merchant_name': self.merchant_name,
            'mcc': self.mcc,
            'industry': self.industry,
            'annual_volume': float(self.annual_volume) if self.annual_volume else None,
            'average_ticket': float(self.average_ticket) if self.average_ticket else None,
            'current_rate': float(self.current_rate) if self.current_rate else None,
            'fixed_fee': float(self.fixed_fee) if self.fixed_fee else None,
        }


class CalculationResult(db.Model):
    """Store calculation results for audit/history"""
    __tablename__ = 'calculation_results'
    
    id = db.Column(db.Integer, primary_key=True)
    calculation_type = db.Column(db.String(50), nullable=False)  # 'MERCHANT_FEE' or 'DESIRED_MARGIN'
    merchant_id = db.Column(db.String(100), nullable=True, index=True)
    mcc = db.Column(db.String(4), nullable=True)
    transaction_count = db.Column(db.Integer, nullable=False)
    total_volume = db.Column(db.Numeric(15, 2), nullable=False)
    total_fees = db.Column(db.Numeric(12, 2), nullable=True)
    effective_rate = db.Column(db.Numeric(6, 4), nullable=True)
    applied_rate = db.Column(db.Numeric(5, 4), nullable=True)
    desired_margin = db.Column(db.Numeric(6, 4), nullable=True)
    recommended_rate = db.Column(db.Numeric(5, 4), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<CalculationResult {self.id}: {self.calculation_type}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'calculation_type': self.calculation_type,
            'merchant_id': self.merchant_id,
            'mcc': self.mcc,
            'transaction_count': self.transaction_count,
            'total_volume': float(self.total_volume),
            'total_fees': float(self.total_fees) if self.total_fees else None,
            'effective_rate': float(self.effective_rate) if self.effective_rate else None,
            'applied_rate': float(self.applied_rate) if self.applied_rate else None,
            'desired_margin': float(self.desired_margin) if self.desired_margin else None,
            'recommended_rate': float(self.recommended_rate) if self.recommended_rate else None,
            'created_at': self.created_at.isoformat(),
        }


class UploadBatch(db.Model):
    """Track file uploads for bulk transaction processing"""
    __tablename__ = 'upload_batches'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # 'csv' or 'xlsx'
    merchant_id = db.Column(db.String(100), nullable=True)
    record_count = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='PROCESSING')  # 'PROCESSING', 'SUCCESS', 'FAILED', 'PARTIAL'
    error_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<UploadBatch {self.batch_id}: {self.status}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'batch_id': self.batch_id,
            'filename': self.filename,
            'file_type': self.file_type,
            'merchant_id': self.merchant_id,
            'record_count': self.record_count,
            'status': self.status,
            'error_count': self.error_count,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
