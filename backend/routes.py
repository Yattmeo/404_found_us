"""
API routes for transactions, calculations, and merchants
"""
from flask import Blueprint, request, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid
from decimal import Decimal

from models import db, Transaction, Merchant, CalculationResult, UploadBatch
from validators import TransactionValidator, MerchantValidator, ValidationError
from services import DataProcessingService, MerchantFeeCalculationService, MCCService
from errors import (
    APIError, ValidationAPIError, NotFoundError, success_response, 
    error_response, paginated_response
)

# Create blueprints
transactions_bp = Blueprint('transactions', __name__, url_prefix='/api/v1/transactions')
calculations_bp = Blueprint('calculations', __name__, url_prefix='/api/v1/calculations')
merchants_bp = Blueprint('merchants', __name__, url_prefix='/api/v1/merchants')
mccs_bp = Blueprint('mccs', __name__, url_prefix='/api/v1/mcc-codes')


# ==================== TRANSACTION ROUTES ====================

@transactions_bp.route('/upload', methods=['POST'])
def upload_transactions():
    """Upload transactions from CSV or Excel file"""
    try:
        # Check file presence
        if 'file' not in request.files:
            return error_response(
                APIError('No file provided', error_type='MISSING_FILE'),
                400
            )
        
        file = request.files['file']
        if file.filename == '':
            return error_response(
                APIError('No file selected', error_type='EMPTY_FILE'),
                400
            )
        
        # Validate file type
        allowed_extensions = {'csv', 'xlsx', 'xls'}
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_ext not in allowed_extensions:
            return error_response(
                APIError(f'File type not allowed. Allowed: {", ".join(allowed_extensions)}',
                        error_type='INVALID_FILE_TYPE'),
                400
            )
        
        # Read file content
        file_content = file.read()
        merchant_id = request.form.get('merchant_id', 'default')
        
        # Parse file
        if file_ext == 'csv':
            headers, rows, errors = DataProcessingService.parse_csv_file(file_content)
        else:  # xlsx or xls
            headers, rows, errors = DataProcessingService.parse_excel_file(file_content, file.filename)
        
        # If parsing failed completely
        if headers is None:
            return error_response(
                ValidationAPIError('Failed to parse file', errors),
                400
            )
        
        # Create batch
        batch_id = f"batch_{uuid.uuid4().hex[:8]}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        upload_batch = UploadBatch(
            batch_id=batch_id,
            filename=secure_filename(file.filename),
            file_type=file_ext,
            merchant_id=merchant_id if merchant_id != 'default' else None,
            record_count=len(rows),
            error_count=len(errors),
            status='SUCCESS' if not errors else 'PARTIAL'
        )
        
        # Store transactions
        stored_count = 0
        for row in rows:
            try:
                transaction = Transaction(
                    transaction_id=row.get('transaction_id'),
                    transaction_date=datetime.strptime(row.get('transaction_date'), '%d/%m/%Y').date(),
                    merchant_id=row.get('merchant_id'),
                    amount=Decimal(row.get('amount', 0)),
                    transaction_type=row.get('transaction_type'),
                    card_type=row.get('card_type'),
                    batch_id=batch_id
                )
                db.session.add(transaction)
                stored_count += 1
            except Exception as e:
                errors.append({
                    'row': rows.index(row) + 2,
                    'error': f'Failed to store: {str(e)}'
                })
        
        try:
            db.session.add(upload_batch)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return error_response(
                InternalServerError(f'Database error: {str(e)}'),
                500
            )
        
        return success_response({
            'batch_id': batch_id,
            'filename': upload_batch.filename,
            'total_records': len(rows),
            'stored_records': stored_count,
            'error_count': len(errors),
            'errors': errors if errors else None,
            'preview': [row for row in rows[:10]]  # Preview first 10
        }, 'File uploaded successfully', 201)
    
    except Exception as e:
        return error_response(
            InternalServerError(str(e)),
            500
        )


