# GetProfitForecast Service

**Monte Carlo profit-analysis simulation service.**

Accepts the pre-computed outputs from the TPV and AvgProcCost forecast
services (passed in by the orchestrator), adds a merchant fee rate, and
returns a full profit distribution for each forecast month — including the
probability of profitability, profit CI, and a break-even fee rate.

---

## Architecture

```
                          ┌──────────────────────┐
                          │    Orchestrator       │
                          │                       │
                          │ 1. Call TPV service    │
                          │ 2. Call Cost service   │
                          │ 3. Pass both outputs   │
                          │    + fee_rate to ──────┼──►┐
                          └──────────────────────┘    │
                                                      │
                       ┌──────────────────────────────┘
                       ▼
              ┌─────────────────────────┐
              │ GetProfitForecast       │
              │ (this service, :8094)   │
              │                         │
              │ Monte Carlo simulation  │
              │ → P(profitable)         │
              │ → profit CI             │
              │ → break-even fee rate   │
              └─────────────────────────┘
```

The **orchestrator** is responsible for calling the upstream services.
This service receives their outputs and runs the simulation only:

1. Parses the TPV forecast (monthly `tpv_mid` + conformal `half_width_dollars`).
2. Parses the cost forecast (monthly `proc_cost_pct_mid` + conformal `half_width`).
3. Converts each conformal half-width into a Gaussian σ
   (`σ = half_width / z_α`).
4. Samples `n_simulations` (default 10,000) independent draws of TPV and
   cost_pct per month.
5. Computes `profit = TPV × (fee_rate − cost_pct)` for every sample.
6. Returns: point estimates, P(profitable), profit CI, median, std, a
   break-even fee rate, and simulation metadata.

**Independence assumption:** Empirical testing on MCC 5411 showed
|ρ(log_tpv, avg_proc_cost_pct)| ≈ 0.14, p = 0.14 — below the 0.15
threshold. TPV and cost_pct are sampled independently.

---

## Quickstart

```bash
cd "GetProfitForecast Service"
pip install -r requirements.txt
python app.py
```

The service starts on `http://127.0.0.1:8094`.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_N_SIMULATIONS` | `10000` | Default Monte Carlo sample count |
| `SERVICE_PORT` | `8094` | Port this service listens on |

---

## Orchestrator Workflow

The orchestrator calls the upstream services first, then passes their
**full JSON responses** to this service. Extra fields are silently ignored.

```python
import httpx

# 1. Call TPV service
tpv_resp = httpx.post("http://127.0.0.1:8093/GetTPVForecast", json={
    "onboarding_merchant_txn_df": txn_records,
    "mcc": 5411,
}).json()

# 2. Call Cost service
cost_resp = httpx.post("http://127.0.0.1:8092/GetM9MonthlyCostForecast", json={
    "onboarding_merchant_txn_df": txn_records,
    "mcc": 5411,
}).json()

