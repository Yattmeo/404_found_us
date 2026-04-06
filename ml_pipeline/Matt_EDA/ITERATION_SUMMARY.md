# Matt_EDA: Iteration History & Technical Summary

**Scope:** ~4 months of research (Jan–Apr 2026) on merchant processing-cost and volume forecasting  
**Domain:** MCC 5411 (Grocery / Supermarkets), 7,981 merchants, 131K rows, 2010–2019  
**Objective:** Given limited onboarding data for a new merchant, forecast (a) average processing-cost percentage, (b) total processing value (TPV), and (c) weekly volume — with calibrated prediction intervals

---

## Phase 0 — Exploratory Data Analysis (Jan 2026)

**Notebooks:** `ARCHIVE/01_EDA_Data_Exploration.ipynb`, `ARCHIVE/ZZ_EDA_0.1.ipynb`

- Loaded HuggingFace Financial_Transactions dataset, filtered to MCC 5411.
- Weekly aggregation of transaction count, total amount, average amount.
- Built 91 engineered features (temporal, 7-lag, 4-window rolling stats, difference, trend).
- Profiled data quality: removed incomplete boundary weeks (first/last), leaving 512 clean weeks.
- Key stats: weekly CV 5–10 %, steady 0.28 %/week growth, clear seasonal patterns.
- Trained baseline models (mean, naïve, MA-4, linear regression) then Random Forest, XGBoost, LightGBM, CatBoost, and ensembles.
- Best single model: LightGBM (R² = 0.95, MAPE 0.53 % for total amount).
- Transfer-learning test: 7-year pre-train + 4-week fine-tune → R² 0.69–0.96.
- Robustness test across 15 store profiles (scale × noise): fine-tuning critical for adaptation.

**Outcome:** Confirmed ML can beat naïve baselines on weekly metrics given enough history. Highlighted that short context windows are the real deployment constraint.

---

## Phase 1 — Clustering & Feature Segmentation (Feb 2026)

**Notebooks:** `Clustering/base cost features/`, `Clustering/transaction type features/`, `Clustering/Dataset Creation/`

### 1a. Dataset Creation & Cost Enrichment
- Created temporal train/validate/test splits for MCC 5411 (merchant-level, no leakage).
- Appended processing cost fields (`proc_cost_pct = proc_cost / amount`) from cost-type reference table.
- Generated cost-type percentage fingerprints per merchant (share of each `cost_type_ID`).

### 1b. Base-Feature Clustering
- Extracted yearly merchant-level features: txn count, total amount, avg amount, cost stats.
- Applied clustering (K-Means, hierarchical) to segment merchants by scale and cost profile.
- Used to understand population diversity, not directly in final models.

### 1c. Transaction-Type KNN (Monthly & Yearly)
- Built kNN on cost-type distribution fingerprints to find "similar merchants."
- Tested monthly sliding windows and yearly windows.
- Confirmed cost-type fingerprint cosine similarity is a strong proxy for merchant similarity.
- This became the foundation of the peer-pool concept used in all later models.

**Key insight:** Merchant similarity is best captured by *what* they sell (cost-type mix) rather than *how much* they sell. Cosine similarity on cost-type vectors became the standard matching method.

---

## Phase 2 — Supervised Learning & Linear Regression Root-Cause (Feb–Mar 2026)

**Notebooks:** `Supervised learning/Supervised learning tests.ipynb`, `Supervised learning/Modelling Benchmarks.ipynb`  
**Docs:** `LINEAR_REGRESSION_ROOT_CAUSE_ANALYSIS.md`, `README_LINEAR_REGRESSION_ANALYSIS.md`

### The Linear Regression Failure
- Initial weekwise LR/Ridge predicted *residuals from context mean* → 34 % worse than plain context-mean baseline.
- Root cause: by construction, residuals are zero-centred; any learned non-zero adjustment adds noise.
- Secondary issues: feature cascade (stale features beyond week 5), pool-vs-test distribution mismatch.
- Fix verified: switch to direct absolute prediction + hybrid blending.

### Broader Benchmark
- Compared context-mean, weekwise LR, Ridge, SARIMA, and early kNN approaches on weekly proc_cost_pct.
- Context mean was a surprisingly strong baseline; beating it required structural changes.

