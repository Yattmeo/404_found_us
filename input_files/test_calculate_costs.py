import pytest
import pandas as pd
import json
import os
from unittest.mock import patch, mock_open, MagicMock
from calculate_costs import (
    normalize_card_type,
    find_matching_card_fee,
    find_matching_network_fee,
    calculate_cost,
    process_transactions,
    load_fee_structure,
    load_network_fee_structure
)


# --- FIXTURES ---

@pytest.fixture
def sample_mastercard_fee_structure():
    """Sample Mastercard fee structure for testing"""
    return [
        {
            "card_type": "Credit",
            "product": "Industry Fee Program (All)",
            "mcc": 5499,
            "percent_rate": 1.65,
            "fixed_rate": 0.10,
            "max_fee": None
        },
        {
            "card_type": "Debit",
            "product": "Industry Fee Program (All)",
            "mcc": 5499,
            "percent_rate": 0.55,
            "fixed_rate": 0.22,
            "max_fee": None
        },
        {
            "card_type": "Prepaid",
            "product": "Industry Fee Program (All)",
            "mcc": 5499,
            "percent_rate": 0.80,
            "fixed_rate": 0.15,
            "max_fee": None
        },
        {
            "card_type": "Credit",
            "product": "Small Ticket Fee Program (All)",
            "mcc": None,
            "percent_rate": 1.50,
            "fixed_rate": 0.04,
            "max_fee": None
        },
        {
            "card_type": "Debit",
            "product": "Small Ticket Fee Program (All)",
            "mcc": None,
            "percent_rate": 1.50,
            "fixed_rate": 0.04,
            "max_fee": None
        }
    ]


@pytest.fixture
def sample_visa_fee_structure():
    """Sample Visa fee structure for testing"""
    return [
        {
            "card_type": "Credit",
            "product": "Industry Fee Program (All)",
            "mcc": 5499,
            "percent_rate": 1.70,
            "fixed_rate": 0.10,
            "max_fee": None
        },
        {
            "card_type": "Debit",
            "product": "Industry Fee Program (All)",
            "mcc": 5499,
            "percent_rate": 0.60,
            "fixed_rate": 0.21,
            "max_fee": None
        }
    ]


@pytest.fixture
def sample_mastercard_network_structure():
    """Sample Mastercard network fee structure"""
    return [
        {
            "fee_name": "Acquirer Brand Volume",
            "percent_rate": 0.13,
            "fixed_rate": 0
        },
        {
            "fee_name": "Transactions => 1000 USD",
            "percent_rate": 0.01,
            "fixed_rate": 0
        },
        {
            "fee_name": "Account Status Inquiry Service Fee",
            "percent_rate": 0,
            "fixed_rate": 0.025
        }
    ]


@pytest.fixture
def sample_visa_network_structure():
    """Sample Visa network fee structure"""
    return [
        {
            "fee_name": "Acquirer Service Fee",
            "card_type": "Credit",
            "percent_rate": 0.14,
            "fixed_rate": 0
        },
        {
            "fee_name": "Acquirer Processing Fee",
            "card_type": "Credit",
            "percent_rate": 0,
            "fixed_rate": 0.0195
        },
        {
            "fee_name": "Acquirer Service Fee",
            "card_type": "Debit",
            "percent_rate": 0.13,
            "fixed_rate": 0
        },
        {
            "fee_name": "Acquirer Processing Fee",
            "card_type": "Debit",
            "percent_rate": 0,
            "fixed_rate": 0.0195
        }
    ]


@pytest.fixture
def sample_transactions_df():
    """Sample transaction DataFrame for testing"""
    return pd.DataFrame({
        'transaction_id': ['TXN001', 'TXN002', 'TXN003', 'TXN004', 'TXN005', 'TXN006'],
        'card_brand': ['Mastercard', 'Visa', 'Mastercard', 'Visa', 'Mastercard', 'Amex'],
        'card_type': ['Credit', 'Debit', 'Debit (Prepaid)', 'Credit', 'Debit', 'Credit'],
        'transaction_type': ['Card Present', 'Card Present', 'E-commerce', 'Card Present', 'E-commerce', 'Card Present'],
        'amount': [100.00, 50.00, 3.50, 1500.00, -25.00, 75.00]
    })


