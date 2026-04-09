# GetTPVForecast Service v2

FastAPI service that forecasts a merchant's monthly **total processing value (TPV)**
in dollars using the **TPV v1 pipeline** — a dollar-weighted HuberRegressor in
log-space with dollar-space split-conformal prediction intervals.

Sourced from notebook `m8_unified_ctx_eval_TPV.ipynb`, version **v6** (the
best-performing variant across 7 tested approaches).

**v2 change:** The caller now sends only raw transaction records and basic
forecast parameters. All feature engineering, monthly aggregation, pool-mean
computation, and kNN peer discovery are handled inside the service using a
shared reference database.

---

## How It Works

Everything is predicted in **log-space** but calibrated and delivered in **dollar-space**.

### Training (offline — `train.py`)

1. **Load & transform** — Read the merchant monthly CSV and create `log_tpv = log1p(total_processing_value)`.
2. **Generate scenarios** — Slide context windows of length 1, 3, and 6 months over each merchant's history; each window becomes one training row with an 11-feature vector and 3 horizon targets (`log_tpv` at t+1, t+2, t+3).
3. **Merchant-level split** — Split merchants (not rows) into train / calibration / test to prevent data leakage.
4. **kNN pool caches** — For every context window, compute the flat peer pool mean and a cosine-similarity kNN pool mean in log-space; cache these for use as features.
5. **Fit 3 HuberRegressors** — One model per horizon step, trained in log-space with **dollar-weighted** sample weights (`expm1(log_tpv)`) so the loss landscape aligns with the high-TPV merchants that dominate dollar error.
6. **Dollar-space calibration residuals** — On the held-out calibration fold, compute `|expm1(pred) − expm1(actual)|` per merchant; store these dollar residuals keyed by `merchant_id`.
7. **Cross-fit GBR risk models** — Train gradient-boosted regressors on 11 risk features to predict each merchant's absolute dollar residual; these power the stratified conformal tier.
8. **Select stratification scheme** — Evaluate candidate bucket boundaries against a deployment guard (coverage slack, gain thresholds); pick the best scheme or disable stratification.
9. **Write artifacts** — Persist models, scaler, calibration residuals, global quantile, risk models, stratification knots, and a `config_snapshot.json` to `artifacts/<mcc>/<context_len>/`.

### Inference (online — `POST /GetTPVForecast`)

1. **Receive request** — Accept raw transaction records (`onboarding_merchant_txn_df`) plus `mcc` and optional forecast parameters.
2. **Aggregate** — Group raw transactions by year-month; compute TPV (sum), txn count, avg, std, median, and cost-type percentages per month.
3. **Select context window** — Pick the last *N* months where *N* is the largest supported context length (6, 3, or 1) ≤ available months.
4. **Resolve model bundle** — Load the pre-trained artifact bundle for the given MCC and context length.
5. **Compute pool info from DB** — Query the reference database to calculate the flat pool mean, kNN pool mean (cosine similarity on cost-type fingerprints), and peer merchant IDs.
6. **Build feature vector** — Compute the same 11 features used in training (context summary, transaction-level stats, recency, decomposition, component momentum).
7. **Scale & predict** — StandardScaler → 3 HuberRegressor models → 3 log-space predictions (one per horizon month).
8. **Back-transform** — `expm1(pred)` for each month. No bias correction: this targets the conditional **median**, which minimises dollar MAE.
9. **Conformal interval** — A 3-tier adaptive-quantile fallback chain determines the dollar half-width:
   - **Local** — If ≥ 10 calibration residuals exist for the merchant's kNN peers, use the 90th percentile of those peer residuals.
   - **Stratified** — Otherwise, use the GBR risk model to score the merchant, bucket it, and interpolate a per-bucket quantile.
   - **Global fallback** — If stratification is disabled or the bucket is too small, fall back to the global 90th-percentile residual.
10. **Return** — Dollar point forecasts ± conformal intervals, plus metadata.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness check + loaded artifact status |
| `POST` | `/GetTPVForecast` | Run TPV forecast |

