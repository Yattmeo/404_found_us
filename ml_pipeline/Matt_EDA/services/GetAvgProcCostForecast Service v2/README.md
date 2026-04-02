# GetM9MonthlyCostForecast Service

FastAPI service that forecasts a merchant's monthly `avg_proc_cost_pct` using the
**M9 pipeline** — a kNN pool-mean HuberRegressor with split-conformal prediction
intervals, sourced from notebook `m8_pipeline_c1.ipynb` Section 8 / Section 11.

The service is designed to:

1. Accept 3 months of observed monthly processing-cost history for an onboarding merchant.
2. Build a 4-feature vector `[context_mean, context_std, momentum, pool_mean]`.
3. Predict the next 3 months using 3 trained `HuberRegressor` models (one per horizon step).
4. Wrap each point prediction in a split-conformal prediction interval backed by a
   3-tier adaptive-quantile fallback chain.
5. Return all forecast months plus full diagnostic metadata.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness check + loaded artifact status |
| `POST` | `/GetM9MonthlyCostForecast` | Run the M9 monthly cost forecast |

---

## Quickstart

### Local (no Docker)

From `ml_pipeline/Matt_EDA/services/GetM9MonthlyCostForecast Service/`:

```bash
# 1. Create and activate a virtualenv (skip if using the project source/ venv)
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Train to generate artifacts (required before the service can start)
python train.py \
  --mcc 5411 \
  --data-path "../../Supervised learning/df_5411_merchants_samplemthly_26th_Mar.csv"

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
# Train first so artifacts/ exists for the volume mount
python train.py \
  --mcc 5411 \
  --data-path "../../Supervised learning/df_5411_merchants_samplemthly_26th_Mar.csv"

# Build and run
docker compose up --build
```

The service is exposed on **port 8092** and mounted at `./artifacts:/app/artifacts`.

---

## Startup Requirements

The service **hard-fails at startup** if no artifact bundle is found for any MCC
listed in `SUPPORTED_MCCS` (currently `[5411]`).  You must run `train.py` at least
once before starting the server.

### Artifact files expected per MCC

Under `artifacts/{mcc}/`:

| File | Contents |
|------|----------|
| `models.pkl` | `List[HuberRegressor]` — one model per horizon step (length 3) |
| `scaler.pkl` | `StandardScaler` fitted on the training feature matrix |
| `cal_residuals.pkl` | `Dict[int, List[float]]` — `merchant_id → [max-horizon residuals]` |
| `global_q90.pkl` | `float` — q90 of all calibration max-residuals |
| `bucket_q90.pkl` | `Dict[int, float]` — `{0: q90_low, 1: q90_high}` by volatility bucket |
| `config_snapshot.json` | Training metadata; **mtime change triggers hot-reload** |

### Hot-reload

A background daemon thread (`artifact-watcher`) polls `config_snapshot.json`
every 60 seconds.  When `train.py` finishes a monthly retrain it writes this file
last — atomically via `os.replace()` — so the watcher picks up the new artifacts
within one poll cycle **without a service restart**.

### Monthly retraining (PoC cron)

Add to `crontab -e` to retrain on the 1st of each month at 02:00:

```cron
0 2 1 * * cd /path/to/GetM9MonthlyCostForecast\ Service && \
  python train.py --mcc 5411 \
    --data-path /data/df_5411_merchants_samplemthly_26th_Mar.csv \
    >> /var/log/m9_train.log 2>&1
```

---

## Input Specification

Request model: `M9ForecastRequest` in [models.py](models.py).

### Required fields

| Field | Type | Description |
|-------|------|-------------|
| `context_months` | `List[ContextMonth]` | 1–3 observed monthly cost rows (see below). Sequences shorter than `CONTEXT_LEN=3` are accepted and zero-padded. |
| `pool_mean_at_context_end` | `float` | kNN peer pool mean at the context window end-date, as returned by the upstream KNN composite service. |
| `mcc` | `int` | Merchant category code — must be in `SUPPORTED_MCCS` (`[5411]`). |

