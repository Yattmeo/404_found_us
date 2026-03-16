# Service Evaluation Guide

This directory contains two evaluation scripts for end-to-end testing of:

- KNN Quote Service (`/getQuote`, `/getCompositeMerchant`)
- GetCostForecast Service (`/GetCostForecast`)
- GetVolumeForecast Service (`/GetVolumeForecast`)

Both scripts start both APIs locally, execute chained requests, and write
metrics artifacts under [service_eval_outputs](service_eval_outputs) with
separate `unified/`, `multi/`, and `multi_volume/` latest/archive folders.

## Scripts

## 1) Single-merchant visual evaluation

Script: [services/integration_tests/unified_service_visual_test.py](services/integration_tests/unified_service_visual_test.py)

Purpose:

- run one end-to-end scenario
- generate comparison plots
- inspect context window vs forecast horizon behavior

Current behavior:

- uses real data from `services/KNN Quote Service Production/processed_transactions_4mcc.csv`
- builds an ephemeral SQLite reference DB in `service_eval_outputs/unified/latest/unified_eval.sqlite`
- evaluates one target merchant for `EVAL_YEAR`

Outputs:

- `service_eval_outputs/unified/latest/knn_quote_prediction_vs_actual.png`
- `service_eval_outputs/unified/latest/get_cost_forecast_prediction_vs_actual.png`
- `service_eval_outputs/unified/latest/unified_eval_metrics.json`

Run:

```bash
cd /Users/yattmeo/Desktop/SMU/Code/404_found_us
.venv/bin/python ml_pipeline/Matt_EDA/unified_service_visual_test.py

# new location
.venv/bin/python ml_pipeline/Matt_EDA/services/integration_tests/unified_service_visual_test.py
```

## 2) Multi-merchant aggregate evaluation

Script: [services/integration_tests/multi_merchant_service_eval.py](services/integration_tests/multi_merchant_service_eval.py)

Purpose:

- test generalisability across multiple target merchants
- report per-merchant and aggregate metrics

Current behavior:

- real data source: `services/KNN Quote Service Production/processed_transactions_4mcc.csv`
- reference pool: random sample of size `N_REFERENCE_MERCHANTS`
- target pool: random sample of size `N_TARGET_MERCHANTS` from eligible merchants
- missing weekly actuals in forecast alignment are filled with epsilon (`1e-9`)
  instead of skipping the merchant

Output:

- `service_eval_outputs/multi/latest/multi_merchant_eval_metrics.json`
- `service_eval_outputs/multi/latest/multi_merchant_forecast_panels.png`

Run:

```bash
cd /Users/yattmeo/Desktop/SMU/Code/404_found_us
.venv/bin/python ml_pipeline/Matt_EDA/multi_merchant_service_eval.py

# new location
.venv/bin/python ml_pipeline/Matt_EDA/services/integration_tests/multi_merchant_service_eval.py
```

## 3) Multi-merchant volume evaluation

Script: [services/integration_tests/multi_merchant_volume_service_eval.py](services/integration_tests/multi_merchant_volume_service_eval.py)

Purpose:

- test generalisability of GetVolumeForecast across multiple target merchants
- report per-merchant and aggregate weekly amount forecast metrics

Current behavior:

- real data source: `services/KNN Quote Service Production/processed_transactions_4mcc.csv`
- reference pool: random sample of size `N_REFERENCE_MERCHANTS`
- target pool: random sample of size `N_TARGET_MERCHANTS` from eligible merchants
- missing weekly actuals in forecast alignment are filled with epsilon (`1e-9`)
  instead of skipping the merchant

Output:

- `service_eval_outputs/multi_volume/latest/multi_merchant_volume_eval_metrics.json`
- `service_eval_outputs/multi_volume/latest/multi_merchant_volume_forecast_panels.png`

Run:

```bash
cd /Users/yattmeo/Desktop/SMU/Code/404_found_us
.venv/bin/python ml_pipeline/Matt_EDA/services/integration_tests/multi_merchant_volume_service_eval.py
```

## Metrics Files

### unified_eval_metrics.json

Contains one-scenario metrics for:

- KNN quote MAE / RMSE
- GetCostForecast MAE / RMSE
- calibrated and raw SARIMA paths
- calibration metadata

### multi_merchant_eval_metrics.json

Contains:

- `summary`:
  - mean/median/std MAE and RMSE for each service across merchants
- `per_merchant`:
  - merchant-level KNN and forecast metrics
  - calibration mode and SARIMA metadata
  - corrected observed-only forecast MAE fields

Artifacts live under:

- `service_eval_outputs/unified/latest/`
- `service_eval_outputs/multi/latest/`
- `service_eval_outputs/multi_volume/latest/`
- archived snapshots under `service_eval_outputs/*/archive/`

## Practical Notes

- Results depend strongly on:
  - reference-merchant pool size
  - chosen target merchants
  - `card_types` filters
  - calibration context window length
- Real `proc_cost` in this dataset contains flat-fee components, so `proc_cost_pct`
  can exceed 1.0. This is expected and affects absolute error scale.
- If a run cannot start APIs, verify ports `8090`, `8091`, and `8092` are free.