---

## Input (Request)

`POST /GetTPVForecast`

### `TPVForecastRequest`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `onboarding_merchant_txn_df` | `List[Dict]` | **Yes** | — | Raw transaction records (see below) |
| `mcc` | `int` | **Yes** | — | Merchant category code (must be in `SUPPORTED_MCCS`, currently `[5411]`) |
| `merchant_id` | `string` | No | `null` | Opaque merchant identifier for traceability |
| `horizon_months` | `int` | No | `3` | Months to forecast (1–3) |
| `confidence_interval` | `float` | No | `0.90` | Desired conformal coverage probability (0–1) |
| `card_types` | `List[string]` | No | `["both"]` | Card filters for the reference pool, e.g. `["visa"]`, `["debit"]`, `["both"]` |

### Raw Transaction Record (each element in `onboarding_merchant_txn_df`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `transaction_date` | `string` | **Yes** | ISO date string, e.g. `"2023-07-15"` |
| `amount` | `float` | **Yes** | Transaction dollar amount |
| `proc_cost` | `float` | No | Processing cost for this transaction |
| `cost_type_ID` | `int` | No | Cost type identifier (used for kNN peer fingerprinting) |
| `card_type` | `string` | No | `"debit"`, `"credit"`, etc. |

### Sample Request

```json
{
  "onboarding_merchant_txn_df": [
    {
      "transaction_date": "2023-07-08",
      "amount": 36.20,
      "proc_cost": 31.80,
      "cost_type_ID": 38,
      "card_type": "debit"
    },
    {
      "transaction_date": "2023-07-15",
      "amount": 42.50,
      "proc_cost": 37.10,
      "cost_type_ID": 12,
      "card_type": "credit"
    },
    {
      "transaction_date": "2023-08-03",
      "amount": 55.00,
      "proc_cost": 48.20,
      "cost_type_ID": 38,
      "card_type": "debit"
    },
    {
      "transaction_date": "2023-08-20",
      "amount": 29.75,
      "proc_cost": 26.00,
      "cost_type_ID": 5,
      "card_type": "debit"
    },
    {
      "transaction_date": "2023-09-10",
      "amount": 61.30,
      "proc_cost": 53.70,
      "cost_type_ID": 12,
      "card_type": "credit"
    },
    {
      "transaction_date": "2023-09-22",
      "amount": 38.90,
      "proc_cost": 34.00,
      "cost_type_ID": 38,
      "card_type": "debit"
    }
  ],
  "mcc": 5411,
  "merchant_id": "M-00451",
  "horizon_months": 3,
  "confidence_interval": 0.90,
  "card_types": ["both"]
}
```

---

## Output (Response)

### `TPVForecastResponse`

| Field | Type | Description |
|-------|------|-------------|
| `forecast` | `List[ForecastMonth]` | One entry per horizon month |
| `conformal_metadata` | `ConformalMetadata` | How the prediction interval was constructed |
| `process_metadata` | `ProcessMetadata` | Execution details and derived feature values |

### `ForecastMonth`

| Field | Type | Description |
|-------|------|-------------|
| `month_index` | `int` | 1-based index after the context window (1 = t+1) |
| `tpv_mid` | `float` | Point forecast in **dollars** (`expm1` of log-space prediction) |
| `tpv_ci_lower` | `float` | Lower bound of the dollar-space conformal interval |
| `tpv_ci_upper` | `float` | Upper bound of the dollar-space conformal interval |

### `ConformalMetadata`

| Field | Type | Description |
|-------|------|-------------|
| `half_width_dollars` | `float` | Dollar-space conformal half-width applied to all horizon months |
| `conformal_mode` | `string` | `"local"` (peer residuals), `"stratified"` (GBR risk-bucket), or `"global_fallback"` |
| `pool_size` | `int` | Number of calibration residuals in the pool used |
| `risk_score` | `float \| null` | GBR-predicted risk score (max across horizon); null if local mode |
| `strat_scheme` | `string \| null` | Stratification scheme name if stratified mode was used |