# 3. Pass both outputs to Profit service
profit_resp = httpx.post("http://127.0.0.1:8094/GetProfitForecast", json={
    "tpv_service_output": tpv_resp,
    "cost_service_output": cost_resp,
    "fee_rate": 0.029,
    "mcc": 5411,
    "merchant_id": "m-grocery-001",
}).json()
```

---

## API Reference

### `GET /health`

Liveness check.

**Response:**
```json
{
  "status": "ok"
}
```

### `POST /GetProfitForecast`

Run the profit forecast.

#### Request Body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `tpv_service_output` | `object` | **Yes** | — | The full JSON response from `POST /GetTPVForecast`. Must contain `forecast` (list with `tpv_mid`), `conformal_metadata` (with `half_width_dollars`, `conformal_mode`), and `process_metadata` (with `context_len_used`). Extra fields are ignored. |
| `cost_service_output` | `object` | **Yes** | — | The full JSON response from `POST /GetM9MonthlyCostForecast`. Must contain `forecast` (list with `proc_cost_pct_mid`), `conformal_metadata` (with `half_width`, `conformal_mode`), and `process_metadata` (with `context_len_used`). Extra fields are ignored. |
| `fee_rate` | `float` | **Yes** | — | Merchant fee rate as a fraction (e.g. `0.029` = 2.9%). Must be 0 < fee_rate < 1. |
| `mcc` | `int` | **Yes** | — | Merchant Category Code (e.g. `5411` for grocery). |
| `merchant_id` | `string` | No | `null` | Opaque merchant identifier for traceability. |
| `confidence_interval` | `float` | No | `0.90` | Coverage level for the profit CI percentiles (0–1 exclusive). |
| `n_simulations` | `int` | No | `10000` | Number of Monte Carlo samples (100–1,000,000). Higher = more precise P(profitable) at the cost of latency. 10k is good for most use cases; use 100k if you need tight estimates. |

#### Response Body

```json
{
  "months": [
    {
      "month_index": 1,
      "tpv_mid": 10000.0,
      "cost_pct_mid": 0.020,
      "revenue_mid": 290.0,
      "cost_mid": 200.0,
      "profit_mid": 90.0,
      "margin_mid": 0.009,
      "p_profitable": 0.87,
      "profit_ci_lower": -42.5,
      "profit_ci_upper": 225.3,
      "profit_median": 91.2,
      "profit_std": 82.1
    }
  ],
  "summary": {
    "total_profit_mid": 270.0,
    "total_revenue_mid": 870.0,
    "total_cost_mid": 600.0,
    "avg_p_profitable": 0.87,
    "min_p_profitable": 0.82,
    "break_even_fee_rate": 0.027
  },
  "metadata": {
    "fee_rate": 0.029,
    "n_simulations": 10000,
    "confidence_interval": 0.90,
    "mcc": 5411,
    "merchant_id": "m-123",
    "horizon_months": 3,
    "tpv_conformal_mode": "adaptive",
    "cost_conformal_mode": "adaptive",
    "tpv_context_len_used": 6,
    "cost_context_len_used": 6,
    "generated_at_utc": "2025-01-15T12:00:00Z",
    "correlation_assumed": "independent"
  }
}
```

---

## Response Fields — Detailed Explanation

### `months[].` fields

| Field | Meaning |
|-------|---------|
| `month_index` | 1-based forecast month (1 = next month). |
| `tpv_mid` | Point forecast of total payment volume in dollars (from TPV service). |
| `cost_pct_mid` | Point forecast of average processing cost as a fraction (from Cost service). |
| `revenue_mid` | Expected revenue = `tpv_mid × fee_rate`. |
| `cost_mid` | Expected cost = `tpv_mid × cost_pct_mid`. |
| `profit_mid` | Expected profit = `revenue_mid − cost_mid`. Can be negative. |
| `margin_mid` | Point margin = `fee_rate − cost_pct_mid`. Positive = profitable at the point estimate. |
| `p_profitable` | **Probability of profit > $0** from Monte Carlo. The key decision metric. Accounts for uncertainty in *both* TPV and cost forecasts. |
| `profit_ci_lower` | Lower bound of the profit CI (in dollars). E.g. with `confidence_interval=0.90`, this is the 5th percentile. |
| `profit_ci_upper` | Upper bound of the profit CI (in dollars). 95th percentile for 90% CI. |
| `profit_median` | Median profit from the simulation (more robust than `profit_mid` for skewed distributions). |
| `profit_std` | Standard deviation of the profit distribution. Measures risk / volatility. |

### `summary.` fields

| Field | Meaning |
|-------|---------|
| `total_profit_mid` | Sum of `profit_mid` across all forecast months. |
| `total_revenue_mid` | Sum of `revenue_mid` across all forecast months. |
| `total_cost_mid` | Sum of `cost_mid` across all forecast months. |
| `avg_p_profitable` | Average P(profitable) across months. |
| `min_p_profitable` | Worst-case P(profitable) across months. Use this for conservative decisions. |
| `break_even_fee_rate` | The minimum fee_rate that covers the worst-month cost upper bound (cost_pct_mid + conformal half_width). Setting `fee_rate ≥ break_even_fee_rate` gives approximately `confidence_interval` coverage that costs will be covered. |

### `metadata.` fields

Transparency about what the service did: fee_rate used, mcc, n_simulations,
conformal modes chosen by the upstream services, context window lengths, and
the timestamp. `correlation_assumed` is always `"independent"` in v1.

---

## How to Interpret Results

### Decision Framework

| Metric | Threshold | Interpretation |
|--------|-----------|----------------|
| `min_p_profitable` | > 0.80 | **Accept** — strong confidence in profitability across all months. |
| `min_p_profitable` | 0.50 – 0.80 | **Review** — profitable in expectation but significant downside risk. |
| `min_p_profitable` | < 0.50 | **Reject / Reprice** — more likely to lose money than not. |
| `break_even_fee_rate` | < your `fee_rate` | Good — your fee covers the worst-case cost scenario. |
| `break_even_fee_rate` | > your `fee_rate` | Risk — in the worst month, cost could exceed your fee. |
| `profit_ci_lower` | > 0 (all months) | Very strong — even the downside scenario is profitable. |

### Repricing Guidance

If the merchant is not profitable at the proposed fee rate:

1. Check `break_even_fee_rate` — this is the minimum fee to charge.
2. Add a safety margin: `suggested_fee = break_even_fee_rate × 1.1`.
3. Re-run the forecast with the new fee rate to confirm `p_profitable > 0.80`.

---

## Sample Request

```bash
curl -X POST http://127.0.0.1:8094/GetProfitForecast \
  -H "Content-Type: application/json" \
  -d '{
    "tpv_service_output": {
      "forecast": [
        {"month_index": 1, "tpv_mid": 10000.0, "tpv_ci_lower": 9500.0, "tpv_ci_upper": 10500.0},
        {"month_index": 2, "tpv_mid": 10500.0, "tpv_ci_lower": 10000.0, "tpv_ci_upper": 11000.0},
        {"month_index": 3, "tpv_mid": 11000.0, "tpv_ci_lower": 10500.0, "tpv_ci_upper": 11500.0}
      ],
      "conformal_metadata": {
        "half_width_dollars": 500.0,
        "conformal_mode": "adaptive",
        "pool_size": 50
      },
      "process_metadata": {
        "context_len_used": 6,
        "mcc": 5411,
        "confidence_interval": 0.90
      }
    },
    "cost_service_output": {
      "forecast": [
        {"month_index": 1, "proc_cost_pct_mid": 0.020},
        {"month_index": 2, "proc_cost_pct_mid": 0.021},
        {"month_index": 3, "proc_cost_pct_mid": 0.022}
      ],
      "conformal_metadata": {
        "half_width": 0.005,
        "conformal_mode": "adaptive",
        "pool_size": 50
      },
      "process_metadata": {
        "context_len_used": 6,
        "mcc": 5411,
        "confidence_interval": 0.90
      }
    },
    "fee_rate": 0.029,
    "mcc": 5411,
    "merchant_id": "m-grocery-001",
    "n_simulations": 10000
  }'
```

---

## Running Tests

```bash
cd "GetProfitForecast Service"
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

Tests mock all upstream HTTP calls — no running services needed.

---

## Files

| File | Purpose |
|------|---------|
| `app.py` | FastAPI entry point, endpoints, lifespan |
| `service.py` | Core logic: upstream calls, Monte Carlo simulation |
| `models.py` | Pydantic request/response schemas |
| `config.py` | Environment variables and defaults |
| `requirements.txt` | Runtime dependencies |
| `requirements-dev.txt` | Test dependencies |
| `tests/unit/test_service.py` | Unit tests (26 tests) |
