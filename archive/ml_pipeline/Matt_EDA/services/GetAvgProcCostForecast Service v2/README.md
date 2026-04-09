# GetAvgProcCostForecast Service v2

FastAPI service that forecasts a merchant's monthly **average processing cost
percentage** (`avg_proc_cost_pct`) using the **M9 v2 pipeline** — a kNN pool-mean
HuberRegressor with GBR risk-stratified split-conformal prediction intervals.

**v2 change:** The caller now sends only raw transaction records and basic
forecast parameters.  All feature engineering, monthly aggregation, pool-mean
computation, and kNN peer discovery are handled inside the service using a
shared reference database.

---

## How It Works

### Training (offline — `train.py`)

1. **Load & transform** — Read the merchant monthly CSV; target is `avg_proc_cost_pct = mean(proc_cost / amount)`.
2. **Generate scenarios** — Slide context windows of length 1, 3, and 6 months over each merchant's history; each window becomes one training row with a 7-feature vector and 3 horizon targets.
3. **Merchant-level split** — Split merchants (not rows) into train / calibration / test.
4. **kNN pool caches** — For every context window, compute the flat peer pool mean and a cosine-similarity kNN pool mean in `avg_proc_cost_pct` space.
5. **Fit 3 HuberRegressors** — One model per horizon step, trained with inverse-pool-mean sample weights.
6. **Calibration residuals** — On the calibration fold, compute `|actual − pred|` per merchant; store keyed by `merchant_id`.
7. **Cross-fit GBR risk models** — Train gradient-boosted regressors on 9 risk features to predict each merchant's absolute residual.
8. **Select stratification scheme** — Evaluate candidate bucket boundaries against a deployment guard; pick the best scheme or disable stratification.
9. **Write artifacts** — Persist models, scaler, calibration residuals, global quantile, risk models, stratification knots, and `config_snapshot.json` to `artifacts/<mcc>/<context_len>/`.

### Inference (online — `POST /GetM9MonthlyCostForecast`)

1. **Receive request** — Accept raw transaction records (`onboarding_merchant_txn_df`) plus `mcc` and optional forecast parameters.
2. **Aggregate** — Group raw transactions by year-month; compute `avg_proc_cost_pct = mean(proc_cost / amount)`, std, median, txn count, avg txn value, and cost-type percentages per month.
3. **Select context window** — Pick the last *N* months where *N* is the largest supported context length (6, 3, or 1) ≤ available months.
4. **Resolve model bundle** — Load the pre-trained artifact bundle for the given MCC and context length.
5. **Compute pool info from DB** — Query the reference database to calculate the flat pool mean, kNN pool mean (cosine on cost-type fingerprints), and peer merchant IDs.
6. **Build feature vector** — Compute the 7 features used in training.
7. **Scale & predict** — StandardScaler → 3 HuberRegressor models → 3 point predictions.
8. **Conformal interval** — A 3-tier adaptive-quantile fallback chain determines the half-width:
   - **Local** — If ≥ 10 calibration residuals exist for the merchant's kNN peers, use the adaptive quantile.
   - **Stratified** — Otherwise, use the GBR risk model to score the merchant, and interpolate a per-bucket quantile.
   - **Global fallback** — If stratification is disabled, fall back to the global 90th-percentile residual.
9. **Return** — Point forecasts ± conformal intervals, plus metadata.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness check + loaded artifact status |
| `POST` | `/GetM9MonthlyCostForecast` | Run the M9 monthly cost forecast |

---

## Quickstart

### Local (no Docker)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Train to generate artifacts (required before the service can start)
python train.py \
  --mcc 5411 \
  --data-path "../../Supervised learning/df_5411_merchants_samplemthly_26th_Mar.csv"

# 3. Set database connection (reference data for pool means + kNN peers)
#    Option A: SQLAlchemy connection string (any supported DB)
export DB_CONNECTION_STRING="sqlite:///path/to/transactions_and_cost_type.db"
#    Option B: Local SQLite file path (fallback)
export TRANSACTIONS_AND_COST_TYPE_DB_PATH="/path/to/transactions_and_cost_type.db"

# 4. Start the service
uvicorn app:app --reload --port 8092
```

Health check:

```bash
curl http://127.0.0.1:8092/health
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
  --data-path "../../Supervised learning/df_5411_merchants_samplemthly_26th_Mar.csv"

# Set DB connection via environment variable in docker-compose.yml or -e flag
docker compose up --build
```

The service is exposed on **port 8092** and mounted at `./artifacts:/app/artifacts`.

---

## Database Configuration

v2 requires access to a reference database containing the `transactions` and
`cost_type_ref` tables (same schema as the KNN Quote Service).

| Env Var | Description |
|---------|-------------|
| `DB_CONNECTION_STRING` | Full SQLAlchemy URL (preferred), e.g. `sqlite:///data.db` or `postgresql://...` |
| `TRANSACTIONS_AND_COST_TYPE_DB_PATH` | Local SQLite file path (fallback if `DB_CONNECTION_STRING` is empty) |