### `ProcessMetadata`

| Field | Type | Description |
|-------|------|-------------|
| `context_len_used` | `int` | Number of context months actually used (snapped to 1/3/6) |
| `context_mean_log_tpv` | `float` | Mean `log1p(TPV)` over the context window |
| `context_mean_dollar` | `float` | `expm1(context_mean_log_tpv)` — approximate dollar mean |
| `momentum` | `float` | Last context `log_tpv` minus context mean |
| `pool_mean_used` | `float` | kNN pool mean (log_tpv) used as a model feature |
| `mcc` | `int` | Merchant category code |
| `model_variant` | `string` | Pipeline version identifier (e.g. `"tpv_v1"`) |
| `horizon_months` | `int` | Number of months forecasted |
| `confidence_interval` | `float` | Coverage probability used |
| `generated_at_utc` | `datetime` | Timestamp of this inference call |
| `artifact_trained_at` | `string \| null` | ISO timestamp from `config_snapshot.json` |
| `strat_enabled` | `bool` | Whether risk-stratification passed the deployment guard |

### Sample Response

```json
{
  "forecast": [
    {
      "month_index": 1,
      "tpv_mid": 14253.47,
      "tpv_ci_lower": 13930.47,
      "tpv_ci_upper": 14576.47
    },
    {
      "month_index": 2,
      "tpv_mid": 14580.12,
      "tpv_ci_lower": 14257.12,
      "tpv_ci_upper": 14903.12
    },
    {
      "month_index": 3,
      "tpv_mid": 14890.35,
      "tpv_ci_lower": 14567.35,
      "tpv_ci_upper": 15213.35
    }
  ],
  "conformal_metadata": {
    "half_width_dollars": 323.0,
    "conformal_mode": "local",
    "pool_size": 10,
    "risk_score": null,
    "strat_scheme": null
  },
  "process_metadata": {
    "context_len_used": 3,
    "context_mean_log_tpv": 9.51,
    "context_mean_dollar": 13466.43,
    "momentum": 0.07,
    "pool_mean_used": 9.51,
    "mcc": 5411,
    "model_variant": "tpv_v1",
    "horizon_months": 3,
    "confidence_interval": 0.90,
    "generated_at_utc": "2025-01-15T08:30:00Z",
    "artifact_trained_at": "2025-01-10T12:00:00Z",
    "strat_enabled": false
  }
}
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| HuberRegressor over GBR | 3× faster training, equivalent dollar MAE, better generalisation |
| Dollar-weighted sample weights | High-TPV merchants dominate dollar error; weighting aligns loss landscape |
| No bias correction (α=0) | `expm1(pred)` targets the conditional median, which minimises MAE; Jensen correction (α=1) targets the conditional mean and inflates MAE |
| Dollar-space conformal | Intervals are directly in dollars — no back-transform distortion from Jensen's inequality |
| 11 features (v3 set) | Exogenous features (v7, 17 features) added noise; v3's 11 endogenous features are optimal |

## Quickstart

### Local (no Docker)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Train to generate artifacts
python train.py \
  --mcc 5411 \
  --data-path "../../Supervised learning/df_5411_merchants_mthly_v2.csv"

# 3. Set database connection (reference data for pool means + kNN peers)
#    Option A: SQLAlchemy connection string (any supported DB)
export DB_CONNECTION_STRING="sqlite:///path/to/transactions_and_cost_type.db"
#    Option B: Local SQLite file path (fallback)
export TRANSACTIONS_AND_COST_TYPE_DB_PATH="/path/to/transactions_and_cost_type.db"

# 4. Start the service
uvicorn app:app --reload --port 8093
```

Health check:

```bash
curl http://127.0.0.1:8093/health
```

Run tests:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

### Docker

