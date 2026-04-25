import httpx, sys

BASE = "http://localhost/api/v1"
ML   = "http://localhost/ml"
ok   = True

def check(label, r, expected_status=200):
    global ok
    passed = r.status_code == expected_status
    if not passed:
        ok = False
    print(f"[{'PASS' if passed else 'FAIL'}] {label} -> {r.status_code}")
    if not passed:
        print(f"       {r.text[:400]}")
    return r

sample_txns = [
    {"transaction_date": "2025-01-15", "amount": 120.50, "card_type": "Visa"},
    {"transaction_date": "2025-02-10", "amount": 85.00,  "card_type": "Mastercard"},
    {"transaction_date": "2025-03-20", "amount": 200.75, "card_type": "Visa"},
    {"transaction_date": "2025-04-05", "amount": 310.00, "card_type": "Mastercard"},
    {"transaction_date": "2025-05-12", "amount": 95.50,  "card_type": "Visa"},
    {"transaction_date": "2025-06-18", "amount": 145.00, "card_type": "Visa"},
]

# ── Backend ──────────────────────────────────────────────────────────────────
print("\n── Backend API ──")

r = httpx.post(f"{BASE}/merchants", json={
    "merchant_id": "HANDOFF-M5", "merchant_name": "Handoff E2E Test",
    "mcc": "5411", "industry": "Grocery", "annual_volume": 500000,
    "average_ticket": 55, "current_rate": 0.018, "fixed_fee": 0.30,
}, timeout=30)
check("POST /merchants (create)", r, 201)

check("GET  /merchants/:id",   httpx.get(f"{BASE}/merchants/HANDOFF-M5", timeout=10))
check("GET  /merchants (list)", httpx.get(f"{BASE}/merchants", timeout=10))

csv_bytes = (
    "transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type\n" +
    "\n".join(
        f"HO5-TX-{i:02d},2026-01-{i+10:02d},HANDOFF-M5,{100+i*25:.2f},Sale,{'Visa' if i%2==0 else 'Mastercard'}"
        for i in range(1, 6)
    ) + "\n"
).encode()
r = httpx.post(f"{BASE}/transactions/upload",
    files={"file": ("txns.csv", csv_bytes, "text/csv")},
    data={"merchant_id": "HANDOFF-M5"}, timeout=60)
check("POST /transactions/upload", r)
print(f"       stored={r.json().get('stored_records')}")

r = httpx.get(f"{BASE}/transactions", params={"merchant_id": "HANDOFF-M5", "limit": 10}, timeout=10)
check("GET  /transactions (list)", r)
print(f"       count={len(r.json())}")

txns = [
    {"transaction_id": f"CALC5-{i}", "transaction_date": "2026-01-15",
     "merchant_id": "HANDOFF-M5", "amount": 100+i*10,
     "transaction_type": "Sale", "card_type": "Visa"}
    for i in range(5)
]
check("POST /calculations/merchant-fee",
    httpx.post(f"{BASE}/calculations/merchant-fee",
               json={"transactions": txns, "mcc": "5411"}, timeout=60))

check("GET  /api/v1/docs (Swagger UI)", httpx.get(f"{BASE}/docs", timeout=10))

# ── ML Service ───────────────────────────────────────────────────────────────
print("\n── ML Service ──")

check("GET  /ml/cost-forecast/health", httpx.get(f"{ML}/cost-forecast/health", timeout=10))
check("GET  /ml/docs (Swagger UI)",    httpx.get(f"{ML}/docs", timeout=10))

# Cost forecast → capture response to reuse in profit forecast
r_cost = httpx.post(f"{ML}/GetCostForecast", json={
    "mcc": 5411,
    "pool_mean_at_context_end": 0.016,
    "knn_pool_mean_at_context_end": 0.015,
    "context_months": [
        {"year": 2025, "month": m,
         "avg_proc_cost_pct": 0.015 + m * 0.0005,
         "transaction_count": 200,
         "avg_transaction_value": 55.0}
        for m in range(1, 7)
    ],
}, timeout=60)
check("POST /ml/GetCostForecast", r_cost)
cost_out = r_cost.json() if r_cost.status_code == 200 else None

# TPV forecast → capture for profit forecast
r_tpv = httpx.post(f"{ML}/GetTPVForecast", json={
    "mcc": 5411,
    "merchant_id": "HANDOFF-M5",
    "onboarding_merchant_txn_df": sample_txns,
}, timeout=60)
check("POST /ml/GetTPVForecast", r_tpv)
tpv_out = r_tpv.json() if r_tpv.status_code == 200 else None

# KNN composite merchant — expected to return 400 when seed CSV not provided
r_knn = httpx.post(f"{ML}/getCompositeMerchant", json={
    "mcc": 5411,
    "onboarding_merchant_txn_df": sample_txns,
}, timeout=60)
if r_knn.status_code == 400 and "No reference transactions" in r_knn.text:
    print(f"[PASS] POST /ml/getCompositeMerchant (KNN) -> 400 (expected: no seed data)")
elif r_knn.status_code == 200:
    print(f"[PASS] POST /ml/getCompositeMerchant (KNN) -> 200")
else:
    ok = False
    print(f"[FAIL] POST /ml/getCompositeMerchant (KNN) -> {r_knn.status_code}")
    print(f"       {r_knn.text[:300]}")

# Profit forecast — uses real cost + TPV outputs
if tpv_out and cost_out:
    r = httpx.post(f"{ML}/GetProfitForecast", json={
        "tpv_service_output": tpv_out,
        "cost_service_output": cost_out,
        "fee_rate": 0.025,
        "fixed_fee_per_tx": 0.30,
        "avg_ticket": 55.0,
        "mcc": 5411,
    }, timeout=60)
    check("POST /ml/GetProfitForecast", r)
else:
    ok = False
    print("[FAIL] POST /ml/GetProfitForecast (upstream calls failed, cannot run)")

print("\n" + "=" * 45)
print("ALL TESTS PASSED" if ok else "SOME TESTS FAILED")
print("=" * 45)
sys.exit(0 if ok else 1)
