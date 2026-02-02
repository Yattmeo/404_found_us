import pandas as pd
import numpy as np
import json
import os
from pathlib import Path

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COST_STRUCTURE_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "cost_structure")
MASTERCARD_FEE_FILE = os.path.join(COST_STRUCTURE_DIR, "masterCard_Card.JSON")
VISA_FEE_FILE = os.path.join(COST_STRUCTURE_DIR, "visa_Card.JSON")
MASTERCARD_NETWORK_FILE = os.path.join(COST_STRUCTURE_DIR, "masterCard_Network.JSON")
VISA_NETWORK_FILE = os.path.join(COST_STRUCTURE_DIR, "visa_Network.JSON")

# --- HELPERS ---
def load_fee_structure(card_brand):
    """Load fee structure from JSON based on card brand"""
    if card_brand == "Mastercard":
        with open(MASTERCARD_FEE_FILE, 'r') as f:
            return json.load(f)
    elif card_brand == "Visa":
        with open(VISA_FEE_FILE, 'r') as f:
            return json.load(f)
    elif card_brand == "Amex":
        # No Amex fee structure available
        return None
    else:
        return None

def load_network_fee_structure(card_brand):
    """Load network fee structure from JSON based on card brand"""
    if card_brand == "Mastercard":
        with open(MASTERCARD_NETWORK_FILE, 'r') as f:
            return json.load(f)
    elif card_brand == "Visa":
        with open(VISA_NETWORK_FILE, 'r') as f:
            return json.load(f)
    elif card_brand == "Amex":
        # No Amex network fee structure available
        return None
    else:
        return None

def normalize_card_type(card_type):
    """Normalize card type from transaction data to match fee structure"""
    if card_type == "Debit (Prepaid)":
        return "Prepaid"
    return card_type

def find_matching_card_fee(card_brand, card_type, mcc, amount):
    """
    Find matching fee structure for a transaction.
    Logic order:
    1. Check card_brand (Mastercard/Visa/Amex)
    2. Check amount to determine product:
       - < $5: Small Ticket Fee Program
       - >= $5: Industry Fee Program (based on MCC)
    3. Match card_type
    """
    # Step 1: Check card brand and load appropriate fee structure
    fee_structure = load_fee_structure(card_brand)
    
    # If no fee structure (e.g., Amex), return None
    if fee_structure is None:
        return None
    
    # Step 2: Determine product based on amount
    if amount < 5.0:
        # Small Ticket Fee Program
        product = "Small Ticket Fee Program (All)"
        target_mcc = None
    else:
        # Industry Fee Program (based on MCC)
        product = "Industry Fee Program (All)"
        target_mcc = mcc
    
    # Step 3: Normalize card type and find matching fee
    normalized_card_type = normalize_card_type(card_type)
    
    for fee in fee_structure:
        if (fee["card_type"] == normalized_card_type and 
            fee["product"] == product and 
            fee["mcc"] == target_mcc):
            return fee
    
    # No match found
    return None

def find_matching_network_fee(card_brand, card_type, amount):
    """
    Find matching network fee structure for a transaction.
    Network fees are separate from card fees.
    
    For Mastercard:
    - All transactions: 0.13% + $0.025
    - Transactions >= $1000: 0.14% (0.13% + 0.01%) + $0.025
    
    For Visa:
    - Check card_type (Debit/Credit)
    - Apply assessment fee (percent_rate) + processing fee (fixed_rate)
    """
    network_structure = load_network_fee_structure(card_brand)
    
    # If no network structure (e.g., Amex), return None
    if network_structure is None:
        return None
    
    if card_brand == "Mastercard":
        # Read fees from JSON structure
        base_assessment_fee = None
        large_transaction_fee = None
        inquiry_service_fee = None
        
        for fee in network_structure:
            if "Acquirer Brand Volume" in fee["fee_name"]:
                base_assessment_fee = fee
            elif "Transactions => 1000 USD" in fee["fee_name"]:
                large_transaction_fee = fee
            elif "Account Status Inquiry Service Fee" in fee["fee_name"]:
                inquiry_service_fee = fee
        
        # Calculate percent_rate and fixed_rate
        percent_rate = base_assessment_fee["percent_rate"] if base_assessment_fee else 0
        fixed_rate = inquiry_service_fee["fixed_rate"] if inquiry_service_fee else 0
        
        # Additional fee for transactions >= $1000
        if amount >= 1000.0 and large_transaction_fee:
            percent_rate += large_transaction_fee["percent_rate"]
        
        return {
            "percent_rate": percent_rate,
            "fixed_rate": fixed_rate,
            "fee_name": "Mastercard Network Fees"
        }
    
    elif card_brand == "Visa":
        # Normalize card type
        normalized_card_type = normalize_card_type(card_type)
        if normalized_card_type == "Prepaid":
            normalized_card_type = "Debit"  # Treat prepaid as debit for network fees
        
        # Find assessment fee and processing fee
        assessment_fee = None
        processing_fee = None
        
        for fee in network_structure:
            if "Acquirer Service Fee" in fee["fee_name"]:
                if fee.get("card_type") == normalized_card_type:
                    assessment_fee = fee
            elif "Acquirer Processing Fee" in fee["fee_name"]:
                if fee.get("card_type") == normalized_card_type:
                    processing_fee = fee
        
        if assessment_fee and processing_fee:
            return {
                "percent_rate": assessment_fee["percent_rate"],
                "fixed_rate": processing_fee["fixed_rate"],
                "fee_name": "Visa Network Fees"
            }
    
    return None

