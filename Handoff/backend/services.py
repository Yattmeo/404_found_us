"""
Services for business logic
"""
import csv
import io
from decimal import Decimal
from validators import TransactionValidator, MerchantValidator
from modules.cost_calculation.service import CostCalculationService

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

    # Default quote margin applied when caller does not provide a current/quoted rate.
    DEFAULT_QUOTE_MARGIN_RATE = 0.003  # 30 bps

    @staticmethod
    def _normalize_card_brand(value):
        text = str(value or '').strip().lower()
        if text == 'visa':
            return 'Visa'
        if text in ('mastercard', 'master card'):
            return 'Mastercard'
        return None

    @staticmethod
    def _normalize_card_type(value):
        text = str(value or '').strip().lower()
        mapping = {
            'credit': 'Credit',
            'super premium credit': 'Super Premium Credit',
            'debit': 'Debit',
            'prepaid': 'Prepaid',
            'debit (prepaid)': 'Prepaid',
        }
        return mapping.get(text)

    @staticmethod
    def _resolve_brand_type_from_tx(tx):
        raw_brand = tx.get('card_brand')
        raw_type = tx.get('card_type')

        brand = MerchantFeeCalculationService._normalize_card_brand(raw_brand)
        card_type = MerchantFeeCalculationService._normalize_card_type(raw_type)

        # Common CSV shape in this project uses card_type as brand (Visa/Mastercard).
        if brand is None:
            brand = MerchantFeeCalculationService._normalize_card_brand(raw_type)
        if card_type is None and brand is not None:
            card_type = 'Credit'

        return brand, card_type

    @staticmethod
    def _effective_rate_from_fees(amount, card_fee, network_fee):
        if amount <= 0:
            return None
        card_cost = 0.0
        network_cost = 0.0

        if card_fee:
            card_cost = CostCalculationService._calc_cost(
                amount,
                card_fee.get('percent_rate', 0.0),
                card_fee.get('fixed_rate', 0.0),
                card_fee.get('max_fee'),
            )
        if network_fee:
            network_cost = CostCalculationService._calc_cost(
                amount,
                network_fee.get('percent_rate', 0.0),
                network_fee.get('fixed_rate', 0.0),
            )

        return (card_cost + network_cost) / amount

    @staticmethod
    def estimate_base_cost_rate(mcc, transactions=None, avg_ticket=None, monthly_txn_count=None):
        """
        Estimate a baseline processing cost rate (decimal) strictly from cost_structure JSON data.
        """
        try:
            mcc_int = int(mcc)
        except (TypeError, ValueError):
            return None

        tx_rows = transactions or []
        total_cost = 0.0
        total_amount = 0.0

        for tx in tx_rows:
            amount = float(tx.get('amount', 0) or 0)
            if amount <= 0:
                continue

            brand, card_type = MerchantFeeCalculationService._resolve_brand_type_from_tx(tx)
            brand_candidates = [brand] if brand else ['Visa', 'Mastercard']
            type_candidates = [card_type] if card_type else ['Credit']

            scenario_rates = []
            for b in brand_candidates:
                for ctype in type_candidates:
                    card_fee = CostCalculationService._find_matching_card_fee(b, ctype, mcc_int, amount)
                    network_fee = CostCalculationService._find_matching_network_fee(b, ctype, amount)
                    rate = MerchantFeeCalculationService._effective_rate_from_fees(amount, card_fee, network_fee)
                    if rate is not None:
                        scenario_rates.append(rate)

            if scenario_rates:
                total_cost += amount * (sum(scenario_rates) / len(scenario_rates))
                total_amount += amount

        if total_amount > 0:
            return total_cost / total_amount

        # Aggregate fallback: derive from JSON entries for this MCC at a representative ticket size.
        representative_amount = float(avg_ticket or 100.0)
        if representative_amount <= 0:
            representative_amount = 100.0

        blended_rates = []
        for brand in ('Visa', 'Mastercard'):
            fee_structure = CostCalculationService._load_fee_structure(brand) or []
            product = 'Small Ticket Fee Program (All)' if representative_amount < 5.0 else 'Industry Fee Program (All)'
            rows = [
                row for row in fee_structure
                if row.get('product') == product and (row.get('mcc') == mcc_int if product.startswith('Industry') else True)
            ]
            for row in rows:
                ctype = row.get('card_type')
                if not ctype:
                    continue
                network_fee = CostCalculationService._find_matching_network_fee(brand, ctype, representative_amount)
                rate = MerchantFeeCalculationService._effective_rate_from_fees(representative_amount, row, network_fee)
                if rate is not None:
                    blended_rates.append(rate)

        if blended_rates:
            return sum(blended_rates) / len(blended_rates)

        return None

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
        
        # Derive baseline cost rate from JSON fee structures (card + network).
        base_cost_rate = MerchantFeeCalculationService.estimate_base_cost_rate(mcc, transactions=transactions)
        if base_cost_rate is None:
            return {'error': 'Unable to derive base cost rate from cost structure data'}
        if current_rate is None:
            current_rate = float(base_cost_rate) + MerchantFeeCalculationService.DEFAULT_QUOTE_MARGIN_RATE

        margin_rate = float(current_rate) - float(base_cost_rate)
        margin_bps = int(round(margin_rate * 10000))
        
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
            'base_cost_rate': float(base_cost_rate),
            'applied_rate': current_rate,
            'margin_rate': float(margin_rate),
            'margin_bps': margin_bps,
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
        
        # Quoted rate should be cost + margin from JSON fee structures.
        base_rate = MerchantFeeCalculationService.estimate_base_cost_rate(mcc, transactions=transactions)
        if base_rate is None:
            return {'error': 'Unable to derive base cost rate from cost structure data'}
        base_cost_rate = Decimal(str(base_rate))
        margin_rate = Decimal(str(desired_margin))
        required_rate = base_cost_rate + margin_rate
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
            'base_cost_rate': float(base_cost_rate),
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