# --- UNIT TESTS ---

class TestNormalizeCardType:
    """Tests for normalize_card_type function"""
    
    def test_normalize_prepaid(self):
        """Test that 'Debit (Prepaid)' is normalized to 'Prepaid'"""
        assert normalize_card_type("Debit (Prepaid)") == "Prepaid"
    
    def test_other_types_unchanged(self):
        """Test that other card types remain unchanged"""
        assert normalize_card_type("Credit") == "Credit"
        assert normalize_card_type("Debit") == "Debit"
        assert normalize_card_type("Business Credit") == "Business Credit"


class TestCalculateCost:
    """Tests for calculate_cost function"""
    
    def test_basic_calculation(self):
        """Test basic cost calculation with percent and fixed rate"""
        # 100 * 1.65% + 0.10 = 1.65 + 0.10 = 1.75
        result = calculate_cost(100.00, 1.65, 0.10)
        assert result == 1.75
    
    def test_small_amount(self):
        """Test calculation with small amount"""
        # 3.50 * 1.50% + 0.04 = 0.0525 + 0.04 = 0.0925
        result = calculate_cost(3.50, 1.50, 0.04)
        assert result == 0.0925
    
    def test_large_amount(self):
        """Test calculation with large amount"""
        # 1500 * 1.65% + 0.10 = 24.75 + 0.10 = 24.85
        result = calculate_cost(1500.00, 1.65, 0.10)
        assert result == 24.85
    
    def test_with_max_fee_cap(self):
        """Test that max_fee cap is applied correctly"""
        # Without cap: 1000 * 2.0% + 0.50 = 20.50
        # With cap of 10.00: should return 10.00
        result = calculate_cost(1000.00, 2.0, 0.50, max_fee=10.00)
        assert result == 10.00
    
    def test_without_max_fee_cap(self):
        """Test calculation when cost is below max_fee"""
        # 100 * 2.0% + 0.50 = 2.50 (below max_fee of 10.00)
        result = calculate_cost(100.00, 2.0, 0.50, max_fee=10.00)
        assert result == 2.50
    
    def test_zero_amount(self):
        """Test calculation with zero amount"""
        result = calculate_cost(0, 1.65, 0.10)
        assert result == 0.10
    
    def test_rounding(self):
        """Test that result is rounded to 4 decimal places"""
        # 33.33 * 1.234% + 0.056 = 0.4113222 + 0.056 = 0.4673222
        result = calculate_cost(33.33, 1.234, 0.056)
        assert result == 0.4673


class TestLoadFeeStructure:
    """Tests for load_fee_structure function"""
    
    @patch('builtins.open', new_callable=mock_open, read_data='[{"test": "data"}]')
    @patch('os.path.join')
    def test_load_mastercard(self, mock_join, mock_file):
        """Test loading Mastercard fee structure"""
        mock_join.return_value = "fake_path"
        result = load_fee_structure("Mastercard")
        assert result == [{"test": "data"}]
        mock_file.assert_called_once()
    
    @patch('builtins.open', new_callable=mock_open, read_data='[{"test": "visa"}]')
    @patch('os.path.join')
    def test_load_visa(self, mock_join, mock_file):
        """Test loading Visa fee structure"""
        mock_join.return_value = "fake_path"
        result = load_fee_structure("Visa")
        assert result == [{"test": "visa"}]
        mock_file.assert_called_once()
    
    def test_load_amex_returns_none(self):
        """Test that Amex returns None (no structure available)"""
        result = load_fee_structure("Amex")
        assert result is None
    
    def test_load_unknown_brand_returns_none(self):
        """Test that unknown brand returns None"""
        result = load_fee_structure("Unknown")
        assert result is None


