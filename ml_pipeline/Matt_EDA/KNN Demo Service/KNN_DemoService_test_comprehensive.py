"""Comprehensive test suite for KNN Rate Quote Service with card type filtering."""
import sys
from pathlib import Path

service_dir = Path("/Users/yattmeo/Desktop/SMU/Code/404_found_us/ml_pipeline/Matt_EDA/KNN Demo Service")
sys.path.insert(0, str(service_dir))

from knn_rate_quote_service import KNNRateQuoteService
import pandas as pd
import sqlite3

service = KNNRateQuoteService()

# Load test data
with sqlite3.connect(service.db_path) as conn:
    df_all = pd.read_sql(
        "SELECT date, amount, cost_type_ID, card_type FROM transactions WHERE date IS NOT NULL LIMIT 1000",
        conn,
    )

df_all = df_all.rename(columns={"date": "transaction_date"})

print("=" * 70)
print("COMPREHENSIVE KNN RATE QUOTE SERVICE TEST")
print("=" * 70)

# Test 1: DataFrame-based queries with different card types
print("\n[Test 1] DataFrame-based queries with different card types")
print("-" * 70)

try:
    result = service.quote(df=df_all, mcc=5411, card_type="both")
    print(f"✓ card_type='both': {result.forecast_proc_cost}")
except Exception as e:
    print(f"✗ card_type='both' failed: {e}")

try:
    result = service.quote(df=df_all, mcc=5411, card_type="visa")
    print(f"✓ card_type='visa': {result.forecast_proc_cost}")
except Exception as e:
    print(f"✗ card_type='visa' failed: {e}")

try:
    result = service.quote(df=df_all, mcc=5411, card_type="mastercard")
    print(f"✓ card_type='mastercard': {result.forecast_proc_cost}")
except Exception as e:
    print(f"✗ card_type='mastercard' failed: {e}")

# Test 2: Metrics-only queries
print("\n[Test 2] Metrics-only queries with different card types")
print("-" * 70)

try:
    result = service.quote(
        df=None,
        mcc=5411,
        card_type="both",
        monthly_txn_count=150,
        avg_amount=50.0,
        as_of_date="2019-06-30",
    )
    print(f"✓ card_type='both', as_of_date=2019-06-30: {result.forecast_proc_cost}")
except Exception as e:
    print(f"✗ card_type='both' metrics-only failed: {e}")

try:
    result = service.quote(
        df=None,
        mcc=5411,
        card_type="visa",
        monthly_txn_count=100,
        avg_amount=45.0,
        as_of_date="2019-03-31",
    )
    print(f"✓ card_type='visa', as_of_date=2019-03-31: {result.forecast_proc_cost}")
except Exception as e:
    print(f"✗ card_type='visa' metrics-only failed: {e}")

try:
    result = service.quote(
        df=None,
        mcc=5411,
        card_type="mastercard",
        monthly_txn_count=200,
        avg_amount=60.0,
        as_of_date="2019-12-31",
    )
    print(f"✓ card_type='mastercard', as_of_date=2019-12-31: {result.forecast_proc_cost}")
except Exception as e:
    print(f"✗ card_type='mastercard' metrics-only failed: {e}")

# Test 3: Mixed input (df + metrics overrides)
print("\n[Test 3] Mixed input (df + metrics) with card type")
print("-" * 70)

try:
    result = service.quote(
        df=df_all,
        mcc=5411,
        card_type="visa",
        monthly_txn_count=300,  # Override
        avg_amount=75.0,  # Override
    )
    print(f"✓ df + metrics override (visa): {result.forecast_proc_cost}")
except Exception as e:
    print(f"✗ df + metrics override failed: {e}")

# Test 4: Different end months
print("\n[Test 4] Different end months with card type filtering")
print("-" * 70)

