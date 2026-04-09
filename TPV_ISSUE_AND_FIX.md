# TPV Volume Forecast — Issue & Fix

## The Problem

The **Volume Trend** chart on the Rates Quotation Tool showed wildly wrong values (e.g. **$4,414/month** instead of **$156,658/month**).

## Why It Happened

There's a mismatch between how the model was **trained** and how data reaches it at **runtime**.

### Training (notebook)
The model was trained on **real transaction data** (`processed_transactions_4mcc.csv`, 2010–2019). Real merchants have varied transaction amounts — different ticket sizes, natural variance in `std`, `median`, `avg_ticket`, etc. The model learned to use these transaction-level patterns as features.

### Runtime (production)
The frontend only sends **two numbers**: `avg_ticket` and `monthly_transactions`. The backend then fabricates synthetic transactions — **all with the exact same dollar amount** — to feed the ML service. For example, a merchant doing $167K/month with a $51 avg ticket gets turned into 120 rows/week × $326.37 each (scaled up to preserve total volume).

### The Result
The synthetic rows produce **degenerate features** that the model never saw during training:

| Feature | Training (real data) | Runtime (synthetic) | Impact |
|---------|---------------------|-------------------|--------|
| `txn_amount_std` | ~21.8 (natural variance) | **0.0** (all identical) | -1.5σ OOD |
| `avg_median_gap` | ~2.69 (skewed distributions) | **0.0** (no skew) | -1.4σ OOD |
| `log_txn_count` | ~7.5 (thousands of txns) | **6.18** (only 480 synthetic rows) | -2.8σ OOD |
| `log_avg_txn_val` | ~2.9 (~$17 avg) | **5.79** ($326 scaled-up amount) | +2.0σ OOD |

The model sees a feature vector it was never trained on and outputs garbage.

## What We Fixed (Workaround)

Added a **sanity check** in `ml_service/modules/tpv_forecast/service.py` (step 6b):

- After the model predicts, compare each prediction to the merchant's actual observed TPV (context mean)
- If any prediction deviates by more than **2.0 log-units (~7×)** from context, flag it as unreliable
- Fall back to **extrapolation** — uses the merchant's real observed monthly TPV + momentum trend
- The extrapolation is simple but grounded in actual data, so it gives sensible numbers

Also fixed:
- **Docker log visibility** — added `PYTHONUNBUFFERED=1` to Dockerfile so startup errors aren't silently swallowed

## What This Means Right Now

- The fallback produces **flat forecasts** (context mean ± 20% CI band) — correct magnitude but no model-driven trend
- The trained HuberRegressor models are effectively **unused** when data comes via the aggregate input path (avg_ticket + monthly_txns)
- If raw transaction CSVs are uploaded directly (with natural variance), the model could work, but this path currently isn't used by the frontend

## Options to Improve

### Option A — Fix the Synthetic Data (Quick Win)
Add realistic noise to `_build_onboarding_rows` in `backend/modules/merchant_quote/service.py`:
- Sample transaction amounts from a log-normal distribution instead of uniform
- Vary counts across weeks
- This makes synthetic data look more like real data so model features stay in-distribution

**Effort:** Small. **Risk:** Low — just changes synthetic generation.

### Option B — Pass Aggregate Features Directly to the Model (Medium)
Skip the synthetic-transactions-to-features roundtrip entirely. Since the frontend already computes `avg_ticket` and `monthly_transactions`, construct the 11 model features directly from those two numbers + sensible defaults for variance-based features (e.g. use training-set medians for `txn_amount_std` and `avg_median_gap`).

**Effort:** Medium. **Risk:** Low — adds a parallel code path.

### Option C — Retrain on Larger/More Diverse Data (Longer Term)
Current training data has only **6 merchants for MCC 5499** (max ~$188K/month). The model has very little to learn from. Getting more merchant data — especially higher-volume merchants — would make the model more robust to feature distributions it hasn't seen.

**Effort:** Large (need data). **Risk:** None — strictly additive.

### Option D — Use the Raw CSV Path End-to-End (Medium)
When the user uploads a CSV, pass the actual transaction rows through to the ML service instead of computing `avg_ticket` + `monthly_txns` and fabricating synthetic rows. The real data has natural variance, so model features would be in-distribution.

**Effort:** Medium — requires frontend and backend changes. **Risk:** Low.

## Recommendation

**Option A** is the fastest path to getting the model actually working instead of falling back to extrapolation. **Option D** is the cleanest long-term fix since it eliminates the synthetic data problem entirely.