@transactions_bp.route('', methods=['GET'])
def list_transactions():
    """List transactions with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        merchant_id = request.args.get('merchant_id', None)
        
        # Validate pagination
        per_page = min(per_page, 100)  # Max 100 per page
        
        # Build query
        query = Transaction.query
        if merchant_id:
            query = query.filter_by(merchant_id=merchant_id)
        
        # Paginate
        pagination = query.paginate(page=page, per_page=per_page)
        
        transactions = [tx.to_dict() for tx in pagination.items]
        
        return paginated_response(
            transactions,
            pagination.total,
            page,
            per_page,
            'Transactions retrieved successfully'
        )
    
    except Exception as e:
        return error_response(
            InternalServerError(str(e)),
            500
        )


@transactions_bp.route('/<int:transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    """Get single transaction"""
    try:
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            return error_response(
                NotFoundError('Transaction not found', 'Transaction'),
                404
            )
        
        return success_response(transaction.to_dict(), 'Transaction retrieved successfully')
    
    except Exception as e:
        return error_response(
            InternalServerError(str(e)),
            500
        )


# ==================== CALCULATION ROUTES ====================

@calculations_bp.route('/merchant-fee', methods=['POST'])
def calculate_merchant_fee():
    """Calculate fees based on current rates"""
    try:
        data = request.get_json()
        
        if not data:
            return error_response(
                APIError('Request body required', error_type='MISSING_DATA'),
                400
            )
        
        # Extract parameters
        transactions = data.get('transactions', [])
        mcc = data.get('mcc')
        current_rate = data.get('current_rate')
        fixed_fee = data.get('fixed_fee', 0.30)
        
        # Validate
        if not mcc:
            return error_response(
                APIError('MCC code required', error_type='MISSING_MCC'),
                400
            )
        
        if not transactions:
            return error_response(
                APIError('Transactions array required', error_type='MISSING_TRANSACTIONS'),
                400
            )
        
        # Calculate
        result = MerchantFeeCalculationService.calculate_current_rates(
            transactions, mcc, current_rate, fixed_fee
        )
        
        if 'error' in result:
            return error_response(
                APIError(result['error'], error_type='CALCULATION_ERROR'),
                400
            )
        
        # Store result
        calc_record = CalculationResult(
            calculation_type='MERCHANT_FEE',
            mcc=mcc,
            transaction_count=result['transaction_count'],
            total_volume=Decimal(str(result['total_volume'])),
            total_fees=Decimal(str(result['total_fees'])),
            effective_rate=Decimal(str(result['effective_rate'])),
            applied_rate=Decimal(str(result['applied_rate']))
        )
        db.session.add(calc_record)
        db.session.commit()
        
        return success_response(result, 'Merchant fee calculation completed', 200)
    
    except Exception as e:
        return error_response(
            InternalServerError(str(e)),
            500
        )


@calculations_bp.route('/desired-margin', methods=['POST'])
def calculate_desired_margin():
    """Calculate rate needed for desired profit margin"""
    try:
        data = request.get_json()
        
        if not data:
            return error_response(
                APIError('Request body required', error_type='MISSING_DATA'),
                400
            )
        
        # Extract parameters
        transactions = data.get('transactions', [])
        mcc = data.get('mcc')
        desired_margin = data.get('desired_margin', 0.015)
        
        # Validate
        if not mcc:
            return error_response(
                APIError('MCC code required', error_type='MISSING_MCC'),
                400
            )
        
        if not transactions:
            return error_response(
                APIError('Transactions array required', error_type='MISSING_TRANSACTIONS'),
                400
            )
        
        # Calculate
        result = MerchantFeeCalculationService.calculate_desired_margin(
            transactions, mcc, desired_margin
        )
        
        if 'error' in result:
            return error_response(
                APIError(result['error'], error_type='CALCULATION_ERROR'),
                400
            )
        
        # Store result
        calc_record = CalculationResult(
            calculation_type='DESIRED_MARGIN',
            mcc=mcc,
            transaction_count=result['transaction_count'],
            total_volume=Decimal(str(result['total_volume'])),
            desired_margin=Decimal(str(result['desired_margin'])),
            recommended_rate=Decimal(str(result['recommended_rate']))
        )
        db.session.add(calc_record)
        db.session.commit()
        
        return success_response(result, 'Desired margin calculation completed', 200)
    
    except Exception as e:
        return error_response(
            InternalServerError(str(e)),
            500
        )


# ==================== MERCHANT ROUTES ====================

@merchants_bp.route('', methods=['GET'])
def list_merchants():
    """List merchants with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        per_page = min(per_page, 100)
        
        pagination = Merchant.query.paginate(page=page, per_page=per_page)
        merchants = [m.to_dict() for m in pagination.items]
        
        return paginated_response(
            merchants,
            pagination.total,
            page,
            per_page,
            'Merchants retrieved successfully'
        )
    
    except Exception as e:
        return error_response(
            InternalServerError(str(e)),
            500
        )


