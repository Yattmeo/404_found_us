# Merchant Forecasting Architecture — Defence Briefing

> **Purpose of this document:** Equip a presenter with the key talking points, rationale, and ready answers for defending each architectural decision. Organised as "what it does → why it was built this way → what to say if challenged."

---

## 1. What the System Does (30-Second Pitch)

Given a new merchant's raw transaction history, the system forecasts their **processing cost %**, **total processing volume (TPV)**, and **expected profit** over the next 3 months — each with calibrated uncertainty intervals. It runs as 4 independent microservices that can be called individually or orchestrated together.

```
  Raw Transactions
        │
   ┌────┴────────────────────────┐
   ▼                             ▼
  ┌──────────────┐    ┌──────────────────────────┐
  │ KNN Quote    │    │ ┌──────────────────────┐ │
  │ :8080        │    │ │ AvgProcCost v2 :8092 │ │ HuberRegressor ×3
  │ k=5 Euclid.  │    │ │ target: cost%        │ │ + GBR risk strat.
  │ → pool means │    │ └──────────┬───────────┘ │
  │ → composite  │    │            │             │
  │   features   │    │ ┌──────────┴───────────┐ │
  └──────────────┘    │ │ TPV v2 :8093         │ │ HuberRegressor ×3
                      │ │ target: $TPV         │ │ dollar-weighted
                      │ │ dollar-space conformal│ │
                      │ └──────────┬───────────┘ │
                      └────────────┼─────────────┘
                                   │
                         ┌─────────┴─────────┐
                         ▼                   ▼
                   ┌─────────────────────────────┐
                   │  Profit Forecast :8094      │
                   │  Monte Carlo (N=10,000)     │
                   │  profit = TPV×(fee − cost)  │
                   └─────────────────────────────┘
```

---

## 2. The 4 Services at a Glance

| Service | What it predicts | How | Key talking point |
|---|---|---|---|
| **KNN Quote** (:8080) | Finds 5 most similar historical merchants | k-NN (k=5, Euclidean) on monthly features | "We don't guess — we find real merchants that looked like this one" |
| **AvgProcCostForecast v2** (:8092) | Processing cost % for next 3 months | HuberRegressor × 3 + conformal intervals | "Point forecast + guaranteed coverage intervals, with risk-adaptive widths" |
| **TPVForecast v2** (:8093) | Total Processing Volume ($) for next 3 months | Same engine, dollar-weighted in log-space | "Optimised for dollar accuracy — high-value merchants matter more" |
| **ProfitForecast** (:8094) | Profit distribution: P(profitable), break-even fee, CI | Monte Carlo (10k simulations) on the two forecasts above | "Propagates uncertainty honestly, gives the business a probability of profit" |

---

## 3. Service-by-Service: What to Know and What to Say

### 3a. KNN Quote Service — "The Matching Engine"

**What it does:** Takes a new merchant's transactions and finds the 5 most similar merchants from the historical reference pool. Returns their composite features as a proxy for "what merchants like this one typically look like."

**How matching works:**
1. Aggregate the new merchant's transactions into monthly features (cost-type %, avg amount, proc_cost_pct)
2. Build a 7-dimensional query vector
3. Run `NearestNeighbors(k=5, metric='euclidean')` against the reference pool
4. Return the neighbours' composite weekly feature history (mean & std across all 5)

**If challenged — "Why k=5? Why Euclidean?"**
- k=5 balances signal (enough neighbours to smooth noise) against specificity (not so many that the composite becomes generic). This was validated via ablation.
- Euclidean distance works well on the normalised feature space. Cosine similarity was tested for the transaction-type matching (where it's used) but Euclidean outperforms on the aggregated monthly profile.

**If challenged — "Why not just use the merchant's own data?"**
- New/onboarding merchants have limited history. The pool mean from similar merchants provides a strong prior, and it turned out to be the single most predictive feature across all model variants.

---

### 3b. AvgProcCostForecast v2 — "The Cost Predictor"

**What it does:** Predicts monthly average processing cost % for months +1, +2, +3 with calibrated confidence intervals.

**How prediction works:**
1. Aggregate raw transactions → monthly summaries
2. Look up the merchant's peer reference values (flat pool mean + k-NN pool mean from the KNN service's reference DB)
3. Build a 7-feature vector: `context_mean`, `context_std`, `momentum`, `pool_mean`, `intra_std`, `log_txn_count`, `mean_median_gap`
4. Feed into 3 separate HuberRegressors (one per horizon month)
5. Wrap point predictions with conformal prediction intervals (see §5 below)

