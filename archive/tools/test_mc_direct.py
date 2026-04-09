"""Direct test of GetProfitForecast with realistic M9-style inputs."""
import requests, json

# Simulate M9 cost output: ~1.24 in 'cents-per-dollar' units = 1.24%
# Volume: ~$325k/month with reasonable CI
profit_body = {
    "cost_service_output": {
        "forecast": [
            {"forecast_week_index": w, "proc_cost_pct_mid": 1.24 + w*0.008,
             "proc_cost_pct_ci_lower": 0.91, "proc_cost_pct_ci_upper": 1.57}
            for w in range(1, 13)
        ],
        "conformal_metadata": None
    },
    "volume_service_output": {
        "forecast": [
            {"forecast_week_index": w,
             "total_proc_value_mid": 80000 + w*500,
             "total_proc_value_ci_lower": 60000,
             "total_proc_value_ci_upper": 105000}
            for w in range(1, 13)
        ]
    },
    "fee_rate": 0.04,
    "mcc": 5499
}

r = requests.post("http://localhost/ml/GetProfitForecast", json=profit_body, timeout=60)
print("Status:", r.status_code)
if r.status_code != 200:
    print(r.text[:500])
else:
    res = r.json()
    s = res["summary"]
    print(f"break_even:       {s['break_even_fee_rate']*100:.4f}%")
    print(f"avg_p_profitable: {s['avg_p_profitable']*100:.1f}%")
    print(f"estimated_profit: ${s['estimated_profit_min']:,.0f} – ${s['estimated_profit_max']:,.0f}")
    print("\nProfitability curve:")
    for pt in s["profitability_curve"]:
        print(f"  rate={pt['rate_pct']:.2f}%  P={pt['probability_pct']:.1f}%  margin={pt['profitability_pct']:.2f}%")
