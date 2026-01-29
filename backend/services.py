"""
Services for business logic
"""
import csv
import io
from decimal import Decimal
from validators import TransactionValidator, MerchantValidator

class DataProcessingService:
    """Service to process and validate uploaded data"""
    
    @staticmethod
    def parse_csv_file(file_content):
        """
        Parse CSV file content
        Returns: (headers, rows, errors)
        """
        try:
            # Decode if bytes
            if isinstance(file_content, bytes):
                file_content = file_content.decode('utf-8')
            
            csv_reader = csv.DictReader(io.StringIO(file_content))
            
            if not csv_reader.fieldnames:
                return None, [], [{'error': 'CSV file is empty'}]
            
            # Normalize headers
            headers = [h.strip().lower() if h else '' for h in csv_reader.fieldnames]
            
            # Validate headers
            is_valid, missing = TransactionValidator.validate_headers(headers)
            if not is_valid:
                return headers, [], [{
                    'row': 0,
                    'column': ', '.join(missing),
                    'error': f'Missing required columns: {", ".join(missing)}',
                    'error_type': 'MISSING_COLUMNS'
                }]
            
            # Parse rows
            rows = []
            errors = []
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
                # Normalize row data
                normalized_row = {k.lower().strip(): v.strip() if v else '' for k, v in row.items()}
                
                # Validate row
                is_valid_row, row_errors = TransactionValidator.validate_row(normalized_row, row_num)
                
                if is_valid_row:
                    rows.append(normalized_row)
                else:
                    errors.extend(row_errors)
            
            return headers, rows, errors
            
        except Exception as e:
            return None, [], [{'error': f'Error parsing CSV: {str(e)}'}]

    @staticmethod
    def parse_excel_file(file_content, filename):
        """
        Parse Excel file content
        Returns: (headers, rows, errors)
        """
        try:
            import openpyxl
            
            # Load workbook
            workbook = openpyxl.load_workbook(io.BytesIO(file_content))
            worksheet = workbook.active
            
            # Get headers from first row
            headers = [cell.value for cell in worksheet[1]]
            headers = [str(h).strip().lower() if h else '' for h in headers]
            
            # Validate headers
            is_valid, missing = TransactionValidator.validate_headers(headers)
            if not is_valid:
                return headers, [], [{
                    'row': 0,
                    'column': ', '.join(missing),
                    'error': f'Missing required columns: {", ".join(missing)}',
                    'error_type': 'MISSING_COLUMNS'
                }]
            
            # Parse data rows
            rows = []
            errors = []
            for row_num, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
                # Create row dict
                row_data = {headers[i]: str(row[i]).strip() if row[i] else '' 
                           for i in range(len(headers))}
                
                # Validate row
                is_valid_row, row_errors = TransactionValidator.validate_row(row_data, row_num)
                
                if is_valid_row:
                    rows.append(row_data)
                else:
                    errors.extend(row_errors)
            
            return headers, rows, errors
            
        except Exception as e:
            return None, [], [{'error': f'Error parsing Excel: {str(e)}'}]


