"""Test the Monte Carlo profit forecast API end-to-end using MCC 5499 data."""
import json
import sys
from datetime import datetime, timedelta

import pandas as pd
import requests

BASE = "http://localhost/ml"
MCC = 5499
MERCHANT_ID = 59935
BASE_COST_RATE = 0.015   # 1.5% decimal
FEE_RATE = 0.04          # 4% decimal

# ── Build onboarding rows from CSV ───────────────────────────────────────────
df = pd.read_csv("data/processed_transactions_5499.csv")
df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
df = df.dropna(subset=["amount"])
merchant = df[df["merchant_id"] == MERCHANT_ID].sort_values(["year", "week"])

today = datetime.now().date()
rows = []
for i, (_, tx) in enumerate(merchant.head(50).iterrows()):
    rows.append({
        "transaction_date": (today - timedelta(days=50 - i)).isoformat(),
        "amount": round(float(tx["amount"]), 2),
        "proc_cost": round(float(tx["amount"]) * BASE_COST_RATE, 6),
        "cost_type_ID": 1,
        "card_type": "both",
    })

print(f"Built {len(rows)} onboarding rows")
print(f"Sample proc_cost/amount: {rows[0]['proc_cost']}/{rows[0]['amount']} = {rows[0]['proc_cost']/rows[0]['amount']:.4f}")

# ── Step 1: Composite ─────────────────────────────────────────────────────────
print("\n=== STEP 1: getCompositeMerchant ===")
r = requests.post(f"{BASE}/getCompositeMerchant", json={
    "onboarding_merchant_txn_df": rows,
    "mcc": MCC,
    "card_types": ["both"],
}, timeout=30)
print(f"Status: {r.status_code}")
if r.status_code != 200:
    print(r.text[:500]); sys.exit(1)
comp = r.json()
weekly_features = comp.get("weekly_features", [])
print(f"Weekly features count: {len(weekly_features)}")
if weekly_features:
    wf = weekly_features[-1]
    print(f"Last weekly_avg_txn_cost_pct_mean: {wf.get('weekly_avg_txn_cost_pct_mean')}")
    print(f"Last weekly_avg_txn_value_mean:    {wf.get('weekly_avg_txn_value_mean')}")
    print(f"Last weekly_txn_count_mean:        {wf.get('weekly_txn_count_mean')}")

# ── Step 2: Cost Forecast ─────────────────────────────────────────────────────
print("\n=== STEP 2: GetCostForecast ===")
r = requests.post(f"{BASE}/GetCostForecast", json={
    "composite_weekly_features": weekly_features,
    "onboarding_merchant_txn_df": rows,
    "mcc": MCC,
}, timeout=30)
print(f"Status: {r.status_code}")
if r.status_code != 200:
    print(r.text[:500]); sys.exit(1)
cost_payload = r.json()
forecast = cost_payload.get("forecast", [])
print(f"Cost forecast weeks: {len(forecast)}")
if forecast:
    for wk in forecast[:4]:
        print(f"  week {wk.get('forecast_week_index',wk.get('month_index'))}: "
              f"mid={wk.get('proc_cost_pct_mid'):.6f}  "
              f"ci=[{wk.get('proc_cost_pct_ci_lower'):.6f}, {wk.get('proc_cost_pct_ci_upper'):.6f}]")
conf = cost_payload.get("conformal_metadata")
print(f"Conformal metadata: {conf}")

# ── Step 3: Volume Forecast ───────────────────────────────────────────────────
print("\n=== STEP 3: GetVolumeForecast ===")
r = requests.post(f"{BASE}/GetVolumeForecast", json={
    "composite_weekly_features": weekly_features,
    "onboarding_merchant_txn_df": rows,
    "mcc": MCC,
}, timeout=30)
print(f"Status: {r.status_code}")
if r.status_code != 200:
    print(r.text[:500]); sys.exit(1)
vol_payload = r.json()
vol_forecast = vol_payload.get("forecast", [])
print(f"Volume forecast weeks: {len(vol_forecast)}")
if vol_forecast:
    for wk in vol_forecast[:4]:
        print(f"  week {wk.get('forecast_week_index')}: "
              f"mid={wk.get('total_proc_value_mid'):.2f}  "
              f"ci=[{wk.get('total_proc_value_ci_lower'):.2f}, {wk.get('total_proc_value_ci_upper'):.2f}]")

# ── Step 4: Profit Forecast ───────────────────────────────────────────────────
print("\n=== STEP 4: GetProfitForecast ===")
profit_body = {
    "cost_service_output": cost_payload,
    "volume_service_output": vol_payload,
    "fee_rate": FEE_RATE,
    "mcc": MCC,
}
print("\nRequest payload:")
print(json.dumps(profit_body, indent=2)[:2000])

r = requests.post(f"{BASE}/GetProfitForecast", json=profit_body, timeout=60)
print(f"\nStatus: {r.status_code}")
if r.status_code != 200:
    print(r.text[:1000]); sys.exit(1)
profit = r.json()
summary = profit.get("summary", {})
print(f"\nSummary:")
print(f"  total_profit_mid:     ${summary.get('total_profit_mid', 0):.2f}")
print(f"  estimated_profit_min: ${summary.get('estimated_profit_min', 0):.2f}")
print(f"  estimated_profit_max: ${summary.get('estimated_profit_max', 0):.2f}")
print(f"  avg_p_profitable:     {summary.get('avg_p_profitable', 0)*100:.1f}%")
print(f"  break_even_fee_rate:  {summary.get('break_even_fee_rate', 0)*100:.3f}%")
print(f"\nProfitability curve:")
for pt in summary.get("profitability_curve", []):
    print(f"  rate={pt['rate_pct']:.2f}%  P={pt['probability_pct']:.1f}%  margin={pt['profitability_pct']:.2f}%")