### Optional fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `peer_merchant_ids` | `List[int]` | `null` | kNN neighbor IDs whose calibration residuals seed the local conformal quantile. Pass `[]` or omit to skip to vol-stratified / global fallback. |
| `merchant_id` | `str` | `null` | Opaque identifier carried through to `process_metadata` for traceability. |
| `horizon_months` | `int` | `3` | Forecast horizon length (max `HORIZON_LEN=3`). |
| `confidence_interval` | `float` | `0.90` | Conformal coverage probability (0 < x < 1). |
| `use_volatility_stratification` | `bool` | `true` | When the local peer pool is too small, fall back to a per-volatility-bucket q90 instead of the global q90. |

### `ContextMonth` row schema

| Field | Type | Description |
|-------|------|-------------|
| `year` | `int` | Calendar year (e.g. `2025`) |
| `month` | `int` | Month 1–12 |
| `avg_proc_cost_pct` | `float` | Average processing cost as a fraction of transaction value (e.g. `0.0285`) |

---

## Output Specification

Response model: `M9ForecastResponse` in [models.py](models.py).

### Top-level fields

| Field | Type | Description |
|-------|------|-------------|
| `forecast` | `List[ForecastMonth]` | One entry per forecast month (`length == horizon_months`). |
| `conformal_metadata` | `ConformalMetadata` | How the prediction interval was constructed. |
| `process_metadata` | `ProcessMetadata` | Derived features, timing, and model bookkeeping. |

### `ForecastMonth` fields

| Field | Type | Description |
|-------|------|-------------|
| `month_index` | `int` | 1-based index after the context window (1 = first forecast month). |
| `proc_cost_pct_mid` | `float` | Point forecast from the HuberRegressor. |
| `proc_cost_pct_ci_lower` | `float` | Lower bound: `mid − q90_used`. |
| `proc_cost_pct_ci_upper` | `float` | Upper bound: `mid + q90_used`. |

### `ConformalMetadata` fields

| Field | Type | Description |
|-------|------|-------------|
| `q90_used` | `float` | Symmetric half-width applied to every horizon month. |
| `pool_size` | `int` | Number of calibration residuals in the pool that produced `q90_used`. |
| `conformal_mode` | `str` | `"local"` · `"vol_stratified_local"` · `"global_fallback"` |
| `volatility_bucket` | `str \| null` | `"Low"` or `"High"` — populated when vol stratification was applied. |
| `merchant_cov` | `float \| null` | Coefficient of Variation of the merchant's context window. |

### `ProcessMetadata` fields

| Field | Type | Description |
|-------|------|-------------|
| `context_len` | `int` | Number of context months used (after any zero-padding). |
| `context_mean` | `float` | Mean of `avg_proc_cost_pct` over the context window. |
| `context_std` | `float` | Standard deviation of the context window. |
| `momentum` | `float` | `context_values[-1] − context_mean` (velocity signal). |
| `pool_mean_used` | `float` | The `pool_mean_at_context_end` value used as model feature 4. |
| `mcc` | `int` | MCC from the request. |
| `model_variant` | `str` | Always `"m9"`. |
| `horizon_months` | `int` | Requested horizon length. |
| `confidence_interval` | `float` | Coverage probability from the request. |
| `generated_at_utc` | `datetime` | UTC timestamp of this inference call. |
| `artifact_trained_at` | `str \| null` | ISO timestamp from `config_snapshot.json` — when models were last trained. |
| `context_was_padded` | `bool` | `true` when fewer than `CONTEXT_LEN` context months were supplied. |

---

## Process Flow

