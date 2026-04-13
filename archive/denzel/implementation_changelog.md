# Implementation Changelog — Denzel's Monte Carlo Proposal

Hey Denzel, here's a summary of what we implemented from your proposal and what extra fixes we had to make along the way.

---

## Your Changes — All 6 Implemented ✅

### 1. Cost Sampling Logic
- Replaced the simple Gaussian sampler with your `_sample_cost_pct_soft_guardrail()` function
- Uses truncated normal for the central CI mass + exponential tails outside the CI
- Costs are still floored at 0 (no negative costs)

### 2. `_simulate_profit_month` Signature
- Added `cost_pct_ci_lower` and `cost_pct_ci_upper` optional params
- These feed directly into the soft-guardrail sampler per month

### 3. Per-Month Cost CI Wiring
- The simulation loop now pulls `proc_cost_pct_ci_lower` and `proc_cost_pct_ci_upper` from each month's forecast
- Falls back to midpoint ± global half-width when per-month bounds are missing

### 4. Break-Even Fee Rate Robustness
- `worst_cost_upper` now prefers the per-month `proc_cost_pct_ci_upper`
- Falls back to `mid + half_width` if the CI field is missing

### 5. Metadata Enrichment
- Added 3 new fields to `SimulationMetadata` in `models.py`:
  - `cost_sampling_strategy` (defaults to `"ci_shaped_soft_guardrails"`)
  - `cost_ci_tail_probability` (defaults to `0.10`)
  - `cost_ci_hard_clip` (defaults to `false`)
- These get populated in the response so we can trace what assumptions were used

### 6. Imports
- `truncnorm` added as a top-level import alongside `norm`

---

## Bug Fixes We Found During Integration

When we tested your changes end-to-end with real CSV data, the cost forecast was returning garbage (negative values like -10.8%). Your code was correct — the problem was upstream in the pipeline feeding bad data into the M9 model. Here's what we fixed:

### Bug 1: proc_cost was in the wrong units
**Where:** `backend/modules/merchant_quote/service.py`

The onboarding rows were computing `proc_cost = amount × (rate / 100)`, which gives dollar values. But the composite merchant service divides `sum(proc_cost) / sum(amount)` and expects that ratio to be ~1.5 (percentage scale, matching training data). With dollar-scale proc_cost, the ratio was ~0.015 — 100× too small. The M9 model got confused and predicted negative costs.

**Fix:** Removed the `/100` so proc_cost stays in cents-scale. Now the ratio comes out correctly at ~1.5.

### Bug 2: TPV pool means were being sent to the cost forecast
**Where:** `backend/modules/merchant_quote/service.py`

The backend was taking `pool_mean` from the TPV forecast response and passing it to the cost forecast. Problem is, TPV pool_mean is `log(total_payment_volume)` (a number like 4–8), not a cost percentage (a number like 1.5). This confused the M9 cost model badly.

**Fix:** Stop passing TPV pool means to the cost forecast. The ML service now calculates its own pool mean from the merchant's actual cost data — which is the correct behaviour.

### Bug 3: Fragile percentage-to-decimal conversion
**Where:** `backend/modules/merchant_quote/service.py`

There was a heuristic that checked `if value > 0.10: divide by 100` to convert M9 output (percentage) to decimal for the rest of the pipeline. This broke when M9 returned negative values (because of bugs 1 & 2).

**Fix:** Always divide by 100 (M9 always outputs percentage-scale by design) and floor negative values at 0.

### Bug 4: Fallback cost forecast units
**Where:** `ml_service/routes.py`

When M9 doesn't have trained artifacts for an MCC, it falls back to a simple estimate from the base cost rate. But it was using the decimal value directly (0.014) while pretending it was percentage-scale. The fallback output was 100× too small.

**Fix:** Multiply `base_cost_rate` by 100 so the fallback output matches M9's percentage-scale convention.

---

## Test Results After All Fixes

With `test_merchant_5411.csv` at 3% current rate:
- **Cost forecast:** ~1.45% mid (was showing -10.8% → 0% before)
- **Profit range:** $843–$1,835 (was $3,550–$1,128,710 before — exceeded total revenue)
- **Profitability curve:** Smooth 77.7% at 1.5% → 98.5% at 2.0% (was flat at 100% before)
- **Both tools work:** Profitability calculator and rates quotation tool share the same pipeline, so both are fixed

---

## Files Changed

| File | What Changed |
|------|-------------|
| `ml_service/modules/profit_forecast/service.py` | Your 6 changes (sampling, CI wiring, break-even, metadata) |
| `ml_service/modules/profit_forecast/models.py` | 3 new SimulationMetadata fields |
| `backend/modules/merchant_quote/service.py` | proc_cost units fix, removed TPV pool means from cost request, fixed conversion heuristic |
| `ml_service/routes.py` | Fallback cost forecast units fix |