```bash
python train.py \
  --mcc 5411 \
  --data-path "../../Supervised learning/df_5411_merchants_mthly_v2.csv"

# Set DB connection via environment variable in docker-compose.yml or -e flag
docker compose up --build
```

Service exposed on port **8093**.

---

## Database Configuration

v2 requires access to a reference database containing the `transactions` and
`cost_type_ref` tables (same schema as the KNN Quote Service).

| Env Var | Description |
|---------|-------------|
| `DB_CONNECTION_STRING` | Full SQLAlchemy URL (preferred), e.g. `sqlite:///data.db` or `postgresql://...` |
| `TRANSACTIONS_AND_COST_TYPE_DB_PATH` | Local SQLite file path (fallback if `DB_CONNECTION_STRING` is empty) |

The service uses this database to:
- Compute the **flat pool mean** (`log_tpv` mean across all reference merchants in the same MCC)
- Perform **kNN peer discovery** via cosine similarity on cost-type fingerprints
- Compute the **kNN pool mean** from the discovered peers

---

## Model Features (11)

| # | Feature | Description |
|---|---------|-------------|
| 1 | `context_mean` | Mean log1p(TPV) over context window |
| 2 | `context_std` | Std dev of log1p(TPV) over context |
| 3 | `momentum` | Last context log_tpv − mean |
| 4 | `pool_mean` | kNN peer pool mean (log_tpv) |
| 5 | `txn_amount_std` | Mean of monthly std_txn_amount |
| 6 | `log_txn_count` | log1p(mean transaction count) |
| 7 | `avg_median_txn_gap` | Mean |avg_txn_val − median_txn_amt| |
| 8 | `last_month` | Most recent context month's log_tpv |
| 9 | `log_avg_txn_val` | log1p(mean avg_transaction_value) |
| 10 | `momentum_tc` | Transaction count momentum |
| 11 | `momentum_atv` | Average transaction value momentum |

## Risk Features (11)

Used by GBR models for stratified conformal width estimation.

| # | Feature | Description |
|---|---------|-------------|
| 1 | `intra_txn_cov` | Transaction amount CoV |
| 2 | `avg_median_txn_gap` | Mean-median gap ratio |
| 3 | `log_txn_count` | Log transaction count |
| 4 | `cost_type_hhi` | Cost type concentration (HHI) |
| 5 | `log_avg_txn_val` | Log average transaction value |
| 6 | `txn_amount_cov` | Transaction amount variation |
| 7 | `pool_mean_gap_ratio` | Distance from flat pool mean |
| 8 | `ctx_to_knn_gap_ratio` | Distance from kNN pool mean |
| 9 | `ctx_cov` | Context window CoV |
| 10 | `tc_cov` | Transaction count CoV |
| 11 | `atv_cov` | Average transaction value CoV |

## Artifacts per (MCC, context_len)

| File | Contents |
|------|----------|
| `models.pkl` | `List[HuberRegressor]` — one per horizon step |
| `scaler.pkl` | `StandardScaler` fitted on training features |
| `cal_residuals.pkl` | `Dict[int, List[float]]` — merchant_id → dollar residuals |
| `global_q90.pkl` | `float` — dollar q90 of all calibration residuals |
| `risk_models.pkl` | `List[GradientBoostingRegressor]` — risk score models |
| `strat_knot_x.pkl` | Risk-score knots (if stratification enabled) |
| `strat_q_vals.pkl` | Dollar q90 per knot (if stratification enabled) |
| `config_snapshot.json` | Training metadata; mtime triggers hot-reload |

## Performance (MCC 5411, CV)

| Context | CV MAE ($) | Baseline ($) | Improvement | Coverage | Half-width |
|---------|-----------|-------------|-------------|----------|------------|
| ctx=1 | $113 | $119 | −5.0% | 0.895 | ±$356 |
| ctx=3 | $97 | $98 | −1.0% | 0.913 | ±$323 |
| ctx=6 | $93 | $94 | −1.1% | 0.907 | ±$312 |
