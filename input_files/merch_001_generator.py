import pandas as pd
import numpy as np
import random
import os
from datetime import datetime, timedelta

# --- CONFIGURATION ---
NUM_ROWS = 1000
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "merch_001_transactions.csv")

# --- HELPERS ---
def generate_txn_id():
    """Generates a fixed-length ID: TXN + 12 random digits"""
    return f"TXN{random.randint(100000000000, 999999999999)}"

def random_date(start_date, end_date):
    """Generates a random timestamp between two dates"""
    delta = end_date - start_date
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = random.randrange(int_delta)
    return start_date + timedelta(seconds=random_second)

# --- MERCHANT PROFILE ---
# "The Coffee Shop" (MERCH_001): High volume, tiny amounts ($3 - $15).
# *Challenge:* Fixed fees kill their margin.

merchant = {
    "id": "MERCH_001",
    "type": "Micro",
    "min": 3.00,
    "max": 15.00,
    "cards": ["Debit", "Debit", "Credit", "Debit (Prepaid)"]
}

card_brands = ["Visa", "Mastercard", "Amex"]
transaction_types = ["Online", "Offline"]
start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 1, 31)

data = []

print(f"Generating {NUM_ROWS} transactions for {merchant['id']} ({merchant['type']})...")

for _ in range(NUM_ROWS):
    # Generate Amount based on profile
    amount = round(random.uniform(merchant["min"], merchant["max"]), 2)
    
    # Generate Card Details
    # Amex is usually Credit only
    brand = random.choice(card_brands)
    card_type = "Credit" if brand == "Amex" else random.choice(merchant["cards"])
    
    row = {
        "transaction_id": generate_txn_id(),
        "merchant_id": merchant["id"],
        "date": random_date(start_date, end_date).strftime("%Y-%m-%d %H:%M:%S"),
        "amount": amount,
        "card_type": card_type,
        "card_brand": brand,
        "transaction_type": random.choice(transaction_types),
    }
    data.append(row)

# --- EDGE CASES (Crucial for Testing) ---
# Add a few "weird" rows to test your validation logic
edge_cases = [
    # The "Zero" amount (Should be rejected or handled)
    {"transaction_id": generate_txn_id(), "merchant_id": merchant["id"], "date": "2025-01-15 10:00:00", "amount": 0.00, "card_type": "Debit", "card_brand": "Visa", "transaction_type": "Online"},
    # The "Negative" refund (Should not add to cost volume)
    {"transaction_id": generate_txn_id(), "merchant_id": merchant["id"], "date": "2025-01-15 12:00:00", "amount": -5.00, "card_type": "Credit", "card_brand": "Visa", "transaction_type": "Offline"},
]
data.extend(edge_cases)

# Create DataFrame and Save
df = pd.DataFrame(data)
df.to_csv(OUTPUT_FILE, index=False)

print(f"Success! Created '{OUTPUT_FILE}' with {len(df)} rows.")
print("Columns:", list(df.columns))
print(df.head())
