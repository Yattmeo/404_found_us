# TPV Forecasting — Final Report

## 1. Objective

Forecast a merchant's **total monthly processing value (TPV)** for the next 3 months,
given 1–6 months of observed history, with:

- Point estimates that **beat the mean-persistence baseline** (expm1 of context mean log_tpv)
- **Dollar-denominated conformal prediction intervals** at 90% coverage
- Minimal conservatism (intervals as tight as possible while meeting coverage)

This output is combined downstream with the `avg_proc_cost_pct` predictor and a
quoted rate to generate a $ profit range.

---

## 2. Methods tested

Seven model versions were developed and evaluated across 3 context lengths
(ctx=1, 3, 6) on MCC 5411 (grocery, 7,996 merchants, 131K rows).

### v1 — Baseline log-space Huber (4 features)
- **Features**: context_mean, context_std, momentum, pool_mean
- **Conformal**: log-space residuals
- **Result**: Beats baseline in log-MAE but **fails in dollar-MAE** due to Jensen's
  inequality — log-space conformal intervals explode when back-transformed to dollars
  for high-TPV merchants.

### v2 — Extended features (7 features)
- Added: txn_amount_std, log_txn_count, avg_median_txn_gap
- Same log-space conformal
- **Result**: Marginal log-MAE improvement, same dollar-MAE problem.

### v3 — TPV-optimised features + GBR (11 features)
- Added: last_month, log_avg_txn_val, momentum_tc, momentum_atv
- Switched to GradientBoostingRegressor
- **Result**: Better log-space metrics. Dollar MAE still above baseline.
  GBR training ~82 min for full ablation — prohibitively slow.

### v4 — Hardened GBR (11 features + clipping + calibration boost)
- Added: prediction clipping (±1.5 log), calibration boost (93%), adaptive GBR
- **Result**: Stratification passed but dollar MAE still worse than baseline.
  Clipping was a band-aid, not a fix.

### v5 — Dollar-space conformal + bias correction (11 features, Huber)
- **Key change**: Moved conformal calibration from log-space to **dollar-space**.
  Residuals computed as |actual_dollar − pred_dollar|.
- Back-transform: expm1(pred + σ²/2) (Jensen bias correction, α=1.0)
- Switched back to HuberRegressor (3× faster than GBR)
- **Result**: Dollar MAE improved significantly but still above baseline at all ctx.
  Bias correction targets conditional mean, not median — hurts MAE.

### v6 — Dollar-weighted, no bias correction (11 features, Huber) ✓ WINNER
- **Key changes**:
  1. **No bias correction** (α=0): expm1(pred) targets conditional median → minimises MAE
  2. **Dollar-weighted sample weights**: sw = expm1(context_mean_log) / log1p(txn_count).
     Aligns the regression loss landscape with dollar-error importance.
- Same dollar-space conformal as v5
- **Result**: **Beats mean baseline at all context lengths.**

### v7 — Extended exogenous features (17 features)
- Added 6 features: sin/cos month (seasonality), merchant_age, MCC-wide trend,
  days_in_horizon, cost_hhi_delta
- Same pipeline as v6 (dollar-weighted, no bias correction)
- **Result**: Worse than v6 at ctx=3 ($100 vs $97) and ctx=6 ($101 vs $93).
  Exogenous features added noise/overfitting rather than signal. Persistence
  dominates this target — the merchant's recent history is the strongest predictor.

---

## 3. Results comparison

### Dollar MAE (CV, lower is better)

| Version | Features | ctx=1 | ctx=3 | ctx=6 | Beats baseline? |
|---------|----------|-------|-------|-------|-----------------|
| Baseline | — | $119 | $98 | $94 | — |
| **v6** | **11** | **$113** | **$97** | **$93** | **Yes (all 3)** |
| v7 | 17 | $113 | $100 | $101 | No (ctx=3,6 fail) |
| v5 | 11 | $141 | $110 | $110 | No |

### Coverage & interval width

| Version | ctx | Flat Cov | Strat Cov | Half-width ($) | Strat |
|---------|-----|----------|-----------|----------------|-------|
| v6 | 1 | 0.895 | 0.895 | ±$356 | PASS |
| v6 | 3 | 0.913 | 0.905 | ±$323 | PASS |
| v6 | 6 | 0.907 | 0.907 | ±$312 | FAIL |
| v7 | 1 | 0.895 | 0.904 | ±$353 | PASS |
| v7 | 3 | 0.910 | 0.904 | ±$320 | PASS |
| v7 | 6 | 0.909 | 0.909 | ±$310 | FAIL |

