"""
Data validation module for transaction and merchant data
"""
from datetime import datetime
import re

class ValidationError(Exception):
    """Custom validation exception"""
    def __init__(self, message, row=None, column=None, error_type=None):
        self.message = message
        self.row = row
        self.column = column
        self.error_type = error_type
        super().__init__(self.message)

class TransactionValidator:
    """Validate transaction data"""
    
    REQUIRED_COLUMNS = ['transaction_id', 'transaction_date', 'merchant_id', 'amount', 'transaction_type', 'card_type']
    
    VALID_TRANSACTION_TYPES = ['Sale', 'Refund', 'Void']
    VALID_CARD_TYPES = ['Visa', 'Mastercard', 'Amex', 'Discover']
    
    DATE_FORMATS = [
        '%d/%m/%Y',  # DD/MM/YYYY
        '%Y-%m-%d',  # YYYY-MM-DD
        '%m/%d/%Y',  # MM/DD/YYYY
    ]

    @staticmethod
    def validate_date(date_str):
        """Validate date format"""
        if not date_str:
            return False
        
        for fmt in TransactionValidator.DATE_FORMATS:
            try:
                datetime.strptime(date_str.strip(), fmt)
                return True
            except ValueError:
                continue
        return False

    @staticmethod
    def validate_amount(amount_str):
        """Validate amount is positive numeric value"""
        if not amount_str:
            return False
        
        try:
            amount = float(amount_str)
            return amount > 0
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_transaction_type(tx_type):
        """Validate transaction type"""
        return tx_type in TransactionValidator.VALID_TRANSACTION_TYPES

    @staticmethod
    def validate_card_type(card_type):
        """Validate card type"""
        return card_type in TransactionValidator.VALID_CARD_TYPES

    @staticmethod
    def validate_transaction_id(tx_id):
        """Validate transaction ID format"""
        return bool(tx_id and len(str(tx_id).strip()) > 0)

    @staticmethod
    def validate_merchant_id(merchant_id):
        """Validate merchant ID format"""
        return bool(merchant_id and len(str(merchant_id).strip()) > 0)

    @classmethod
    def validate_row(cls, row_data, row_number):
        """
        Validate a single transaction row
        Returns: (is_valid, errors)
        """
        errors = []

        # Check required fields
        for column in cls.REQUIRED_COLUMNS:
            if column not in row_data or not row_data[column]:
                errors.append({
                    'row': row_number,
                    'column': column,
                    'error': 'Required field cannot be empty',
                    'error_type': 'MISSING_VALUE'
                })

        # Validate individual fields
        if row_data.get('transaction_id'):
            if not cls.validate_transaction_id(row_data['transaction_id']):
                errors.append({
                    'row': row_number,
                    'column': 'transaction_id',
                    'error': 'Invalid transaction ID format',
                    'error_type': 'INVALID_FORMAT'
                })

        if row_data.get('transaction_date'):
            if not cls.validate_date(row_data['transaction_date']):
                errors.append({
                    'row': row_number,
                    'column': 'transaction_date',
                    'error': 'Invalid date format (use DD/MM/YYYY, YYYY-MM-DD, or MM/DD/YYYY)',
                    'error_type': 'INVALID_DATE'
                })

        if row_data.get('merchant_id'):
            if not cls.validate_merchant_id(row_data['merchant_id']):
                errors.append({
                    'row': row_number,
                    'column': 'merchant_id',
                    'error': 'Invalid merchant ID format',
                    'error_type': 'INVALID_FORMAT'
                })

        if row_data.get('amount'):
            if not cls.validate_amount(row_data['amount']):
                errors.append({
                    'row': row_number,
                    'column': 'amount',
                    'error': 'Amount must be a positive number',
                    'error_type': 'INVALID_TYPE'
                })

        if row_data.get('transaction_type'):
            if not cls.validate_transaction_type(row_data['transaction_type']):
                errors.append({
                    'row': row_number,
                    'column': 'transaction_type',
                    'error': f"Transaction type must be one of: {', '.join(cls.VALID_TRANSACTION_TYPES)}",
                    'error_type': 'INVALID_TYPE'
                })

        if row_data.get('card_type'):
            if not cls.validate_card_type(row_data['card_type']):
                errors.append({
                    'row': row_number,
                    'column': 'card_type',
                    'error': f"Card type must be one of: {', '.join(cls.VALID_CARD_TYPES)}",
                    'error_type': 'INVALID_TYPE'
                })

        return len(errors) == 0, errors

    @classmethod
    def validate_headers(cls, headers):
        """
        Validate CSV headers
        Returns: (is_valid, missing_columns)
        """
        headers_lower = [h.lower().strip() for h in headers]
        missing = [col for col in cls.REQUIRED_COLUMNS if col not in headers_lower]
        
        return len(missing) == 0, missing


class MerchantValidator:
    """Validate merchant data"""
    
    @staticmethod
    def validate_mcc(mcc):
        """Validate MCC (Merchant Category Code)"""
        if not mcc:
            return False
        
        # MCC should be 4 digits
        mcc_str = str(mcc).strip()
        return bool(re.match(r'^\d{4}$', mcc_str))

    @staticmethod
    def validate_merchant_profile(profile_data):
        """Validate merchant profile data"""
        errors = []
        
        if not profile_data.get('merchant_name'):
            errors.append('Merchant name is required')
        
        if profile_data.get('mcc'):
            if not MerchantValidator.validate_mcc(profile_data['mcc']):
                errors.append('MCC must be a 4-digit code')
        
        return len(errors) == 0, errors