@merchants_bp.route('/<merchant_id>', methods=['GET'])
def get_merchant(merchant_id):
    """Get single merchant profile"""
    try:
        merchant = Merchant.query.filter_by(merchant_id=merchant_id).first()
        if not merchant:
            return error_response(
                NotFoundError('Merchant not found', 'Merchant'),
                404
            )
        
        return success_response(merchant.to_dict(), 'Merchant retrieved successfully')
    
    except Exception as e:
        return error_response(
            InternalServerError(str(e)),
            500
        )


@merchants_bp.route('', methods=['POST'])
def create_merchant():
    """Create or update merchant profile"""
    try:
        data = request.get_json()
        
        if not data:
            return error_response(
                APIError('Request body required', error_type='MISSING_DATA'),
                400
            )
        
        # Validate required fields
        required_fields = ['merchant_id', 'merchant_name', 'mcc']
        missing = [f for f in required_fields if not data.get(f)]
        
        if missing:
            return error_response(
                APIError(f'Missing required fields: {", ".join(missing)}',
                        error_type='MISSING_FIELDS'),
                400
            )
        
        # Validate MCC
        if not MerchantValidator.validate_mcc(data['mcc']):
            return error_response(
                APIError('Invalid MCC code', error_type='INVALID_MCC'),
                400
            )
        
        # Check if merchant exists
        merchant = Merchant.query.filter_by(merchant_id=data['merchant_id']).first()
        
        if merchant:
            # Update
            merchant.merchant_name = data.get('merchant_name', merchant.merchant_name)
            merchant.mcc = data.get('mcc', merchant.mcc)
            merchant.industry = data.get('industry', merchant.industry)
            merchant.annual_volume = Decimal(str(data['annual_volume'])) if data.get('annual_volume') else merchant.annual_volume
            merchant.average_ticket = Decimal(str(data['average_ticket'])) if data.get('average_ticket') else merchant.average_ticket
            merchant.current_rate = Decimal(str(data['current_rate'])) if data.get('current_rate') else merchant.current_rate
        else:
            # Create
            merchant = Merchant(
                merchant_id=data['merchant_id'],
                merchant_name=data['merchant_name'],
                mcc=data['mcc'],
                industry=data.get('industry'),
                annual_volume=Decimal(str(data['annual_volume'])) if data.get('annual_volume') else None,
                average_ticket=Decimal(str(data['average_ticket'])) if data.get('average_ticket') else None,
                current_rate=Decimal(str(data['current_rate'])) if data.get('current_rate') else None,
            )
        
        db.session.add(merchant)
        db.session.commit()
        
        return success_response(merchant.to_dict(), 'Merchant saved successfully', 201)
    
    except Exception as e:
        db.session.rollback()
        return error_response(
            InternalServerError(str(e)),
            500
        )


# ==================== MCC ROUTES ====================

@mccs_bp.route('', methods=['GET'])
def list_mccs():
    """Get all MCC codes"""
    try:
        mccs = MCCService.get_all_mccs()
        return success_response(mccs, 'MCC codes retrieved successfully')
    
    except Exception as e:
        return error_response(
            InternalServerError(str(e)),
            500
        )


@mccs_bp.route('/search', methods=['GET'])
def search_mccs():
    """Search MCC codes by code or description"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query or len(query) < 2:
            return error_response(
                APIError('Query must be at least 2 characters', error_type='INVALID_QUERY'),
                400
            )
        
        results = MCCService.search_mccs(query)
        return success_response(results, f'Found {len(results)} MCC codes')
    
    except Exception as e:
        return error_response(
            InternalServerError(str(e)),
            500
        )


@mccs_bp.route('/<mcc_code>', methods=['GET'])
def get_mcc(mcc_code):
    """Get single MCC by code"""
    try:
        mcc = MCCService.get_mcc_by_code(mcc_code)
        if not mcc:
            return error_response(
                NotFoundError('MCC code not found', 'MCC'),
                404
            )
        
        return success_response(mcc, 'MCC retrieved successfully')
    
    except Exception as e:
        return error_response(
            InternalServerError(str(e)),
            500
        )


# Error handlers
def register_error_handlers(app):
    """Register error handlers with the Flask app"""
    
    @app.errorhandler(APIError)
    def handle_api_error(error):
        return error_response(error)
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return error_response(error)
    
    @app.errorhandler(404)
    def handle_not_found(error):
        return error_response(
            NotFoundError('Resource not found'),
            404
        )
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        return error_response(
            InternalServerError('Internal server error'),
            500
        )