**If challenged — "Why HuberRegressor instead of SARIMA / XGBoost / neural nets?"**
- HuberRegressor is robust to outliers (ε=1.35 clips influence of extreme residuals), trains in milliseconds, and is fully interpretable. On this dataset, more complex models (SARIMA, GBR, Trees, MLP) did not meaningfully improve point-forecast MAE compared to the mean baselines but added latency and opacity. The competitive edge comes from the *features* (especially pool_mean) and the *interval calibration*, not model complexity.

**If challenged — "What does 'conformal' mean?"**
- Conformal prediction is a distribution-free method that guarantees coverage without assuming normality. We calibrate on held-out data: the interval width is set so that 90% of calibration merchants fall inside it. This gives a formal, testable guarantee (see §5).

---

### 3c. TPVForecast v2 — "The Volume Predictor"

**What it does:** Predicts total processing volume in dollars for months +1, +2, +3 with dollar-denominated confidence intervals.

**Same engine as the cost service, with 3 deliberate differences:**

| Design choice | What | Why |
|---|---|---|
| **Log-space modelling** | Predicts `log1p(TPV)`, back-transforms via `expm1()` | TPV spans orders of magnitude; log-space stabilises variance |
| **Dollar-weighted loss** | Training weights ∝ `expm1(log_tpv)` | A $10 error on a $100K merchant matters more than on a $1K merchant — aligns model accuracy with business impact |
| **No bias correction (α=0)** | Targets the conditional *median*, not mean | Minimises MAE in dollar space, which is the business metric. Mean-targeting would inflate predictions for high-variance merchants |
| **Dollar-space conformal** | Residuals computed as `|actual_$ − pred_$|` | Intervals in dollars are directly interpretable for business decisions |

**If challenged — "Why not bias-correct the log→dollar transform?"**
- The standard Jensen correction (`expm1(pred + σ²/2)`) targets the conditional mean, which inflates forecasts for volatile merchants and increases MAE. Omitting it (α=0) targets the median, which empirically minimises dollar-space MAE. This was validated in ablation (v5 with correction vs v6 without).

---

### 3d. ProfitForecast — "The Business Outcome Layer"

**What it does:** Takes the TPV and cost forecasts with their uncertainty intervals, runs 10,000 Monte Carlo simulations, and returns: point profit estimate, full profit distribution, probability of profitability, break-even fee rate, and suggested fee for a target margin.

**How simulation works:**
1. Convert each service's conformal half-width to a Gaussian σ: `σ = half_width / z_α`
2. Sample: `tpv ~ N(mid, σ_tpv)` and `cost ~ N(mid, σ_cost)` independently per simulation
3. Clamp negatives to zero (TPV and cost cannot be negative)
4. Compute: `profit = tpv × (fee_rate − cost_pct)`
5. Derive percentiles, probability of profitability, etc.

**If challenged — "Why sample TPV and cost independently?"**
- Empirically validated: ρ(log_tpv, avg_proc_cost_pct) ≈ 0.14 on MCC 5411 data. At correlations below ~0.15, joint sampling changes interval widths by <2%, which is within conformal calibration noise. Independence is the simpler, more transparent choice.

**If challenged — "Why Gaussian? The underlying distributions might not be normal."**
- The conformal intervals themselves are distribution-free. The Gaussian is only used to *propagate* those intervals through the profit calculation. The Central Limit Theorem applies here because each forecast aggregates over multiple months of transaction data. The Monte Carlo approach also naturally handles the non-linearity of `tpv × (fee − cost)` that a Gaussian delta-method approximation would miss.

---