for month in [1, 6, 12]:
    for card_type in ["visa", "both"]:
        try:
            result = service.quote(
                df=None,
                mcc=5411,
                card_type=card_type,
                monthly_txn_count=150,
                avg_amount=50.0,
                as_of_date=f"2019-{month:02d}-28",
            )
            print(f"✓ card_type='{card_type}', month={month}: end_month={result.end_month}")
        except Exception as e:
            print(f"✗ card_type='{card_type}', month={month}: {str(e)[:50]}")

# Test 5: Forecast consistency
print("\n[Test 5] Forecast consistency across card types")
print("-" * 70)

results = {}
for card_type in ["visa", "mastercard", "both"]:
    try:
        result = service.quote(
            df=df_all,
            mcc=5411,
            card_type=card_type,
        )
        results[card_type] = result
        print(f"✓ card_type='{card_type}': {len(result.forecast_proc_cost)} months forecast")
    except Exception as e:
        print(f"✗ card_type='{card_type}': {e}")

if "visa" in results and "both" in results:
    visa_forecast = results["visa"].forecast_proc_cost
    both_forecast = results["both"].forecast_proc_cost
    if visa_forecast != both_forecast:
        print(f"  - Different forecasts (expected when pools differ)")
        print(f"    visa: {[f'{x:.4f}' for x in visa_forecast]}")
        print(f"    both: {[f'{x:.4f}' for x in both_forecast]}")
    else:
        print(f"  - Same forecast (both visa and all contain same patterns)")

# Test 6: Error handling
print("\n[Test 6] Error handling")
print("-" * 70)

try:
    result = service.quote(
        df=None,
        mcc=5411,
        card_type="visa",
        monthly_txn_count=None,  # Missing required metric
        avg_amount=50.0,
        as_of_date="2019-06-30",
    )
    print(f"✗ Should have raised error for missing monthly_txn_count")
except ValueError as e:
    print(f"✓ Correctly raised error: {str(e)[:50]}")

try:
    empty_df = pd.DataFrame({"transaction_date": [], "amount": [], "cost_type_ID": []})
    result = service.quote(df=empty_df, mcc=5411, card_type="visa")
    print(f"✗ Should have raised error for empty df")
except ValueError as e:
    print(f"✓ Correctly raised error: {str(e)[:50]}")

# Test 7: as_of_date fallback to most recent year
print("\n[Test 7] as_of_date fallback when beyond data range")
print("-" * 70)

max_period = service.all_monthly["ym_period"].max()
print(f"Reference data ends at: {max_period}")

# Test within range
try:
    result = service.quote(
        df=None,
        mcc=5411,
        monthly_txn_count=150,
        avg_amount=50.0,
        as_of_date="2019-06-30",
    )
    print(f"✓ as_of_date=2019-06-30 (within range): end_month={result.end_month}")
except Exception as e:
    print(f"✗ Failed: {e}")

# Test beyond range (should map to most recent year)
future_year = max_period.year + 2
try:
    result = service.quote(
        df=None,
        mcc=5411,
        monthly_txn_count=150,
        avg_amount=50.0,
        as_of_date=f"{future_year}-06-30",
    )
    print(f"✓ as_of_date={future_year}-06-30 (beyond range):")
    print(f"  Maps to {max_period.year}-06, end_month={result.end_month}")
except Exception as e:
    print(f"✗ Failed: {e}")

# Test multiple months beyond range
print("\n  Testing various months beyond range:")
for month in [1, 3, 6, 9, 12]:
    try:
        future_date = f"{max_period.year + 3}-{month:02d}-15"
        result = service.quote(
            df=None,
            mcc=5411,
            monthly_txn_count=150,
            avg_amount=50.0,
            as_of_date=future_date,
        )
        print(f"  ✓ {future_date} → end_month={result.end_month}")
    except Exception as e:
        print(f"  ✗ {future_date}: {str(e)[:40]}")

print("\n" + "=" * 70)
print("COMPREHENSIVE TEST COMPLETE")
print("=" * 70)
