import pandas as pd
import numpy as np

DATA_DIR = r"C:\Users\justi\Documents\GitHub\404_found_us\data"

# 1) 5411_monthly_v2.csv - pre-aggregated monthly
df = pd.read_csv(f"{DATA_DIR}/5411_monthly_v2.csv")
print("=== 5411_monthly_v2.csv (pre-aggregated) ===")
print(f"  Shape: {df.shape}")
print(f"  Merchants: {df.merchant_id.nunique()}")
print(f"  Year range: {df.year.min()}-{df.year.max()}")
tpv = df["total_processing_value"]
lt = np.log1p(tpv)
print(f"  Monthly TPV: median=${tpv.median():,.0f}  mean=${tpv.mean():,.0f}  p90=${tpv.quantile(0.9):,.0f}  max=${tpv.max():,.0f}")
print(f"  log1p mean={lt.mean():.3f} -> expm1=${np.expm1(lt.mean()):,.0f}")
print()

# 2) Per-MCC transaction files
for fname, mcc in [
    ("processed_transactions_5499.csv", 5499),
    ("processed_transactions_5411.csv", 5411),
    ("processed_transactions_5812.csv", 5812),
    ("processed_transactions_4121.csv", 4121),
]:
    df = pd.read_csv(f"{DATA_DIR}/{fname}")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df["mo"] = df["transaction_date"].dt.month
    df["yr"] = df["transaction_date"].dt.year
    monthly = df.groupby(["merchant_id", "yr", "mo"])["amount"].sum().reset_index()
    monthly.columns = ["mid", "yr", "mo", "tpv"]
    lt = np.log1p(monthly["tpv"])
    print(f"=== {fname} (MCC {mcc}) ===")
    print(f"  Rows: {len(df):,}  Merchants: {monthly.mid.nunique()}")
    print(f"  Monthly TPV: median=${monthly.tpv.median():,.0f}  mean=${monthly.tpv.mean():,.0f}  p90=${monthly.tpv.quantile(0.9):,.0f}  max=${monthly.tpv.max():,.0f}")
    print(f"  log1p mean={lt.mean():.3f} -> expm1=${np.expm1(lt.mean()):,.0f}")
    print()

# 3) Compare with combined 4mcc
df = pd.read_csv(f"{DATA_DIR}/processed_transactions_4mcc.csv")
df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
df["date"] = pd.to_datetime(df["date"])
df["mo"] = df["date"].dt.month
df["yr"] = df["date"].dt.year
for mcc in [5411, 5499, 5812, 4121]:
    sub = df[df["mcc"] == mcc]
    monthly = sub.groupby(["merchant_id", "yr", "mo"])["amount"].sum().reset_index()
    monthly.columns = ["mid", "yr", "mo", "tpv"]
    lt = np.log1p(monthly["tpv"])
    print(f"=== processed_transactions_4mcc.csv MCC {mcc} ===")
    print(f"  Rows: {len(sub):,}  Merchants: {monthly.mid.nunique()}")
    print(f"  Monthly TPV: median=${monthly.tpv.median():,.0f}  mean=${monthly.tpv.mean():,.0f}  p90=${monthly.tpv.quantile(0.9):,.0f}  max=${monthly.tpv.max():,.0f}")
    print(f"  log1p mean={lt.mean():.3f} -> expm1=${np.expm1(lt.mean()):,.0f}")
    print()
