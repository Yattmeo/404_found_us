"""Debug script to test TPV forecast directly inside ml-service container."""
import json
from datetime import date

import httpx

rows = []
for m_offset in (3, 2, 1):
    today = date(2026, 4, 9)
    m = today.month - m_offset
    y = today.year + (m - 1) // 12
    m = ((m - 1) % 12) + 1
    for wk_day in (1, 8, 15, 22):
        day = date(y, m, wk_day)
        for _ in range(120):
            rows.append({
                "transaction_date": day.isoformat(),
                "amount": 3603.34,
                "proc_cost": 18.017,
                "cost_type_ID": 1,
                "card_type": "both",
                "monthly_txn_count": 1063100,
            })

print(f"Total rows: {len(rows)}")
print(f"Monthly volume per synthetic month: {120 * 4 * 3603.34:.2f}")

resp = httpx.post("http://localhost:8001/ml/GetTPVForecast", json={
    "onboarding_merchant_txn_df": rows,
    "mcc": 5499,
    "card_types": ["both"],
}, timeout=30)
data = resp.json()
print(f"Status: {resp.status_code}")
for item in data.get("forecast", []):
    print(f"  Month {item['month_index']}: mid={item['tpv_mid']:.2f}, lower={item['tpv_ci_lower']:.2f}, upper={item['tpv_ci_upper']:.2f}")
meta = data.get("process_metadata", {})
print(f"Context len: {meta.get('context_len_used')}")
print(f"Context mean dollar: {meta.get('context_mean_dollar')}")
print(f"Momentum: {meta.get('momentum')}")
print(f"Pool mean: {meta.get('pool_mean_used')}")
print(f"Flat pool mean: {meta.get('flat_pool_mean')}")
print(f"Peer IDs: {meta.get('peer_merchant_ids')}")
print(f"Artifact trained at: {meta.get('artifact_trained_at')}")