The service uses this database to:
- Compute the **flat pool mean** (`avg_proc_cost_pct` across all reference merchants in the same MCC)
- Perform **kNN peer discovery** via cosine similarity on cost-type fingerprints
- Compute the **kNN pool mean** from the discovered peers

---

## Startup Requirements

The service logs a warning at startup if no artifact bundle is found for a given
MCC/context_len combination. You must run `train.py` at least once before serving
forecasts.

### Artifact files expected per (MCC, context_len)

Under `artifacts/{mcc}/{context_len}/`:

| File | Contents |
|------|----------|
| `models.pkl` | `List[HuberRegressor]` — one model per horizon step (length 3) |
| `scaler.pkl` | `StandardScaler` fitted on the training feature matrix |
| `cal_residuals.pkl` | `Dict[int, List[float]]` — `merchant_id → [absolute residuals]` |
| `global_q90.pkl` | `float` — q90 of all calibration residuals |
| `risk_models.pkl` | `List[GradientBoostingRegressor]` — risk score models |
| `strat_knot_x.pkl` | Risk-score knots (if stratification enabled) |
| `strat_q_vals.pkl` | q90 per knot (if stratification enabled) |
| `config_snapshot.json` | Training metadata; **mtime change triggers hot-reload** |

### Hot-reload

A background daemon thread (`artifact-watcher`) polls `config_snapshot.json`
every 60 seconds.  When `train.py` finishes a retrain it writes this file
last — the watcher picks up the new artifacts within one poll cycle
**without a service restart**.

---

## Input (Request)

`POST /GetM9MonthlyCostForecast`

### `M9ForecastRequest`

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
| `proc_cost` | `float` | **Yes** | Processing cost for this transaction |
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

### `M9ForecastResponse`

| Field | Type | Description |
|-------|------|-------------|
| `forecast` | `List[ForecastMonth]` | One entry per horizon month |
| `conformal_metadata` | `ConformalMetadata` | How the prediction interval was constructed |
| `process_metadata` | `ProcessMetadata` | Execution details and derived feature values |

### `ForecastMonth`

| Field | Type | Description |
|-------|------|-------------|
| `month_index` | `int` | 1-based index after the context window (1 = t+1) |
| `proc_cost_pct_mid` | `float` | Point forecast for `avg_proc_cost_pct` |
| `proc_cost_pct_ci_lower` | `float` | Lower bound of the conformal interval |
| `proc_cost_pct_ci_upper` | `float` | Upper bound of the conformal interval |

### `ConformalMetadata`

| Field | Type | Description |
|-------|------|-------------|
| `half_width` | `float` | Conformal half-width applied symmetrically to all horizon months |
| `conformal_mode` | `string` | `"local"` (peer residuals), `"stratified"` (GBR risk-bucket), or `"global_fallback"` |
| `pool_size` | `int` | Number of calibration residuals in the pool used |
| `risk_score` | `float \| null` | GBR-predicted risk score (max across horizon); null if local mode |
| `strat_scheme` | `string \| null` | Stratification scheme name if stratified mode was used |

### `ProcessMetadata`

