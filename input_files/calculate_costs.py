import pandas as pd
import numpy as np
import json
import os
from pathlib import Path

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COST_STRUCTURE_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "cost_structure")
MASTERCARD_FEE_FILE = os.path.join(COST_STRUCTURE_DIR, "masterCard_Card.JSON")

# --- HELPERS ---
def load_fee_structure():
    """Load Mastercard fee structure from JSON"""
    with open(MASTERCARD_FEE_FILE, 'r') as f:
        return json.load(f)

def normalize_card_type(card_type):
    """Normalize card type from transaction data to match fee structure"""
    if card_type == "Debit (Prepaid)":
        return "Prepaid"
    return card_type

def find_matching_fee(card_type, mcc, amount, fee_structure):
    """
    Find matching fee structure for a transaction.
    Priority: Small Ticket Fee Program if amount < $5, otherwise Industry Fee Program by MCC
    """
    normalized_card_type = normalize_card_type(card_type)
    
    # Special rule: amounts less than $5 use Small Ticket Fee Program
    if amount < 5.0:
        for fee in fee_structure:
            if (fee["card_type"] == normalized_card_type and 
                fee["product"] == "Small Ticket Fee Program (All)" and 
                fee["mcc"] is None):
                return fee
    
    # Otherwise, try to match by MCC and card type
    for fee in fee_structure:
        if (fee["card_type"] == normalized_card_type and 
            fee["mcc"] == mcc):
            return fee
    
    # Fallback: if no MCC match, return None (will be handled separately)
    return None

def calculate_cost(amount, percent_rate, fixed_rate, max_fee=None):
    """Calculate transaction cost based on percent and fixed rates"""
    cost = (amount * percent_rate) + fixed_rate
    
    # Apply max_fee cap if specified
    if max_fee is not None:
        cost = min(cost, max_fee)
    
    return round(cost, 4)

def process_transactions(csv_path, mcc):
    """Process transactions and add cost calculation columns"""
    # Load data
    df = pd.read_csv(csv_path)
    fee_structure = load_fee_structure()
    
    # Initialize new columns
    df['mcc'] = mcc
    df['product'] = None
    df['percent_rate'] = None
    df['fixed_rate'] = None
    df['max_fee'] = None
    df['cost'] = None
    df['match_found'] = True
    
    # Process each transaction
    for idx, row in df.iterrows():
        # Skip negative amounts (refunds) and zero amounts
        if row['amount'] <= 0:
            df.at[idx, 'cost'] = 0.0
            df.at[idx, 'match_found'] = False
            continue
        
        # Find matching fee structure
        fee = find_matching_fee(row['card_type'], mcc, row['amount'], fee_structure)
        
        if fee:
            df.at[idx, 'product'] = fee['product']
            df.at[idx, 'percent_rate'] = fee['percent_rate']
            df.at[idx, 'fixed_rate'] = fee['fixed_rate']
            df.at[idx, 'max_fee'] = fee.get('max_fee', None)
            df.at[idx, 'cost'] = calculate_cost(
                row['amount'], 
                fee['percent_rate'], 
                fee['fixed_rate'],
                fee.get('max_fee')
            )
        else:
            df.at[idx, 'match_found'] = False
            df.at[idx, 'cost'] = 0.0
    
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
    total_cost = valid_df['cost'].sum()
    total_volume = valid_df['amount'].sum()
    transaction_count = len(valid_df)
    effective_rate = (total_cost / total_volume * 100) if total_volume > 0 else 0
    
    output.append(f"\n📊 OVERALL METRICS:")
    output.append(f"   Total Transactions:     {transaction_count:,}")
    output.append(f"   Total Volume:           ${total_volume:,.2f}")
    output.append(f"   Total Cost:             ${total_cost:,.2f}")
    output.append(f"   Effective Rate:         {effective_rate:.3f}%")
    if transaction_count > 0:
        output.append(f"   Average Cost/Txn:       ${total_cost/transaction_count:.4f}")
    else:
        output.append("   Average Cost/Txn:       N/A")
    
    # By Product
    output.append(f"\n💳 BY PRODUCT:")
    product_summary = valid_df.groupby('product').agg({
        'cost': 'sum',
        'amount': 'sum',
        'transaction_id': 'count'
    }).rename(columns={'transaction_id': 'count'})
    
    for product, row in product_summary.iterrows():
        output.append(f"   {product}:")
        output.append(f"      Transactions: {int(row['count']):,}")
        output.append(f"      Volume:       ${row['amount']:,.2f}")
        output.append(f"      Total Cost:   ${row['cost']:,.2f}")
        output.append(f"      Eff. Rate:    {(row['cost']/row['amount']*100):.3f}%")
    
    # By Card Type
    output.append(f"\n💰 BY CARD TYPE:")
    card_summary = valid_df.groupby('card_type').agg({
        'cost': 'sum',
        'amount': 'sum',
        'transaction_id': 'count'
    }).rename(columns={'transaction_id': 'count'})
    
    for card_type, row in card_summary.iterrows():
        output.append(f"   {card_type}:")
        output.append(f"      Transactions: {int(row['count']):,}")
        output.append(f"      Volume:       ${row['amount']:,.2f}")
        output.append(f"      Total Cost:   ${row['cost']:,.2f}")
    
    # By Transaction Type
    output.append(f"\n🌐 BY TRANSACTION TYPE:")
    txn_type_summary = valid_df.groupby('transaction_type').agg({
        'cost': 'sum',
        'amount': 'sum',
        'transaction_id': 'count'
    }).rename(columns={'transaction_id': 'count'})
    
    for txn_type, row in txn_type_summary.iterrows():
        output.append(f"   {txn_type}:")
        output.append(f"      Transactions: {int(row['count']):,}")
        output.append(f"      Volume:       ${row['amount']:,.2f}")
        output.append(f"      Total Cost:   ${row['cost']:,.2f}")
    
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