class TestLoadNetworkFeeStructure:
    """Tests for load_network_fee_structure function"""
    
    @patch('builtins.open', new_callable=mock_open, read_data='[{"test": "network"}]')
    @patch('os.path.join')
    def test_load_mastercard_network(self, mock_join, mock_file):
        """Test loading Mastercard network fee structure"""
        mock_join.return_value = "fake_path"
        result = load_network_fee_structure("Mastercard")
        assert result == [{"test": "network"}]
        mock_file.assert_called_once()
    
    @patch('builtins.open', new_callable=mock_open, read_data='[{"test": "visa_network"}]')
    @patch('os.path.join')
    def test_load_visa_network(self, mock_join, mock_file):
        """Test loading Visa network fee structure"""
        mock_join.return_value = "fake_path"
        result = load_network_fee_structure("Visa")
        assert result == [{"test": "visa_network"}]
        mock_file.assert_called_once()
    
    def test_load_amex_network_returns_none(self):
        """Test that Amex network returns None"""
        result = load_network_fee_structure("Amex")
        assert result is None


class TestFindMatchingCardFee:
    """Tests for find_matching_card_fee function"""
    
    @patch('calculate_costs.load_fee_structure')
    def test_industry_program_match(self, mock_load, sample_mastercard_fee_structure):
        """Test matching for Industry Fee Program (amount >= $5)"""
        mock_load.return_value = sample_mastercard_fee_structure
        
        result = find_matching_card_fee("Mastercard", "Credit", 5499, 100.00)
        
        assert result is not None
        assert result["card_type"] == "Credit"
        assert result["product"] == "Industry Fee Program (All)"
        assert result["mcc"] == 5499
        assert result["percent_rate"] == 1.65
    
    @patch('calculate_costs.load_fee_structure')
    def test_small_ticket_program_match(self, mock_load, sample_mastercard_fee_structure):
        """Test matching for Small Ticket Fee Program (amount < $5)"""
        mock_load.return_value = sample_mastercard_fee_structure
        
        result = find_matching_card_fee("Mastercard", "Credit", 5499, 3.50)
        
        assert result is not None
        assert result["card_type"] == "Credit"
        assert result["product"] == "Small Ticket Fee Program (All)"
        assert result["mcc"] is None
        assert result["percent_rate"] == 1.50
    
    @patch('calculate_costs.load_fee_structure')
    def test_prepaid_card_normalization(self, mock_load, sample_mastercard_fee_structure):
        """Test that 'Debit (Prepaid)' is normalized to 'Prepaid'"""
        mock_load.return_value = sample_mastercard_fee_structure
        
        result = find_matching_card_fee("Mastercard", "Debit (Prepaid)", 5499, 100.00)
        
        assert result is not None
        assert result["card_type"] == "Prepaid"
        assert result["percent_rate"] == 0.80
    
    @patch('calculate_costs.load_fee_structure')
    def test_no_match_found(self, mock_load, sample_mastercard_fee_structure):
        """Test when no matching fee structure is found"""
        mock_load.return_value = sample_mastercard_fee_structure
        
        result = find_matching_card_fee("Mastercard", "Credit", 9999, 100.00)
        
        assert result is None
    
    @patch('calculate_costs.load_fee_structure')
    def test_amex_no_structure(self, mock_load):
        """Test Amex returns None (no fee structure)"""
        mock_load.return_value = None
        
        result = find_matching_card_fee("Amex", "Credit", 5499, 100.00)
        
        assert result is None
    
    @patch('calculate_costs.load_fee_structure')
    def test_boundary_amount_five_dollars(self, mock_load, sample_mastercard_fee_structure):
        """Test boundary condition at exactly $5.00"""
        mock_load.return_value = sample_mastercard_fee_structure
        
        # Exactly $5 should use Industry Program
        result = find_matching_card_fee("Mastercard", "Credit", 5499, 5.00)
        
        assert result is not None
        assert result["product"] == "Industry Fee Program (All)"