def calculate_cost(amount, percent_rate, fixed_rate, max_fee=None):
    """Calculate transaction cost based on percent and fixed rates"""
    cost = (amount * percent_rate/100) + fixed_rate
    
    # Apply max_fee cap if specified
    if max_fee is not None:
        cost = min(cost, max_fee)
    
    return round(cost, 4)

def process_transactions(csv_path, mcc):
    """Process transactions and add cost calculation columns"""
    # Load data
    df = pd.read_csv(csv_path)
    
    # Initialize new columns
    df['mcc'] = mcc
    df['product'] = None
    df['percent_rate'] = None
    df['fixed_rate'] = None
    df['max_fee'] = None
    df['card_cost'] = None
    df['network_percent_rate'] = None
    df['network_fixed_rate'] = None
    df['network_cost'] = None
    df['total_cost'] = None
    df['match_found'] = True
    
    # Process each transaction
    for idx, row in df.iterrows():
        # Skip negative amounts (refunds) and zero amounts
        if row['amount'] <= 0:
            df.at[idx, 'card_cost'] = 0.0
            df.at[idx, 'network_cost'] = 0.0
            df.at[idx, 'total_cost'] = 0.0
            df.at[idx, 'match_found'] = False
            continue
        
        # Find matching card fee structure (card_brand is checked first)
        card_fee = find_matching_card_fee(row['card_brand'], row['card_type'], mcc, row['amount'])
        
        # Calculate card cost
        if card_fee:
            df.at[idx, 'product'] = card_fee['product']
            df.at[idx, 'percent_rate'] = card_fee['percent_rate']
            df.at[idx, 'fixed_rate'] = card_fee['fixed_rate']
            df.at[idx, 'max_fee'] = card_fee.get('max_fee', None)
            df.at[idx, 'card_cost'] = calculate_cost(
                row['amount'], 
                card_fee['percent_rate'], 
                card_fee['fixed_rate'],
                card_fee.get('max_fee')
            )
        else:
            df.at[idx, 'match_found'] = False
            df.at[idx, 'card_cost'] = 0.0
        
        # Find matching network fee structure (separate from card fees)
        network_fee = find_matching_network_fee(row['card_brand'], row['card_type'], row['amount'])
        
        # Calculate network cost
        if network_fee:
            df.at[idx, 'network_percent_rate'] = network_fee['percent_rate']
            df.at[idx, 'network_fixed_rate'] = network_fee['fixed_rate']
            df.at[idx, 'network_cost'] = calculate_cost(
                row['amount'],
                network_fee['percent_rate'],
                network_fee['fixed_rate']
            )
        else:
            df.at[idx, 'network_cost'] = 0.0
        
        # Calculate total cost (card + network)
        df.at[idx, 'total_cost'] = df.at[idx, 'card_cost'] + df.at[idx, 'network_cost']
    
    return df

