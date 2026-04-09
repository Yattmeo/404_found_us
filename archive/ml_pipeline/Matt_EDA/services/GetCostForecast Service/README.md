# GetCostForecast Service

FastAPI service that forecasts onboarding merchant weekly `proc_cost_pct` using
composite weekly features from KNN Quote Service `/getCompositeMerchant`.

The service is designed to:

1. Generate SARIMA/SARIMAX paths in weekly space.
2. Align model-generated onboarding-window values to onboarding actuals.
3. Apply guarded calibration when it improves context-window fit.
4. Return post-onboarding weekly forecasts with confidence intervals.

## Endpoints

- `GET /health`
- `POST /GetCostForecast`

## Quickstart

From [ml_pipeline/Matt_EDA/services/GetCostForecast Service](.):

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8091
```

Health check:

```bash
curl http://127.0.0.1:8091/health
```

Run tests:

```bash
python -m pytest -q
```

Docker run:

```bash
docker compose up --build
```

## Input Specification

Request model: `CostForecastRequest` in [models.py](models.py).

Required:

- `composite_weekly_features`: array of weekly rows from KNN

Optional but strongly recommended:

- `onboarding_merchant_txn_df`: raw onboarding transactions for calibration
- `composite_merchant_id`
- `mcc`

Tunable controls:

- `forecast_horizon_wks` (default 12)
- `confidence_interval` (default 0.95)
- `use_optimised_sarima` (default `false`)
- `use_exogenous_sarimax` (default `false`)
- `use_guarded_calibration` (default `true`)

### composite_weekly_features row schema

Each row must include:

- `calendar_year`, `week_of_year`
- `weekly_txn_count_mean`, `weekly_txn_count_stdev`
- `weekly_total_proc_value_mean`, `weekly_total_proc_value_stdev`
- `weekly_avg_txn_value_mean`, `weekly_avg_txn_value_stdev`
- `weekly_avg_txn_cost_pct_mean`, `weekly_avg_txn_cost_pct_stdev`
- `neighbor_coverage`
- `pct_ct_means` (map)

### onboarding_merchant_txn_df row expectations

Per row:

- date under `transaction_date` or `date`
- `amount`
- `proc_cost`

Rows missing required fields are skipped during onboarding aggregation.

## Output Specification

Response model: `CostForecastResponse` in [models.py](models.py).

Top-level fields:

- `forecast[]`: post-onboarding forecast weeks
- `process_metadata`
- `sarima_metadata`
- `is_guarded_sarima`
- `context_sarima_fitted[]`: model-generated onboarding-window values aligned to onboarding weeks

### forecast item (`ForecastWeek`)

- `forecast_week_index`
- `proc_cost_pct_mid`
- `proc_cost_pct_ci_lower`
- `proc_cost_pct_ci_upper`

### process metadata highlights

- `context_window_weeks_count`
- `matched_calibration_points`
- `calibration_mode`
- `calibration_successful`
- `calibration_mae`, `calibration_rmse`, `calibration_r2`
- `context_window_mean_proc_cost_pct`
- `is_fallback`, `fallback_reason`

### SARIMA metadata highlights

- `seasonal_length`
- `selected_order`, `selected_seasonal_order`
- `use_optimised_sarima`
- `use_exogenous_sarimax`
- `exogenous_feature_names`
- `aic`
- optimisation timing/candidate counts

## Process Explanation

Current forecasting flow is rolling-origin relative to onboarding start:

1. Sort composite weekly history by `(calendar_year, week_of_year)`.
2. Aggregate onboarding transactions to weekly actual `proc_cost_pct`.
3. Find onboarding week positions in composite history.
4. Train SARIMA/SARIMAX up to the week before onboarding starts.
5. Generate a continuous path for:
    - onboarding window length, plus
    - requested forecast horizon.
6. Use generated onboarding-window values vs onboarding actuals for calibration.
7. Return only the post-onboarding horizon segment as final forecast.

This avoids timeline mismatch between context and forecast paths.

## Defaults and Config

Defined in [config.py](config.py):

- `SARIMA_SEASONAL_PERIOD = 13`
- fixed differencing: `d=1`, `D=1`
- default non-optimised order: `(1,1,1)(1,1,1,13)`
- optimisation timeout and candidate grids
- fallback minimum history weeks
- calibration guardrails

## Calibration Guardrails

Calibration applies only if all checks pass:

- minimum matched points
- sufficient SARIMA variability in context
- least-squares solve success
- calibration improves context RMSE over raw

If not, service keeps raw SARIMA/SARIMAX output and sets
`process_metadata.calibration_mode` (for example `skipped_no_improvement`).

Intercept clamp is scale-aware:

- absolute floor: `CALIBRATION_MAX_ABS_INTERCEPT`
- relative cap: `CALIBRATION_MAX_ABS_INTERCEPT_RELATIVE_TO_CONTEXT_MEAN * |context_mean|`
- effective cap is the max of the two.

## Example Request

```json
{
   "composite_weekly_features": [
      {
         "calendar_year": 2016,
         "week_of_year": 1,
         "weekly_txn_count_mean": 120.0,
         "weekly_txn_count_stdev": 14.0,
         "weekly_total_proc_value_mean": 5400.0,
         "weekly_total_proc_value_stdev": 610.0,
         "weekly_avg_txn_value_mean": 45.0,
         "weekly_avg_txn_value_stdev": 4.5,
         "weekly_avg_txn_cost_pct_mean": 0.82,
         "weekly_avg_txn_cost_pct_stdev": 0.12,
         "neighbor_coverage": 5,
         "pct_ct_means": {"pct_ct_2": 0.41, "pct_ct_38": 0.37}
      }
   ],
   "onboarding_merchant_txn_df": [
      {
         "transaction_date": "2016-01-08",
         "amount": 36.2,
         "proc_cost": 31.8,
         "cost_type_ID": 38,
         "card_type": "debit"
      }
   ],
   "composite_merchant_id": "composite_mcc_5411_...",
   "mcc": 5411,
   "forecast_horizon_wks": 12,
   "confidence_interval": 0.95,
   "use_optimised_sarima": false,
   "use_exogenous_sarimax": true,
   "use_guarded_calibration": true
}
```

## Example Response

```json
{
   "process_metadata": {
      "context_window_weeks_count": 8,
      "matched_calibration_points": 8,
      "calibration_mode": "guarded_linear",
      "is_fallback": false,
      "fallback_reason": null,
      "fallback_mean_proc_cost_pct": null,
      "context_window_mean_proc_cost_pct": 0.9134,
      "generated_at_utc": "2026-03-16T10:20:11.123456Z",
      "forecast_horizon_wks": 12,
      "confidence_interval": 0.95,
      "used_guarded_calibration": true,
      "calibration_successful": true,
      "calibration_mae": 0.0412,
      "calibration_rmse": 0.0528,
      "calibration_r2": 0.71
   },
   "sarima_metadata": {
      "seasonal_length": 13,
      "use_optimised_sarima": false,
      "use_exogenous_sarimax": true,
      "exogenous_feature_names": [
         "weekly_txn_count_mean",
         "weekly_total_proc_value_mean",
         "weekly_avg_txn_value_mean",
         "weekly_txn_count_stdev",
         "weekly_total_proc_value_stdev",
         "weekly_avg_txn_value_stdev",
         "weekly_avg_txn_cost_pct_stdev",
         "neighbor_coverage"
      ],
      "selected_order": [1, 1, 1],
      "selected_seasonal_order": [1, 1, 1, 13],
      "aic": 147.82,
      "fit_status": "ok",
      "optimisation_attempted": false,
      "optimisation_time_ms": null,
      "optimisation_candidates_evaluated": 0
   },
   "is_guarded_sarima": true,
   "forecast": [
      {
         "forecast_week_index": 10,
         "proc_cost_pct_mid": 0.8842,
         "proc_cost_pct_ci_lower": 0.7411,
         "proc_cost_pct_ci_upper": 1.0240
      },
      {
         "forecast_week_index": 11,
         "proc_cost_pct_mid": 0.8729,
         "proc_cost_pct_ci_lower": 0.7295,
         "proc_cost_pct_ci_upper": 1.0173
      }
   ],
   "context_sarima_fitted": [
      0.8412,
      0.8639,
      0.9011,
      0.8894,
      0.9170,
      0.9288,
      0.9055,
      0.8962
   ]
}
```

Notes:

- `forecast_week_index` starts immediately after the onboarding context window.
- `context_sarima_fitted` length should typically match `context_window_weeks_count`.
- Calibration may be skipped (`calibration_mode != guarded_linear`) if guardrails fail.

## Integration Contract With KNN Service

Expected upstream call sequence:

1. KNN `/getCompositeMerchant`
2. pass `weekly_features` into GetCostForecast `/GetCostForecast`

The `composite_weekly_features` schema must match KNN output exactly.

## Operational Notes

- For very short composite history, service may return fallback flat forecasts.
- `use_exogenous_sarimax=true` enables exogenous columns from config.
- Future exogenous values currently use last-value carry-forward.
- If onboarding rows are sparse or unaligned to composite keys, calibration can
   be skipped automatically.