class TestFindMatchingNetworkFee:
    """Tests for find_matching_network_fee function"""
    
    @patch('calculate_costs.load_network_fee_structure')
    def test_mastercard_network_fee_standard(self, mock_load, sample_mastercard_network_structure):
        """Test Mastercard network fee for standard transaction (< $1000)"""
        mock_load.return_value = sample_mastercard_network_structure
        
        result = find_matching_network_fee("Mastercard", "Credit", 100.00)
        
        assert result is not None
        assert result["percent_rate"] == 0.13  # Base assessment only
        assert result["fixed_rate"] == 0.025   # Inquiry service fee
    
    @patch('calculate_costs.load_network_fee_structure')
    def test_mastercard_network_fee_large_transaction(self, mock_load, sample_mastercard_network_structure):
        """Test Mastercard network fee for large transaction (>= $1000)"""
        mock_load.return_value = sample_mastercard_network_structure
        
        result = find_matching_network_fee("Mastercard", "Credit", 1500.00)
        
        assert result is not None
        assert result["percent_rate"] == 0.14  # Base (0.13) + large txn (0.01)
        assert result["fixed_rate"] == 0.025
    
    @patch('calculate_costs.load_network_fee_structure')
    def test_mastercard_boundary_1000_dollars(self, mock_load, sample_mastercard_network_structure):
        """Test boundary condition at exactly $1000"""
        mock_load.return_value = sample_mastercard_network_structure
        
        result = find_matching_network_fee("Mastercard", "Credit", 1000.00)
        
        assert result is not None
        assert result["percent_rate"] == 0.14  # Should include large txn fee
    
    @patch('calculate_costs.load_network_fee_structure')
    def test_visa_network_fee_credit(self, mock_load, sample_visa_network_structure):
        """Test Visa network fee for credit card"""
        mock_load.return_value = sample_visa_network_structure
        
        result = find_matching_network_fee("Visa", "Credit", 100.00)
        
        assert result is not None
        assert result["percent_rate"] == 0.14
        assert result["fixed_rate"] == 0.0195
    
    @patch('calculate_costs.load_network_fee_structure')
    def test_visa_network_fee_debit(self, mock_load, sample_visa_network_structure):
        """Test Visa network fee for debit card"""
        mock_load.return_value = sample_visa_network_structure
        
        result = find_matching_network_fee("Visa", "Debit", 100.00)
        
        assert result is not None
        assert result["percent_rate"] == 0.13
        assert result["fixed_rate"] == 0.0195
    
    @patch('calculate_costs.load_network_fee_structure')
    def test_visa_prepaid_treated_as_debit(self, mock_load, sample_visa_network_structure):
        """Test that Visa Prepaid is treated as Debit for network fees"""
        mock_load.return_value = sample_visa_network_structure
        
        result = find_matching_network_fee("Visa", "Debit (Prepaid)", 100.00)
        
        assert result is not None
        assert result["percent_rate"] == 0.13  # Debit rate
        assert result["fixed_rate"] == 0.0195
    
    @patch('calculate_costs.load_network_fee_structure')
    def test_amex_network_returns_none(self, mock_load):
        """Test Amex network returns None"""
        mock_load.return_value = None
        
        result = find_matching_network_fee("Amex", "Credit", 100.00)
        
        assert result is None


