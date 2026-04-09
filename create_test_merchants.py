"""
Create single-merchant test CSVs from each per-MCC processed transaction file.
Picks one merchant per MCC, outputs to data/test_merchant_<mcc>.csv
"""
import pandas as pd

DATA_DIR = r"C:\Users\justi\Documents\GitHub\404_found_us\data"

# The upload endpoint needs: transaction_id, merchant_id, transaction_date, amount, card_brand, card_type
# (mcc is provided as a query param, not from CSV)

files = {
    5499: "processed_transactions_5499.csv",
    5411: "processed_transactions_5411.csv",
    5812: "processed_transactions_5812.csv",
    4121: "processed_transactions_4121.csv",
}

for mcc, fname in files.items():
    print(f"\n=== MCC {mcc} ({fname}) ===")
    df = pd.read_csv(f"{DATA_DIR}/{fname}")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    
    # Pick the merchant with highest total volume (most realistic test)
    vol = df.groupby("merchant_id")["amount"].sum().sort_values(ascending=False)
    top_mid = vol.index[0]
    top_vol = vol.iloc[0]
    n_txns = (df["merchant_id"] == top_mid).sum()
    
    print(f"  Top merchant: {top_mid}  total_vol=${top_vol:,.0f}  txns={n_txns:,}")
    
    # Extract just that merchant
    merchant_df = df[df["merchant_id"] == top_mid].copy()
    
    # Normalize card_type casing to match what the cost engine expects
    # The cost engine expects: Credit, Debit, Prepaid (title case)
    merchant_df["card_type"] = merchant_df["card_type"].str.strip()
    ct_map = {
        "credit": "Credit",
        "debit": "Debit",
        "debit (prepaid)": "Debit (Prepaid)",
        "prepaid": "Prepaid",
    }
    merchant_df["card_type"] = merchant_df["card_type"].str.lower().map(ct_map).fillna(merchant_df["card_type"])
    
    # Normalize card_brand casing
    cb_map = {"visa": "Visa", "mastercard": "Mastercard"}
    merchant_df["card_brand"] = merchant_df["card_brand"].str.lower().map(cb_map).fillna(merchant_df["card_brand"])
    
    out_path = f"{DATA_DIR}/test_merchant_{mcc}.csv"
    merchant_df.to_csv(out_path, index=False)
    
    avg_txn = merchant_df["amount"].mean()
    monthly_approx = top_vol / (merchant_df["transaction_date"].apply(pd.Timestamp).dt.year.nunique() * 12)
    print(f"  Avg txn=${avg_txn:,.2f}  ~${monthly_approx:,.0f}/month")
    print(f"  Card brands: {merchant_df['card_brand'].value_counts().to_dict()}")
    print(f"  Card types:  {merchant_df['card_type'].value_counts().to_dict()}")
    print(f"  Saved: {out_path} ({len(merchant_df):,} rows)")

print("\n\nDone! Test files created.")