```
Request received
      │
      ▼
Validate MCC is loaded into artifact cache
      │
      ▼
Zero-pad context_months if len < CONTEXT_LEN=3
      │
      ▼
Build feature vector   ──────────────────────────────────────────────
  [context_mean, context_std, momentum, pool_mean]  shape (1, 4)     │
      │                                                               │
      ▼                                                     (features used
Scale with stored StandardScaler                          identically during
      │                                                     training)
      ▼
Predict 3 horizon steps with 3 HuberRegressor models
  h=1: model[0].predict(X_scaled)
  h=2: model[1].predict(X_scaled)
  h=3: model[2].predict(X_scaled)
      │
      ▼
Compute conformal half-width (3-tier chain)
  Tier 1 — LOCAL:          collect cal_residuals for each peer_merchant_id;
                           if total >= MIN_POOL=10, adaptive_q at requested CI
  Tier 2 — VOL-STRATIFIED: classify CoV(context) vs VOL_THRESHOLD=0.15 → Low/High;
                           use the per-bucket q90 from bucket_q90 artifact
  Tier 3 — GLOBAL:         use global_q90 from calibration set (always available)
      │
      ▼
Assemble ForecastMonth list
  ci_lower = mid − q90_used
  ci_upper = mid + q90_used
      │
      ▼
Return M9ForecastResponse
```

### Conformal interval construction

`M9` uses **split conformal prediction** over the max-over-horizon absolute error:

```
cal_max_res[i] = max_h |y_cal[i, h] − ŷ[i, h]|   for h = 1, 2, 3
```

The adaptive finite-sample quantile (Vovk et al.) is used:

```
level = ceil((n + 1) × target) / n
q = quantile(cal_max_res, level)     # returns None if level > 1.0
```

This guarantees marginal coverage ≥ `confidence_interval` for the worst
horizon step, applied symmetrically to all steps.

---

## Defaults and Config

Defined in [config.py](config.py):

| Constant | Value | Description |
|----------|-------|-------------|
| `CONTEXT_LEN` | `3` | Months of observed history used as model input |
| `HORIZON_LEN` | `3` | Months to forecast (t+1 … t+3) |
| `TARGET_COV` | `0.90` | Default conformal coverage probability |
| `MIN_POOL` | `10` | Minimum residuals required to use local conformal q90 |
| `KNN_K` | `10` | k used for pool mean computation during training |
| `VOL_THRESHOLD` | `0.15` | CoV threshold separating Low / High volatility buckets |
| `DEFAULT_WINDOW_YEARS` | `3` | Rolling training window for `train.py` |
| `ARTIFACT_POLL_INTERVAL_S` | `60` | Seconds between hot-reload checks |

To override the artifacts path at runtime:

```bash
ARTIFACTS_BASE_PATH=/custom/path uvicorn app:app --port 8092
```

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

### Training steps

1. **Load & window** — filter to the most recent `window_years` of data.
2. **Scenario generation** — slide `(CONTEXT_LEN=3, HORIZON_LEN=3)` windows over
   each merchant's sorted monthly history; enforce no calendar gaps.
3. **Merchant-level split** — 60/20/20 stratified by merchant (seed=42, matching notebook Cell 14).
4. **kNN pool mean cache** — for each unique `(merchant_id, year, month)` key,
   fit a `NearestNeighbors(metric='cosine')` on cost-type fingerprints of all
   peers available up to that date; take the mean cost of the `k=10` nearest neighbors.
5. **Temporal train/cal split** — calibration year = latest year in the validate split.
6. **Fit** — `StandardScaler` + 3 × `HuberRegressor(epsilon=1.35, max_iter=500)` with
   `sample_weight = 1 / (pool_mean + 1)`.
7. **Residuals** — `cal_max_res[i] = max_h |y_cal[i,h] − ŷ[i,h]|`.
8. **q90s** — global q90 + per-volatility-bucket q90 (Low CoV < 0.15; High CoV ≥ 0.15).
9. **Atomic write** — all `.pkl` files then `config_snapshot.json` last (triggers hot-reload).

---

## Integration Contract with KNN Service

Expected upstream call sequence:

1. KNN service → `/getCompositeMerchant` (returns `pool_mean` + `peer_merchant_ids`)
2. Pass values directly into `POST /GetM9MonthlyCostForecast`

`pool_mean_at_context_end` should reflect the kNN peer mean at the **end-date of the
context window**, consistent with how features were built during training.

---

## Example Request