**Key insight:** For cost-rate forecasting, the merchant's own recent average is hard to beat. Models must add signal *beyond* that average to justify complexity.

---

## Phase 3 — SARIMA-Based Weekly Services (Mar 2026)

**Notebooks:** `isolated_service_lab/isolated_service_testing.ipynb`, `isolated_service_lab/methods_test_17mar.ipynb`  
**Services:** `GetCostForecast Service`, `GetVolumeForecast Service`

### KNN Quote Service
- `/getQuote`: match onboarding merchant to k=5 nearest historical merchants (Euclidean on aggregated features); return their next 3 months' proc_cost_pct.
- `/getCompositeMerchant`: return a composite weekly feature time series (weighted mean of k=5 neighbours) for downstream SARIMA consumption.
- Filters by MCC and card_types. Backed by SQLite or external DB.

### GetCostForecast (weekly proc_cost_pct)
- Consumes composite weekly features from KNN.
- Fits SARIMA/SARIMAX via AIC-guided grid search on the composite series.
- Aligns SARIMA-generated onboarding-window values to onboarding actuals.
- **Guarded calibration:** a linear scaling of the raw SARIMA forecast is applied only if it improves context-window fit (checked by constrained intercept/slope).
- Returns 12-week forecasts with 95 % confidence intervals.

### GetVolumeForecast (weekly total_proc_value)
- Same architecture as GetCostForecast but targets weekly dollar volume.
- Improvement backlog documented: hurdle models for intermittent merchants, anomaly handling, sparse-series fallbacks.

### Multi-Merchant Evaluation
- Automated evaluation scripts test 10–20 random target merchants against a reference pool.
- Per-merchant and aggregate MAE/RMSE reported.
- Calibrated SARIMA consistently outperforms raw SARIMA; context-mean anchoring prevents drift.

**Key insight:** SARIMA on a *composite* of similar merchants is more stable than SARIMA on scarce onboarding data alone. Guarded calibration prevents overcorrection.

---

## Phase 4 — M8/M9/M10 Pipeline: Monthly Huber Models (Mar 2026)

**Notebooks:** `Supervised learning/m8_pipeline_c1.ipynb` through `m8_pipeline_final_c6.ipynb`  
**Doc:** `M8_PIPELINE_FINDINGS.md`

This was the core modelling effort. It shifted from weekly to **monthly** aggregation and from SARIMA to **HuberRegressor** for the point forecast, with **split-conformal prediction intervals**.

### 4a. Problem Setup
- Target: `avg_proc_cost_pct` per merchant per month.
- Sliding-window scenarios: `CONTEXT_LEN` months of history → predict `HORIZON_LEN = 3` next months.
- Merchant-level 60/20/20 split (train/calibrate/test). No merchant appears in multiple splits.

### 4b. Model Evolution

| Model | Description | CV MAE (pp) |
|-------|-------------|-------------|
| Baseline | Predict context-window mean | 1.257 |
| M8 — Flat Huber | 4 context features (mean, std, trend, last) | 1.217 |
| **M9 — kNN Pool Huber** | **M8 + pool_mean + pool_mean_gap (kNN anchor)** | **1.213** |
| M10 — kNN Deviation Huber | Predict deviation from pool mean | 1.218 |

**M9 was selected** — 3.5 % below baseline. The kNN pool-mean anchor provides soft regularisation: the model is told "your peers average X" and learns to adjust from there. Three separate models fitted per horizon step (t+1, t+2, t+3).

### 4c. Context-Length Experiments
Tested `CONTEXT_LEN ∈ {1, 3, 6}`. Longer context gives richer features and tighter intervals, but the 6-month requirement limits applicability to merchants with enough history. All three are supported at inference via context-length snapping (uses the longest available).

### 4d. SVD Feature Extension (M11)
- `m11_svd_features_c1.ipynb`, `m11_svd_features_c3.ipynb`: added SVD-based latent features from cost-type distributions.
- Did not improve over M9 for avg_proc_cost_pct. Added complexity without gain.