def display_metrics(df):
    """Display useful metrics about the processed transactions"""
    import sys
    
    # Build output as a string to avoid buffering issues
    output = []
    output.append("\n" + "="*60)
    output.append("COST ANALYSIS SUMMARY")
    output.append("="*60)
    
    # Filter valid transactions (positive amounts, match found)
    valid_df = df[(df['amount'] > 0) & (df['match_found'] == True)]
    
    # Overall metrics
    total_card_cost = valid_df['card_cost'].sum()
    total_network_cost = valid_df['network_cost'].sum()
    total_cost = valid_df['total_cost'].sum()
    total_volume = valid_df['amount'].sum()
    transaction_count = len(valid_df)
    effective_rate = (total_cost / total_volume * 100) if total_volume > 0 else 0
    
    output.append(f"\n📊 OVERALL METRICS:")
    output.append(f"   Total Transactions:     {transaction_count:,}")
    output.append(f"   Total Volume:           ${total_volume:,.2f}")
    output.append(f"   Card Cost:              ${total_card_cost:,.2f}")
    output.append(f"   Network Cost:           ${total_network_cost:,.2f}")
    output.append(f"   Total Cost:             ${total_cost:,.2f}")
    output.append(f"   Effective Rate:         {effective_rate:.3f}%")
    if transaction_count > 0:
        output.append(f"   Average Cost/Txn:       ${total_cost/transaction_count:.4f}")
    else:
        output.append("   Average Cost/Txn:       N/A")
    
    # By Product
    output.append(f"\n💳 BY PRODUCT:")
    product_summary = valid_df.groupby('product').agg({
        'card_cost': 'sum',
        'network_cost': 'sum',
        'total_cost': 'sum',
        'amount': 'sum',
        'transaction_id': 'count'
    }).rename(columns={'transaction_id': 'count'})
    
    for product, row in product_summary.iterrows():
        output.append(f"   {product}:")
        output.append(f"      Transactions: {int(row['count']):,}")
        output.append(f"      Volume:       ${row['amount']:,.2f}")
        output.append(f"      Card Cost:    ${row['card_cost']:,.2f}")
        output.append(f"      Network Cost: ${row['network_cost']:,.2f}")
        output.append(f"      Total Cost:   ${row['total_cost']:,.2f}")
        output.append(f"      Eff. Rate:    {(row['total_cost']/row['amount']*100):.3f}%")
    
    # By Card Type
    output.append(f"\n💰 BY CARD TYPE:")
    card_summary = valid_df.groupby('card_type').agg({
        'card_cost': 'sum',
        'network_cost': 'sum',
        'total_cost': 'sum',
        'amount': 'sum',
        'transaction_id': 'count'
    }).rename(columns={'transaction_id': 'count'})
    
    for card_type, row in card_summary.iterrows():
        output.append(f"   {card_type}:")
        output.append(f"      Transactions: {int(row['count']):,}")
        output.append(f"      Volume:       ${row['amount']:,.2f}")
        output.append(f"      Card Cost:    ${row['card_cost']:,.2f}")
        output.append(f"      Network Cost: ${row['network_cost']:,.2f}")
        output.append(f"      Total Cost:   ${row['total_cost']:,.2f}")
    
    # By Transaction Type
    output.append(f"\n🌐 BY TRANSACTION TYPE:")
    txn_type_summary = valid_df.groupby('transaction_type').agg({
        'card_cost': 'sum',
        'network_cost': 'sum',
        'total_cost': 'sum',
        'amount': 'sum',
        'transaction_id': 'count'
    }).rename(columns={'transaction_id': 'count'})
    
    for txn_type, row in txn_type_summary.iterrows():
        output.append(f"   {txn_type}:")
        output.append(f"      Transactions: {int(row['count']):,}")
        output.append(f"      Volume:       ${row['amount']:,.2f}")
        output.append(f"      Card Cost:    ${row['card_cost']:,.2f}")
        output.append(f"      Network Cost: ${row['network_cost']:,.2f}")
        output.append(f"      Total Cost:   ${row['total_cost']:,.2f}")
    
    # Edge cases
    edge_cases = df[df['match_found'] == False]
    if len(edge_cases) > 0:
        output.append(f"\n⚠️  UNMATCHED TRANSACTIONS:")
        output.append(f"   Count: {len(edge_cases)}")
        output.append(f"   These transactions had no matching fee structure or invalid amounts.")
    
    output.append("\n" + "="*60)
    
    # Print all at once to avoid buffering issues
    print("\n".join(output), flush=True)

def main():
    """Main function"""
    print("="*60)
    print("MASTERCARD TRANSACTION COST CALCULATOR")
    print("="*60)
    
    # Prompt for MCC
    mcc_input = input("\nEnter MCC code (e.g., 5812, 5411, 4121, 5499): ").strip()
    try:
        mcc = int(mcc_input)
    except ValueError:
        print("❌ Error: MCC must be a valid integer.")
        return
    
    # Prompt for CSV filename
    csv_filename = input("Enter CSV filename (e.g., merch_001_transactions.csv): ").strip()
    csv_path = os.path.join(SCRIPT_DIR, csv_filename)
    
    # Check if file exists
    if not os.path.exists(csv_path):
        print(f"❌ Error: File '{csv_filename}' not found in {SCRIPT_DIR}")
        return
    
    print(f"\n📁 Loading transactions from: {csv_filename}")
    print(f"🏢 Processing with MCC: {mcc}")
    
    # Process transactions
    try:
        df = process_transactions(csv_path, mcc)
        
        # Save output with suffix
        output_filename = csv_filename.replace('.csv', f'_with_costs_mcc{mcc}.csv')
        output_path = os.path.join(SCRIPT_DIR, output_filename)
        df.to_csv(output_path, index=False)
        
        print(f"✅ Processed! Output saved to: {output_filename}")
        
        # Display metrics
        display_metrics(df)
        
    except Exception as e:
        print(f"❌ Error processing file: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