```json
{
  "merchant_id": "merchant_abc",
  "mcc": 5411,
  "context_months": [
    { "year": 2025, "month": 1, "avg_proc_cost_pct": 0.0268 },
    { "year": 2025, "month": 2, "avg_proc_cost_pct": 0.0291 },
    { "year": 2025, "month": 3, "avg_proc_cost_pct": 0.0274 }
  ],
  "pool_mean_at_context_end": 0.0282,
  "peer_merchant_ids": [1042, 2817, 3950, 1120, 4771, 3301, 877, 2245, 509, 1688],
  "horizon_months": 3,
  "confidence_interval": 0.90,
  "use_volatility_stratification": true
}
```

**Short context (zero-padded automatically):**

```json
{
  "merchant_id": "merchant_new",
  "mcc": 5411,
  "context_months": [
    { "year": 2025, "month": 3, "avg_proc_cost_pct": 0.0274 }
  ],
  "pool_mean_at_context_end": 0.0282,
  "peer_merchant_ids": []
}
```

---

## Example Response

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
    "q90_used": 0.0145,
    "pool_size": 183,
    "conformal_mode": "local",
    "volatility_bucket": null,
    "merchant_cov": null
  },
  "process_metadata": {
    "context_len": 3,
    "context_mean": 0.0278,
    "context_std": 0.00095,
    "momentum": -0.00040,
    "pool_mean_used": 0.0282,
    "mcc": 5411,
    "model_variant": "m9",
    "horizon_months": 3,
    "confidence_interval": 0.90,
    "generated_at_utc": "2026-03-28T02:14:05.881243Z",
    "artifact_trained_at": "2026-03-01T02:00:11.204512+00:00",
    "context_was_padded": false
  }
}
```

**Fallback to global q90 (unknown peers, vol-strat disabled):**

```json
{
  "forecast": [
    {
      "month_index": 1,
      "proc_cost_pct_mid": 0.0279,
      "proc_cost_pct_ci_lower": 0.0015,
      "proc_cost_pct_ci_upper": 0.0543
    }
  ],
  "conformal_metadata": {
    "q90_used": 0.0264,
    "pool_size": 0,
    "conformal_mode": "global_fallback",
    "volatility_bucket": "Low",
    "merchant_cov": 0.034
  },
  "process_metadata": {
    "context_len": 3,
    "context_mean": 0.0278,
    "context_std": 0.00095,
    "momentum": -0.00040,
    "pool_mean_used": 0.0282,
    "mcc": 5411,
    "model_variant": "m9",
    "horizon_months": 1,
    "confidence_interval": 0.90,
    "generated_at_utc": "2026-03-28T02:14:06.001123Z",
    "artifact_trained_at": "2026-03-01T02:00:11.204512+00:00",
    "context_was_padded": false
  }
}
```

---

## Conformal Mode Interpretation

| `conformal_mode` | Meaning | Typical interval width |
|------------------|---------|----------------------|
| `local` | Peer pool had ≥ 10 calibration residuals; tightest and most personalised interval | Narrowest |
| `vol_stratified_local` | Peer pool too small; used the q90 for this merchant's volatility bucket (Low / High CoV) | Moderate |
| `global_fallback` | `use_volatility_stratification=false` or vol-strat also insufficient; entire calibration set q90 | Widest / most conservative |

---

## Error Responses

| HTTP status | Trigger | `detail` example |
|-------------|---------|-----------------|
| `422` | MCC not in `SUPPORTED_MCCS` | `"MCC 9999 is not supported. Supported MCCs: [5411]."` |
| `422` | Pydantic validation error | `"context_months: field required"` |
| `503` | Artifacts not loaded (train.py not yet run) | `"No artifact bundle loaded for MCC 5411."` |

---

## Operational Notes

- The same `q90_used` is applied symmetrically to **all horizon steps**.
  This gives marginal coverage ≥ `confidence_interval` for the hardest step;
  shorter-horizon steps will be over-covered (conservative but correct).
- `context_was_padded: true` indicates the merchant has fewer than 3 months of
  history. The zero-padding biases `context_mean` and `context_std` downward;
  treat confidence intervals for new merchants as more conservative.
- `momentum` can be negative, indicating the merchant's cost trended below its
  own average at the end of the context window.
- Hot-reload introduces at most `ARTIFACT_POLL_INTERVAL_S=60` seconds of lag
  after a retrain. Requests served during a reload window use the previous bundle.