class TestProcessTransactions:
    """Tests for process_transactions function"""
    
    @patch('calculate_costs.find_matching_network_fee')
    @patch('calculate_costs.find_matching_card_fee')
    @patch('pandas.read_csv')
    def test_process_valid_transactions(self, mock_read_csv, mock_card_fee, mock_network_fee, 
                                       sample_transactions_df):
        """Test processing of valid transactions"""
        mock_read_csv.return_value = sample_transactions_df
        
        # Mock card fee response
        mock_card_fee.return_value = {
            'product': 'Industry Fee Program (All)',
            'percent_rate': 1.65,
            'fixed_rate': 0.10,
            'max_fee': None
        }
        
        # Mock network fee response
        mock_network_fee.return_value = {
            'percent_rate': 0.13,
            'fixed_rate': 0.025
        }
        
        result_df = process_transactions('fake_path.csv', 5499)
        
        # Check that new columns are added
        assert 'mcc' in result_df.columns
        assert 'card_cost' in result_df.columns
        assert 'network_cost' in result_df.columns
        assert 'total_cost' in result_df.columns
        assert 'match_found' in result_df.columns
        
        # Check MCC is set correctly
        assert all(result_df['mcc'] == 5499)
        
        # Check that costs are calculated for positive amounts
        positive_amounts = result_df[result_df['amount'] > 0]
        assert all(positive_amounts['card_cost'] > 0)
        assert all(positive_amounts['network_cost'] > 0)
    
    @patch('calculate_costs.find_matching_network_fee')
    @patch('calculate_costs.find_matching_card_fee')
    @patch('pandas.read_csv')
    def test_process_negative_amount_refund(self, mock_read_csv, mock_card_fee, mock_network_fee,
                                            sample_transactions_df):
        """Test that negative amounts (refunds) have zero costs"""
        mock_read_csv.return_value = sample_transactions_df
        
        # Mock fee structures (not actually used for negative amounts, but needed for positive ones)
        mock_card_fee.return_value = {
            'product': 'Industry Fee Program (All)',
            'percent_rate': 1.65,
            'fixed_rate': 0.10,
            'max_fee': None
        }
        mock_network_fee.return_value = {
            'percent_rate': 0.13,
            'fixed_rate': 0.025
        }
        
        result_df = process_transactions('fake_path.csv', 5499)
        
        # Find the refund transaction (TXN005 with -25.00)
        refund = result_df[result_df['transaction_id'] == 'TXN005'].iloc[0]
        
        assert refund['card_cost'] == 0.0
        assert refund['network_cost'] == 0.0
        assert refund['total_cost'] == 0.0
        assert refund['match_found'] == False
    
    @patch('calculate_costs.find_matching_network_fee')
    @patch('calculate_costs.find_matching_card_fee')
    @patch('pandas.read_csv')
    def test_process_no_card_fee_match(self, mock_read_csv, mock_card_fee, mock_network_fee,
                                       sample_transactions_df):
        """Test handling when no card fee match is found"""
        mock_read_csv.return_value = sample_transactions_df
        mock_card_fee.return_value = None  # No match
        mock_network_fee.return_value = {
            'percent_rate': 0.13,
            'fixed_rate': 0.025
        }
        
        result_df = process_transactions('fake_path.csv', 5499)
        
        # Check that unmatched transactions have card_cost = 0 and match_found = False
        unmatched = result_df[result_df['amount'] > 0].iloc[0]
        assert unmatched['card_cost'] == 0.0
        assert unmatched['match_found'] == False
    
    @patch('calculate_costs.find_matching_network_fee')
    @patch('calculate_costs.find_matching_card_fee')
    @patch('pandas.read_csv')
    def test_process_total_cost_calculation(self, mock_read_csv, mock_card_fee, mock_network_fee,
                                            sample_transactions_df):
        """Test that total_cost is sum of card_cost and network_cost"""
        mock_read_csv.return_value = sample_transactions_df
        
        mock_card_fee.return_value = {
            'product': 'Industry Fee Program (All)',
            'percent_rate': 1.65,
            'fixed_rate': 0.10,
            'max_fee': None
        }
        
        mock_network_fee.return_value = {
            'percent_rate': 0.13,
            'fixed_rate': 0.025
        }
        
        result_df = process_transactions('fake_path.csv', 5499)
        
        # Check first valid transaction (TXN001: $100)
        txn = result_df[result_df['transaction_id'] == 'TXN001'].iloc[0]
        
        # Card cost: 100 * 1.65% + 0.10 = 1.75
        # Network cost: 100 * 0.13% + 0.025 = 0.155
        # Total: 1.75 + 0.155 = 1.905
        assert txn['card_cost'] == 1.75
        assert txn['network_cost'] == 0.155
        assert txn['total_cost'] == 1.905


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_calculate_cost_negative_amount(self):
        """Test calculate_cost with negative amount"""
        # This should technically still calculate (refunds might need processing)
        # -100 * 1.65% + 0.10 = -1.65 + 0.10 = -1.55
        result = calculate_cost(-100.00, 1.65, 0.10)
        assert result == -1.55
    
    @patch('calculate_costs.load_fee_structure')
    def test_find_matching_card_fee_zero_amount(self, mock_load, sample_mastercard_fee_structure):
        """Test find_matching_card_fee with zero amount"""
        mock_load.return_value = sample_mastercard_fee_structure
        
        # Zero should use Small Ticket (< $5)
        result = find_matching_card_fee("Mastercard", "Credit", 5499, 0.0)
        
        assert result is not None
        assert result["product"] == "Small Ticket Fee Program (All)"
    
    def test_normalize_card_type_empty_string(self):
        """Test normalize_card_type with empty string"""
        result = normalize_card_type("")
        assert result == ""
    
    def test_normalize_card_type_none(self):
        """Test normalize_card_type with None"""
        result = normalize_card_type(None)
        assert result is None