### 4e. Unified Context-Length Evaluation
- `m8_unified_ctx_eval.ipynb`: standardised eval across ctx=1, 3, 6 with consistent baselines.
- `m8_unified_ctx_eval_TPV.ipynb`: same framework adapted for TPV (see Phase 5).

### 4f. Rolling Temporal Cross-Validation
- 9 temporal folds on training merchants. Strict time cutoffs prevent leakage.
- M8 Rolling CV avg MAE: –5.8 % vs baseline across folds (2017, 2018, 2019).
- Per-fold: Fold 2017 –9.6 %, Fold 2018 –13.6 %, Fold 2019 –11.3 %.

**Key insight:** Anchoring predictions on a kNN peer-pool mean is the single most effective modelling decision. It stabilises predictions for volatile merchants without hurting stable ones.

---

## Phase 5 — Conformal Prediction Intervals & Stratification (Mar–Apr 2026)

**Notebooks:** `m8_pipeline_c6.ipynb`, `m8_pipeline_final_c6.ipynb`  
**Docs:** `M8_PIPELINE_FINDINGS.md` §6–§14, `M8_STRATIFICATION_EXPERIMENT_SUMMARY.md`

### 5a. Flat (Uniform) Conformal Intervals
- Pool-local split conformal on the validate split (192 merchants).
- Target coverage: 90 %. Achieved: 90.6 %. Average half-width: ±4.02 pp.
- Problem: one-size-fits-all width. Stable merchants get over-wide intervals; volatile merchants get under-wide.

### 5b. The Stratification Journey (12 experiments)

The following sequence was explored to reduce interval conservatism:

1. **Two-bucket CoV split** → too coarse.
2. **Multi-bucket CoV (3–5 bins)** → unaligned bucket geometry.
3. **Auto-selected quantile buckets** → improved locally, worsened globally.
4. **Asymmetric tail-aware CoV buckets** (`50/85`, `70/90`, etc.) → first real improvement.
5. **Effective half-width correction** (after lower-bound clip to 0) → critical measurement fix.
6. **Best CoV-only result:** `low-mid-high_70_90` — coverage 0.903, half-width ±3.87 pp (vs baseline ±4.02). Small but robust.
7. **Leak-free holdout selection** → correct practice, didn't change directional result.
8. **Linear residual-risk model** (4 context features) → promising on holdout, failed deployment guard.
9. **GBR residual-risk model** (cross-fitted, 6 features) → stronger holdout gains, still failed guard.
10. **Peer-pool composition features** → reasonable extension, didn't cross guard.
11. **Horizon-specific risk models** → more sophistication, no test improvement.
12. **Continuous width adjustment** (monotone curve vs hard buckets) → still failed guard.

**Pattern:** More complex risk models improved holdout-set intervals but did not generalise to the final test year. Simpler CoV-based approaches were more robust.

### 5c. Final Deployed Stratification

Ultimately the notebook settled on a **GBR-based 6-feature risk model** (`gbr_all6`), which the pipeline findings document recommends:

| Variant | Test Coverage | Avg Half-Width | Width Reduction |
|---------|---------------|----------------|-----------------|
| Flat conformal | 0.906 | ±4.02 pp | — |
| **gbr_all6** | **0.892** | **±3.36 pp** | **–16.3 %** |
| gbr_ctx4 | 0.900 | ±3.62 pp | –10.0 % |

Risk features and importances:
- `pool_mean_gap_ratio` (69.9 %) — how different the merchant is from its kNN peers
- `residual_cv` (11.8 %), `context_std` (8.2 %), others < 6 %

**Deployment guard:** coverage ≥ 0.870 (soft floor) AND width gain ≥ 0.05 pp. Prevents shipping a stratification that sacrifices coverage without meaningful tightening.

**Drift diagnostics:** Spearman ρ = 1.00 on risk-score rank ordering across 2018 and 2019 holdout years. Top-20 riskiest merchants miss coverage 4.9–7.2× more than bottom-20 — strong discriminative power.

**Key insight:** `pool_mean_gap_ratio` (deviation from peer average) is the dominant risk signal. Merchants that behave unlike their neighbours are hardest to cover. Simple CoV misses this.

---

## Phase 6 — TPV (Dollar Volume) Forecasting Pipeline (Apr 2026)