| Field | Type | Description |
|-------|------|-------------|
| `context_len_used` | `int` | Number of context months actually used (snapped to 1/3/6) |
| `context_mean` | `float` | Mean `avg_proc_cost_pct` over the context window |
| `context_std` | `float` | Std dev of `avg_proc_cost_pct` over the context window |
| `momentum` | `float` | Last context value minus context mean |
| `pool_mean_used` | `float` | kNN pool mean used as a model feature |
| `mcc` | `int` | Merchant category code |
| `model_variant` | `string` | Always `"m9_v2"` |
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
      "proc_cost_pct_mid": 0.0279,
      "proc_cost_pct_ci_lower": 0.0134,
      "proc_cost_pct_ci_upper": 0.0424
    },
    {
      "month_index": 2,
      "proc_cost_pct_mid": 0.0281,
      "proc_cost_pct_ci_lower": 0.0136,
      "proc_cost_pct_ci_upper": 0.0426
    },
    {
      "month_index": 3,
      "proc_cost_pct_mid": 0.0276,
      "proc_cost_pct_ci_lower": 0.0131,
      "proc_cost_pct_ci_upper": 0.0421
    }
  ],
  "conformal_metadata": {
    "half_width": 0.0145,
    "conformal_mode": "local",
    "pool_size": 183,
    "risk_score": null,
    "strat_scheme": null
  },
  "process_metadata": {
    "context_len_used": 3,
    "context_mean": 0.0278,
    "context_std": 0.00095,
    "momentum": -0.00040,
    "pool_mean_used": 0.0282,
    "mcc": 5411,
    "model_variant": "m9_v2",
    "horizon_months": 3,
    "confidence_interval": 0.90,
    "generated_at_utc": "2026-03-28T02:14:05.881243Z",
    "artifact_trained_at": "2026-03-01T02:00:11.204512+00:00",
    "strat_enabled": true
  }
}
```

---

## Conformal Mode Interpretation

| `conformal_mode` | Meaning | Typical interval width |
|------------------|---------|----------------------|
| `local` | Peer pool had ≥ 10 calibration residuals; tightest and most personalised interval | Narrowest |
| `stratified` | Peer pool too small; used GBR risk-score interpolation across trained knots | Moderate |
| `global_fallback` | Stratification disabled or insufficient; entire calibration set q90 | Widest / most conservative |

---

## Model Features (7)

| # | Feature | Description |
|---|---------|-------------|
| 1 | `context_mean` | Mean `avg_proc_cost_pct` over context window |
| 2 | `context_std` | Std dev of `avg_proc_cost_pct` over context |
| 3 | `momentum` | Last context value − mean |
| 4 | `pool_mean` | kNN peer pool mean (`avg_proc_cost_pct`) |
| 5 | `intra_std` | Mean of monthly `std_proc_cost_pct` |
| 6 | `log_txn_count` | `log1p(mean transaction count)` |
| 7 | `mean_median_gap` | Mean `|avg − median|` of `proc_cost_pct` |

## Risk Features (9)

Used by GBR models for stratified conformal width estimation.

| # | Feature | Description |
|---|---------|-------------|
| 1 | `intra_cov` | Intra-month proc-cost CoV |
| 2 | `mean_median_gap` | Mean-median gap ratio |
| 3 | `log_txn_count` | Log transaction count |
| 4 | `cost_type_hhi` | Cost type concentration (HHI) |
| 5 | `log_avg_txn_val` | Log average transaction value |
| 6 | `txn_amount_cov` | Transaction amount variation |
| 7 | `pool_mean_gap_ratio` | Distance from flat pool mean |
| 8 | `ctx_to_knn_gap_ratio` | Distance from kNN pool mean |
| 9 | `ctx_cov` | Context window CoV |

## Artifacts per (MCC, context_len)

| File | Contents |
|------|----------|
| `models.pkl` | `List[HuberRegressor]` — one per horizon step |
| `scaler.pkl` | `StandardScaler` fitted on training features |
| `cal_residuals.pkl` | `Dict[int, List[float]]` — merchant_id → absolute residuals |
| `global_q90.pkl` | `float` — q90 of all calibration residuals |
| `risk_models.pkl` | `List[GradientBoostingRegressor]` — risk score models |
| `strat_knot_x.pkl` | Risk-score knots (if stratification enabled) |
| `strat_q_vals.pkl` | q90 per knot (if stratification enabled) |
| `config_snapshot.json` | Training metadata; mtime triggers hot-reload |

---

## Error Responses

| HTTP status | Trigger | `detail` example |
|-------------|---------|-----------------|
| `422` | MCC not in `SUPPORTED_MCCS` | `"MCC 9999 is not supported. Supported MCCs: [5411]."` |
| `422` | Pydantic validation error | `"onboarding_merchant_txn_df: field required"` |
| `503` | Artifacts / DB not configured | `"No artifact bundle loaded for MCC 5411."` |

---

## Operational Notes

- The same `half_width` is applied symmetrically to **all horizon steps**.
  This gives marginal coverage ≥ `confidence_interval` for the hardest step;
  shorter-horizon steps will be over-covered (conservative but correct).
- `momentum` can be negative, indicating the merchant's cost trended below its
  own average at the end of the context window.
- Hot-reload introduces at most `ARTIFACT_POLL_INTERVAL_S=60` seconds of lag
  after a retrain. Requests served during a reload window use the previous bundle.

---

## Training Script

`train.py` produces all required artifacts from a raw monthly CSV.

```bash
python train.py \
  --mcc 5411 \
  --data-path /path/to/monthly_data.csv \
  [--window-years 3]
```

### Required CSV columns

| Column | Description |
|--------|-------------|
| `merchant_id` | Unique merchant identifier |
| `year` | Calendar year (int) |
| `month` | Month 1–12 (int) |
| `avg_proc_cost_pct` | Average processing cost as a fraction of transaction value |
| `cost_type_1_pct` … `cost_type_61_pct` | Cost-type fingerprint columns used for kNN pool mean (optional but recommended) |

If cost-type columns are absent, `train.py` falls back to a flat pool mean
(mean of all peer merchants at each snapshot date).