class TestIntegration:
    """Integration tests combining multiple functions"""
    
    @patch('calculate_costs.load_network_fee_structure')
    @patch('calculate_costs.load_fee_structure')
    def test_full_cost_calculation_mastercard_credit(self, mock_card_load, mock_network_load,
                                                      sample_mastercard_fee_structure,
                                                      sample_mastercard_network_structure):
        """Integration test: Calculate full cost for Mastercard Credit transaction"""
        mock_card_load.return_value = sample_mastercard_fee_structure
        mock_network_load.return_value = sample_mastercard_network_structure
        
        amount = 100.00
        
        # Find card fee
        card_fee = find_matching_card_fee("Mastercard", "Credit", 5499, amount)
        card_cost = calculate_cost(amount, card_fee['percent_rate'], 
                                   card_fee['fixed_rate'], card_fee.get('max_fee'))
        
        # Find network fee
        network_fee = find_matching_network_fee("Mastercard", "Credit", amount)
        network_cost = calculate_cost(amount, network_fee['percent_rate'], 
                                      network_fee['fixed_rate'])
        
        total_cost = card_cost + network_cost
        
        # Expected: Card (100*1.65% + 0.10) + Network (100*0.13% + 0.025)
        # = 1.75 + 0.155 = 1.905
        assert card_cost == 1.75
        assert network_cost == 0.155
        assert total_cost == 1.905
    
    @patch('calculate_costs.load_network_fee_structure')
    @patch('calculate_costs.load_fee_structure')
    def test_full_cost_calculation_small_ticket(self, mock_card_load, mock_network_load,
                                                 sample_mastercard_fee_structure,
                                                 sample_mastercard_network_structure):
        """Integration test: Small ticket transaction (< $5)"""
        mock_card_load.return_value = sample_mastercard_fee_structure
        mock_network_load.return_value = sample_mastercard_network_structure
        
        amount = 3.50
        
        card_fee = find_matching_card_fee("Mastercard", "Credit", 5499, amount)
        assert card_fee['product'] == "Small Ticket Fee Program (All)"
        
        card_cost = calculate_cost(amount, card_fee['percent_rate'], 
                                   card_fee['fixed_rate'], card_fee.get('max_fee'))
        
        # Expected: 3.50 * 1.50% + 0.04 = 0.0525 + 0.04 = 0.0925
        assert card_cost == 0.0925


# --- PARAMETRIZED TESTS ---

@pytest.mark.parametrize("card_type,expected", [
    ("Debit (Prepaid)", "Prepaid"),
    ("Credit", "Credit"),
    ("Debit", "Debit"),
    ("Business Credit", "Business Credit"),
])
def test_normalize_card_type_parametrized(card_type, expected):
    """Parametrized test for normalize_card_type"""
    assert normalize_card_type(card_type) == expected


@pytest.mark.parametrize("amount,percent_rate,fixed_rate,expected", [
    (100.00, 1.65, 0.10, 1.75),
    (50.00, 0.55, 0.22, 0.495),
    (3.50, 1.50, 0.04, 0.0925),
    (1500.00, 1.65, 0.10, 24.85),
    (0, 1.65, 0.10, 0.10),
])
def test_calculate_cost_parametrized(amount, percent_rate, fixed_rate, expected):
    """Parametrized test for calculate_cost"""
    assert calculate_cost(amount, percent_rate, fixed_rate) == expected


@pytest.mark.parametrize("brand,expected_result", [
    ("Mastercard", "data_returned"),
    ("Visa", "data_returned"),
    ("Amex", None),
    ("Unknown", None),
])
def test_load_fee_structure_brands(brand, expected_result):
    """Parametrized test for different card brands"""
    with patch('builtins.open', mock_open(read_data='[{"test": "data"}]')), \
         patch('os.path.join', return_value="fake_path"):
        result = load_fee_structure(brand)
        if expected_result is None:
            assert result is None
        else:
            assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