**Notebook:** `m8_unified_ctx_eval_TPV.ipynb`  
**Service:** `GetTPVForecast Service v2`  
**Doc:** `services/GetTPVForecast Service v2/REPORT.md`

Seven model versions tested, all predicting in log-space (`log1p(TPV)`), evaluated in dollar-space:

| Version | Key Change | Beats Baseline? |
|---------|-----------|-----------------|
| v1 | 4-feature Huber, log conformal | No — Jensen inequality blows up dollar intervals |
| v2 | 7 features | No |
| v3 | 11 features, GBR | No (and 82 min training) |
| v4 | GBR + clipping + calibration boost | No |
| v5 | Dollar-space conformal + bias correction | No — targets mean not median |
| **v6** | **Dollar-weighted, no bias correction** | **Yes — all 3 context lengths** |
| v7 | 17 exogenous features | No (ctx=3, 6 regress) |

### Why v6 Wins
Two critical insights:
1. **No Jensen bias correction (α=0):** `expm1(pred)` is the conditional *median*, which minimises MAE. Bias correction targets the conditional *mean*, inflating MAE.
2. **Dollar-weighted sample weights:** `sw = expm1(context_mean) / log1p(txn_count)`. Without this, the regression optimises log-error uniformly, but dollar errors are dominated by high-TPV merchants.

### v6 Results

| Context | Baseline MAE | v6 MAE | Improvement |
|---------|-------------|--------|-------------|
| ctx=1 | $119 | $113 | –5.0 % |
| ctx=3 | $98 | $97 | –1.0 % |
| ctx=6 | $94 | $93 | –1.1 % |

Coverage: 0.895–0.913 (near or above 90 % target). Intervals in dollars (not log), directly interpretable.

**Key insight:** TPV is dominated by persistence — last month's volume is the strongest predictor. ML ceiling is low. Exogenous features (seasonality, merchant age, macro trend) added noise.

---

## Phase 7 — Production Services (Mar–Apr 2026)

Five microservices were built, all dockerised FastAPI apps:

| Service | Port | Target | Granularity | Method |
|---------|------|--------|-------------|--------|
| KNN Quote Service | 8080 | Peer matching | — | k=5 Euclidean + cosine |
| GetCostForecast | 8091 | proc_cost_pct | Weekly | SARIMA + guarded calibration |
| GetVolumeForecast | 8092 | total_proc_value | Weekly | SARIMA + guarded calibration |
| GetAvgProcCostForecast v2 | 8092 | avg_proc_cost_pct | Monthly | M9 HuberRegressor + GBR conformal |
| GetTPVForecast v2 | 8092 | TPV ($) | Monthly | v6 HuberRegressor + dollar conformal |

### Architecture Pattern (v2 services)
1. **Offline `train.py`:** generates artifacts per (MCC, context_len) — models, scaler, calibration residuals, risk models, stratification knots.
2. **Hot-reload watcher:** background thread polls `config_snapshot.json` every 60s; new artifacts loaded without restart.
3. **3-tier conformal fallback:** Local (peer residuals) → Stratified (GBR risk bucket) → Global q90.
4. **DB-backed pool computation:** kNN peer discovery and pool-mean features computed at inference time from the reference database.

### Integration Testing
- `unified_service_visual_test.py`: single-merchant end-to-end with plots.
- `multi_merchant_service_eval.py`: 10–20 random targets, aggregate MAE/RMSE.
- `multi_merchant_volume_service_eval.py`: same for volume forecasting.
- Isolated service lab for safe experimentation without affecting production copies.

---

## Key Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| kNN peer-pool anchoring | Strongest single modelling lever: grounds prediction on similar merchants rather than global average |
| HuberRegressor over OLS/GBR | Robust to outliers (ε = 1.35), fast, competitive with GBR at fraction of training time |
| Separate models per horizon step | Allows step-specific seasonality and mean-reversion dynamics |
| Split conformal for intervals | Distribution-free, finite-sample coverage guarantee; works on any point predictor |
| GBR risk stratification | 16 % width reduction; `pool_mean_gap_ratio` dominant feature at 70 % importance |
| Dollar-space conformal for TPV | Avoids Jensen-inequality blow-up from log→dollar back-transform |
| No bias correction for TPV | Targets conditional median (MAE-optimal) instead of conditional mean |
| Dollar-weighted training for TPV | Aligns log-space regression with dollar-space evaluation metric |
| Deployment guard | Prevents shipping stratification that fails on held-out test; protects against overfit |
| Monthly aggregation for M8/M9 | Weekly data too noisy for merchant-level cost-rate forecasting; monthly smooths noise |