class MerchantFeeCalculationService:
    """Service for merchant fee calculations"""
    
    # Standard MCC-based fee rates
    MCC_RATES = {
        '5812': {'description': 'Eating Places and Restaurants', 'base_rate': 0.029, 'fixed_fee': 0.30},
        '5411': {'description': 'Grocery Stores', 'base_rate': 0.020, 'fixed_fee': 0.00},
        '5541': {'description': 'Service Stations', 'base_rate': 0.025, 'fixed_fee': 0.00},
        '5311': {'description': 'Department Stores', 'base_rate': 0.023, 'fixed_fee': 0.15},
        '7011': {'description': 'Hotels and Motels', 'base_rate': 0.028, 'fixed_fee': 0.25},
    }

    @staticmethod
    def calculate_current_rates(transactions, mcc, current_rate=None, fixed_fee=0.30, minimum_fee=0.00):
        """
        Calculate fees based on current merchant rates
        
        Args:
            transactions: List of transaction dictionaries
            mcc: Merchant Category Code
            current_rate: Current interchange rate (or use MCC default)
            fixed_fee: Fixed fee per transaction
            minimum_fee: Minimum fee threshold
        
        Returns: Dictionary with calculations
        """
        if not transactions:
            return {'error': 'No transactions provided'}
        
        # Get base rate from MCC if not provided
        if current_rate is None:
            mcc_data = MerchantFeeCalculationService.MCC_RATES.get(mcc, {})
            current_rate = mcc_data.get('base_rate', 0.025)
        
        total_volume = Decimal('0')
        total_fees = Decimal('0')
        transaction_count = len(transactions)
        
        try:
            for tx in transactions:
                amount = Decimal(str(tx.get('amount', 0)))
                total_volume += amount
                
                # Calculate fee: (amount * rate) + fixed_fee, minimum of minimum_fee
                fee = (amount * Decimal(str(current_rate))) + Decimal(str(fixed_fee))
                fee = max(fee, Decimal(str(minimum_fee)))
                total_fees += fee
        except Exception as e:
            return {'error': f'Error calculating fees: {str(e)}'}
        
        # Calculate metrics
        effective_rate = (total_fees / total_volume) if total_volume > 0 else Decimal('0')
        average_ticket = total_volume / Decimal(str(transaction_count)) if transaction_count > 0 else Decimal('0')
        
        return {
            'success': True,
            'transaction_count': transaction_count,
            'total_volume': float(total_volume),
            'total_fees': float(total_fees),
            'effective_rate': float(effective_rate),
            'average_ticket': float(average_ticket),
            'mcc': mcc,
            'applied_rate': current_rate,
            'fixed_fee': fixed_fee,
            'minimum_fee': minimum_fee,
        }

    @staticmethod
    def calculate_desired_margin(transactions, mcc, desired_margin=0.015, minimum_fee=0.30):
        """
        Calculate required rate to achieve desired profit margin
        
        Args:
            transactions: List of transaction dictionaries
            mcc: Merchant Category Code
            desired_margin: Target profit margin
            minimum_fee: Minimum fee threshold
        
        Returns: Dictionary with calculations and recommended rate
        """
        if not transactions:
            return {'error': 'No transactions provided'}
        
        total_volume = Decimal('0')
        transaction_count = len(transactions)
        
        try:
            for tx in transactions:
                amount = Decimal(str(tx.get('amount', 0)))
                total_volume += amount
        except Exception as e:
            return {'error': f'Error calculating margin: {str(e)}'}
        
        if total_volume <= 0:
            return {'error': 'Total transaction volume must be greater than zero'}
        
        # Calculate required rate
        required_rate = Decimal(str(desired_margin))
        average_ticket = total_volume / Decimal(str(transaction_count)) if transaction_count > 0 else Decimal('0')
        
        # Calculate estimated fees with required rate
        estimated_fees = (total_volume * required_rate) + (Decimal(str(minimum_fee)) * Decimal(str(transaction_count)))
        estimated_effective_rate = (estimated_fees / total_volume) if total_volume > 0 else Decimal('0')
        
        return {
            'success': True,
            'transaction_count': transaction_count,
            'total_volume': float(total_volume),
            'average_ticket': float(average_ticket),
            'desired_margin': desired_margin,
            'recommended_rate': float(required_rate),
            'estimated_total_fees': float(estimated_fees),
            'estimated_effective_rate': float(estimated_effective_rate),
            'mcc': mcc,
            'minimum_fee': minimum_fee,
        }


class MCCService:
    """Service for MCC (Merchant Category Code) operations"""
    
    MCC_LIST = [
        {'code': '5812', 'description': 'Eating Places and Restaurants'},
        {'code': '5411', 'description': 'Grocery Stores and Supermarkets'},
        {'code': '5541', 'description': 'Service Stations'},
        {'code': '5311', 'description': 'Department Stores'},
        {'code': '5912', 'description': 'Drug Stores and Pharmacies'},
        {'code': '5999', 'description': 'Miscellaneous Retail Stores'},
        {'code': '7011', 'description': 'Hotels, Motels, Resorts'},
        {'code': '5814', 'description': 'Fast Food Restaurants'},
        {'code': '5941', 'description': 'Sporting Goods Stores'},
        {'code': '5942', 'description': 'Book Stores'},
        {'code': '5944', 'description': 'Jewelry Stores'},
        {'code': '5945', 'description': 'Hobby, Toy, and Game Shops'},
        {'code': '7230', 'description': 'Barber and Beauty Shops'},
        {'code': '7298', 'description': 'Health and Beauty Spas'},
        {'code': '7372', 'description': 'Computer Programming Services'},
        {'code': '7512', 'description': 'Automobile Rental Agency'},
        {'code': '7523', 'description': 'Parking Lots and Garages'},
        {'code': '7832', 'description': 'Motion Picture Theaters'},
        {'code': '7922', 'description': 'Theatrical Producers and Ticket Agencies'},
        {'code': '7992', 'description': 'Golf Courses - Public'},
    ]

    @staticmethod
    def get_all_mccs():
        """Get all available MCC codes"""
        return MCCService.MCC_LIST

    @staticmethod
    def get_mcc_by_code(code):
        """Get MCC details by code"""
        for mcc in MCCService.MCC_LIST:
            if mcc['code'] == str(code):
                return mcc
        return None

    @staticmethod
    def search_mccs(query):
        """Search MCCs by code or description"""
        query_lower = str(query).lower()
        results = [
            mcc for mcc in MCCService.MCC_LIST
            if query_lower in mcc['code'] or query_lower in mcc['description'].lower()
        ]
        return results