## 4. Infrastructure Decisions Worth Knowing

**Database abstraction:** All services share a `repository.py` with a pluggable backend — SQLAlchemy for production (PostgreSQL/MySQL/MSSQL via `DB_CONNECTION_STRING` env var) or SQLite for local development. Same schema everywhere.

**Hot-reload:** The v2 forecast services (cost, TPV) poll a `config_snapshot.json` file every 60 seconds. When the training pipeline produces new model artifacts, services pick them up without restart. This enables continuous retraining without downtime.

**Schema:**
```sql
CREATE TABLE transactions (
  transaction_id INTEGER PRIMARY KEY,
  date DATE, amount FLOAT, merchant_id INTEGER, mcc INTEGER,
  card_brand TEXT, card_type TEXT, cost_type_ID INTEGER, proc_cost FLOAT
);
CREATE TABLE cost_type_ref (cost_type_ID INTEGER PRIMARY KEY);
```

---

## 5. The Conformal Interval System — "Why Our Intervals Are Trustworthy"

This is likely the most scrutinised component. The system uses a 3-tier conformal fallback, embedded in both v2 forecast services:

| Tier | When it activates | How it works | Why |
|---|---|---|---|
| **1. Local** | ≥10 calibration residuals from the merchant's k-NN peers | Uses the 90th percentile of peer residuals as the interval half-width | Best case: merchant-specific, tightest intervals |
| **2. Stratified** | Peer data insufficient | GBR risk model scores the merchant → maps to a risk bucket → interpolated quantile from that bucket's calibration residuals | Adapts width to the merchant's predicted difficulty |
| **3. Global** | Risk model unavailable or edge case | Uses the 90th percentile of the entire calibration set | Safe fallback: always satisfies coverage guarantee |

**Key numbers to cite:**
- Stratified intervals are **16.3% narrower** than the global baseline while maintaining 89.2% joint coverage (target: 87% floor)
- There is a **deployment guard**: stratification only activates if coverage within 3% of target AND width savings ≥ 0.05 pp. If the guard fails, the system falls back to global intervals.

**If challenged — "90% target but 89.2% actual?"**
- Losing 0.8% joint coverage for 16.3% improvement in interval conservatism is a worthwhile tradeoff. Conformal prediction guarantees marginal coverage asymptotically; finite-sample fluctuation of ~1% is expected and documented.

---

## 6. The Risk Model — "How We Know Which Merchants Are Hard to Predict"

A Gradient Boosting Regressor (120 trees, depth=2, lr=0.05) trained to predict each merchant's worst-case forecast error (`max_abs_residual` across 3 months). Its output is a continuous risk score that drives the stratified intervals in §5.

**The single most important insight:** 70% of predictive power comes from one feature — `pool_mean_gap_ratio`, which measures how different a merchant behaves from its transaction-type peers. Merchants that *don't look like their peers* are the hardest to forecast. Simple volatility metrics (std, trend) matter much less.

| Feature | Importance | Plain English |
|---------|------------|---------------|
| `pool_mean_gap_ratio` | **69.9%** | "How much does this merchant deviate from similar merchants?" |
| `residual_cv` | 11.8% | "How inconsistent is this merchant's own cost pattern?" |
| `context_std` | 8.2% | "How volatile is recent history?" |
| `max_abs_residual` | 5.4% | "What was the worst prediction error we've seen for this merchant?" |
| `context_trend_abs` | 2.9% | "Is cost trending sharply up or down?" |
| `pool_residual_mean` | 1.8% | "How well do we predict this merchant's peer group in general?" |

**Risk tiers:**

| Tier | Who | Interval width |
|---|---|---|
| Low risk (bottom 40%) | Behaves like peers | ±2.71 pp |
| Mid risk (40th–80th pctl) | Some peer deviation | ±3.41 pp |
| High risk (top 20%) | Outlier vs peer group | ±4.63 pp |

**Temporal stability:** The risk ranking held perfectly (Spearman ρ = 1.00) across 2018 and 2019 holdout years. The top 20% riskiest merchants accounted for 4.87× (2018) and 7.20× (2019) more coverage misses — the model genuinely identifies the hard cases.