---

## What Didn't Work (and Why)

| Approach | Failure Mode |
|----------|-------------|
| Weekwise LR residual-from-mean | Zero-centred residuals guarantee model can't beat baseline |
| SVD latent features (M11) | Cost-type distributions already captured by kNN; SVD adds redundant info |
| Complex risk models (linear, GBR, horizon-specific, continuous width) | Improve calibration-holdout but don't generalise to test — temporal drift in risk rankings |
| Jensen bias correction (TPV v5) | Targets conditional mean, inflates dollar MAE; median is the MAE-optimal estimand |
| Exogenous features for TPV (v7) | TPV dominated by persistence; seasonality/age/macro signals are noise at merchant level |
| GBR for main TPV predictor (v3/v4) | Overfits small merchant-level samples, 3× slower, marginal log-MAE gain |

---

## Final Model Performance Summary

### avg_proc_cost_pct (M9, ctx=6, MCC 5411)

| Metric | Value |
|--------|-------|
| Point MAE | 1.14 pp (–9.2 % vs baseline) |
| Horizon t+1 / t+2 / t+3 MAE | 1.09 / 1.14 / 1.19 pp |
| Conformal coverage (flat) | 90.6 % |
| Conformal coverage (gbr_all6) | 89.2 % |
| Half-width (gbr_all6) | ±3.36 pp (–16.3 % vs flat) |

### TPV (v6, ctx=6, MCC 5411)

| Metric | Value |
|--------|-------|
| Dollar MAE (CV) | $93 (–1.1 % vs baseline) |
| Dollar MAE (test) | $94 |
| Conformal coverage | 90.7 % |
| Half-width | ±$312 |

### Weekly Services (SARIMA, cost-rate, single-merchant demo)

| Metric | Value |
|--------|-------|
| GetCostForecast MAE | 0.027 (calibrated) |
| KNN Quote MAE | 0.134 |

---

## Repository Map

```
Matt_EDA/
├── ARCHIVE/                        ← Phase 0: initial EDA & modelling
├── Clustering/                     ← Phase 1: merchant segmentation & kNN design
│   ├── base cost features/
│   ├── transaction type features/
│   └── Dataset Creation/
├── Supervised learning/            ← Phases 2–5: LR diagnosis, M8–M11 pipelines
│   ├── m8_pipeline_c{1,3,6}.ipynb
│   ├── m8_pipeline_final_c{3,6}.ipynb
│   ├── m8_unified_ctx_eval.ipynb
│   ├── m8_unified_ctx_eval_TPV.ipynb    ← Phase 6
│   ├── m11_svd_features_c{1,3}.ipynb
│   └── *.md                        ← findings, root-cause, stratification docs
├── KNN Demo Service/               ← Phase 1 prototype
├── isolated_service_lab/           ← Phase 3: safe SARIMA service testing
├── services/                       ← Phase 7: production microservices
│   ├── KNN Quote Service Production/
│   ├── GetCostForecast Service/
│   ├── GetVolumeForecast Service/
│   ├── GetAvgProcCostForecast Service v2/
│   ├── GetTPVForecast Service v2/
│   └── integration_tests/
└── service_eval_outputs/           ← automated eval metrics & plots
```

---

## Open Items & Future Directions

1. **Extend to other MCCs** (4121, 5812) — pipeline is MCC-agnostic by design.
2. **Dynamic k per cluster** — tune kNN k locally rather than global k=5.
3. **Online conformal re-calibration** — quarterly rolling-window quantile update.
4. **Macro / exogenous signals** — card-network mix, economic indicators (not useful for TPV but may help cost-rate).
5. **Intermittent-merchant handling** — hurdle models, Croston-style fallback for sparse activity merchants.
6. **Anomaly-aware calibration** — Huber-loss or quantile-aware calibration for skewed merchants.