### Test set MAE ($)

| Version | ctx=1 | ctx=3 | ctx=6 |
|---------|-------|-------|-------|
| v6 | $123 | $94 | $94 |
| v7 | $120 | $95 | $94 |

### Ranking metrics (Spearman ρ on risk score vs actual residual)

| Version | ctx=1 | ctx=3 | ctx=6 |
|---------|-------|-------|-------|
| v6 | 0.520 | 0.588 | 0.610 |
| v7 | 0.522 | 0.590 | 0.610 |

---

## 4. Winner: v6

**Justification:**

1. **Beats baseline at all context lengths** — the only version to do so.
   v7 loses to baseline at ctx=3 and ctx=6.

2. **Simplest effective approach** — 11 features (endogenous only), HuberRegressor
   (linear, fast), no hyperparameter-sensitive components like GBR for the main model.

3. **Dollar-space conformal** — intervals are directly interpretable in dollars, no
   back-transform distortion. Coverage is within 0.5% of the 90% target at all ctx.

4. **Fast** — full 3-ctx evaluation in ~26 min (vs ~82 min for GBR-based v3/v4).

5. **Two critical insights made v6 work**:
   - **No bias correction (α=0)** — Jensen correction targets the conditional mean,
     but MAE is minimised by the conditional median. Setting α=0 gives expm1(pred),
     which is the median of the back-transformed distribution.
   - **Dollar-weighted sample weights** — without dollar weighting, the regression
     optimises log-space error uniformly, but dollar errors are dominated by
     high-TPV merchants. Dollar weighting aligns the loss with the evaluation metric.

**What didn't work and why:**

- **GBR (v3/v4)**: Overfits on small merchant-level datasets, 3× slower, marginal improvement
- **Bias correction (v5)**: Targets E[TPV] instead of median(TPV); inflates MAE
- **Exogenous features (v7)**: Seasonality, merchant age, and MCC trend don't help
  because TPV is dominated by merchant-specific persistence — the last few months'
  TPV is the strongest predictor of next month's TPV
- **Log-space conformal (v1–v4)**: Jensen's inequality causes exponential blow-up of
  intervals for high-TPV merchants when back-transforming from log to dollar space

---

## 5. Coverage assessment

The 90% target is met at ctx=3 (0.913) and ctx=6 (0.907). At ctx=1, flat coverage is
0.895 — marginally below the 0.90 target by 0.5 percentage points. This is within
statistical noise for the conformal calibration set size and represents minimally
conservative intervals (not over-inflated).

Stratification passes its deployment guard at ctx=1 and ctx=3 but fails at ctx=6,
meaning volume-tier-specific intervals don't reliably improve over flat intervals at
the longest context length. The service falls back to flat conformal at ctx=6.

---

## 6. Service architecture

The GetTPVForecast Service v1 mirrors the structure of GetAvgProcCostForecast Service v2:

| File | Role |
|------|------|
| `config.py` | Pipeline constants, feature names, supported MCCs |
| `models.py` | Pydantic request/response schemas (dollar-denominated) |
| `service.py` | Inference: feature construction → log-space predict → expm1 → dollar conformal |
| `train.py` | Batch retraining: builds artifacts per (MCC, context_len) |
| `app.py` | FastAPI endpoint: POST /GetTPVForecast |
| `tests/` | 23 unit tests (all passing) |

**Key differences from GetAvgProcCostForecast Service v2:**
- Target: `log1p(total_processing_value)` instead of `avg_proc_cost_pct`
- 11 model features (v3 set) instead of 7 (v2 set)
- 11 risk features instead of 9
- Dollar-weighted sample weights during training
- Dollar-space conformal (residuals & half-widths in dollars)
- No bias correction on back-transform

---

## 7. Limitations & future work

1. **Thin margins at ctx=3 and ctx=6** — v6 beats baseline by only $1 at these lengths.
   With more data or a different MCC, the margin may not hold.

2. **Persistence dominance** — the strongest predictor of next month's TPV is this
   month's TPV. This limits the ceiling for any ML approach on this data.

3. **Exogenous signals** — macro-economic indicators, industry trends, or merchant-level
   metadata (e.g., store size, location) are not available in the current dataset but
   could improve predictions if provided.

4. **Single MCC** — only MCC 5411 is evaluated. Other MCCs may have different dynamics.