---

## 7. Clustering — "How We Define 'Similar Merchants'"

Three clustering workstreams, each serving a different purpose:

### Transaction-Type k-NN (directly integrated into services)
- Each merchant has a 61-dimensional "fingerprint" of cost_type percentages
- Cosine similarity finds the k=10 nearest neighbours
- The resulting `pool_mean` (average cost/TPV of peers) is the **single most predictive feature** across all model variants — this is the core bridge between clustering and forecasting

**If challenged — "Why 61 dimensions?"**
- These are the distinct cost_type_IDs in the data. Each represents a real category of transaction processing (interchange tiers, assessment fees, etc.). The fingerprint captures the merchant's *mix* of processing types, which is a strong proxy for their cost structure.

### MCC 4121 Full Clustering (Taxicabs)
- 8 features (cost %, amount, volume, payment mix, fraud rate)
- Tested K-Means, Hierarchical, DBSCAN, and GMM
- **GMM selected** — best Silhouette (~0.48–0.55), provides probabilistic soft assignments with >90% cluster confidence
- Segments reveal distinct merchant profiles: cost-efficient vs high-cost, chip-only vs legacy, small-frequent vs large-bulk

### MCC 5411 Base Clustering (Grocery)
- Simpler 2-feature baseline (`cost_percent`, `cost_percent_stdev`)
- Temporally validated: train 2017 → validate 2018 → test 2019

---

## 8. Model Evolution — "Why This Architecture and Not Something Simpler/Fancier"

| Iteration | What changed | Result | Lesson |
|---|---|---|---|
| M8 | HuberRegressor on basic context stats | MAE ~1.26 pp | Robust regression works, but features are weak |
| M9 | Added `pool_mean` from k-NN peer matching | MAE ~1.21 pp (−3.5%) | **Peer reference is the biggest single lever** |
| M9 + GBR risk | Added stratified conformal intervals | Same MAE, 16% narrower intervals | Risk-adaptive intervals add real value without changing point forecasts |
| M11 | Tried SVD on cost_type features | No improvement | High-dimensional cost features don't compress well — the k-NN summarisation (pool_mean) already captures the signal |
| TPV v6 (final) | Dollar-weighted, log-space, α=0 | Best dollar MAE | Aligning the loss with the business metric matters |

**The takeaway:** The accuracy gains came from *better features* (peer matching, pool_mean) and *better calibration* (conformal intervals, risk stratification), not from more complex models. HuberRegressor beat GBR, MLP, and CQR on the point forecast task because the feature engineering had already done the heavy lifting.

---

## 9. Anticipated Hard Questions

**Q: "Why microservices instead of a single model?"**
A: Each service solves a different prediction problem with different targets, loss functions, and output units. Separating them means each can be tested, deployed, and scaled independently. The profit service is purely stateless simulation — it doesn't need model artifacts at all.

**Q: "How does this handle a brand-new merchant with no history?"**
A: The KNN Quote service only requires the *type* of transactions (MCC, card_types) to find peers. Even one month of data is enough to build the feature vector. The conformal intervals are wider for low-data merchants by design (pool_mean deviates more → higher risk score → wider interval).

**Q: "What happens when the model is wrong?"**
A: The conformal intervals are designed to be honest about uncertainty. A merchant the system is unsure about gets wider intervals, not a hedged point prediction. The deployment guard ensures stratification only activates when coverage has been validated on held-out data.

**Q: "Can this scale to other MCCs?"**
A: The architecture is MCC-agnostic. The current models are trained on MCC 5411 (Grocery). To add a new MCC, you run the same training pipeline on that MCC's data and deploy new artifacts. The service code is unchanged — only `SUPPORTED_MCCS` in config needs updating.

**Q: "Why not a deep learning approach?"**
A: With ~500–600 merchants in the training set and only 7–11 features, there isn't enough data to justify neural networks. HuberRegressor trains in milliseconds and is fully transparent. The GBR risk model (120 shallow trees) is the most complex component, and it's interpretable enough to explain which features drive risk scores.
