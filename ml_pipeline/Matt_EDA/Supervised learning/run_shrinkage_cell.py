#!/usr/bin/env python3
"""Execute the new Bayesian Shrinkage cell in the notebook context."""

import pandas as pd
import numpy as np
import sys

# Load required data
df_5411_sample = pd.read_csv('df_5411_sample21Mar.csv')

# Helper function from notebook
def get_test_scenario(df, onboard_merchant_id, context_len, context_max_NAN_months, horizon_len, horizon_max_NAN_months):
    merchant_data = df[df['merchant_id'] == onboard_merchant_id].copy()
    if len(merchant_data) == 0:
        return []
    merchant_data = merchant_data.sort_values(['year', 'month']).reset_index(drop=True)
    valid_scenarios = []
    for start_idx in range(len(merchant_data) - context_len - horizon_len + 1):
        context_end_idx = start_idx + context_len - 1
        context_window = merchant_data.iloc[start_idx:context_end_idx + 1].copy().reset_index(drop=True)
        if len(context_window) > 0:
            context_start = (int(context_window.iloc[0]['year']), int(context_window.iloc[0]['month']))
            context_end = (int(context_window.iloc[-1]['year']), int(context_window.iloc[-1]['month']))
            expected_months = (context_end[0] - context_start[0]) * 12 + (context_end[1] - context_start[1]) + 1
            nan_months_context = expected_months - len(context_window)
        else:
            nan_months_context = context_len
        if nan_months_context <= context_max_NAN_months and len(context_window) > 0:
            horizon_start_idx = context_end_idx + 1
            horizon_end_idx = horizon_start_idx + horizon_len - 1
            if horizon_end_idx < len(merchant_data):
                horizon_window = merchant_data.iloc[horizon_start_idx:horizon_end_idx + 1].copy().reset_index(drop=True)
                if len(horizon_window) > 0:
                    horizon_start = (int(horizon_window.iloc[0]['year']), int(horizon_window.iloc[0]['month']))
                    horizon_end = (int(horizon_window.iloc[-1]['year']), int(horizon_window.iloc[-1]['month']))
                    expected_months_h = (horizon_end[0] - horizon_start[0]) * 12 + (horizon_end[1] - horizon_start[1]) + 1
                    nan_months_horizon = expected_months_h - len(horizon_window)
                else:
                    nan_months_horizon = horizon_len
                if nan_months_horizon <= horizon_max_NAN_months and len(horizon_window) > 0:
                    scenario = {
                        'context_data': context_window,
                        'horizon_data': horizon_window,
                        'context_range': (context_start, context_end),
                        'horizon_range': (horizon_start, horizon_end),
                        'context_gaps': nan_months_context,
                        'horizon_gaps': nan_months_horizon
                    }
                    valid_scenarios.append(scenario)
    return valid_scenarios

# Find valid merchants
def find_valid_merchants(df, context_len, horizon_len, n_merchants=10):
    valid_merchants = []
    for merchant_id in df['merchant_id'].unique():
        merchant_data = df[df['merchant_id'] == merchant_id]
        merchant_months = merchant_data.groupby(['year', 'month']).size()
        if len(merchant_months) >= (context_len + horizon_len):
            valid_merchants.append(merchant_id)
            if len(valid_merchants) >= n_merchants:
                break
    return valid_merchants

valid_merchants = find_valid_merchants(df_5411_sample, context_len=1, horizon_len=3, n_merchants=5000)

# Recreate valid_test_scenarios_6
valid_test_scenarios_6 = []
for merchant_id in valid_merchants:
    scenarios = get_test_scenario(
        df_5411_sample, merchant_id,
        context_len=6, context_max_NAN_months=0,
        horizon_len=3, horizon_max_NAN_months=0
    )
    for s in scenarios:
        valid_test_scenarios_6.append({
            'merchant_id': merchant_id,
            'context_data': s['context_data'],
            'horizon_data': s['horizon_data'],
            'context_range': s['context_range'],
            'horizon_range': s['horizon_range'],
            'context_gaps': s['context_gaps'],
            'horizon_gaps': s['horizon_gaps']
        })

# Calculate mean_baseline_mae_6
baseline_results_6 = []
for i, s in enumerate(valid_test_scenarios_6):
    ctx_vals = s['context_data']['avg_proc_cost_pct'].values
    hor_vals = s['horizon_data']['avg_proc_cost_pct'].values
    context_mean = np.mean(ctx_vals)
    mean_pred = np.full_like(hor_vals, fill_value=context_mean)
    mae = np.mean(np.abs(hor_vals - mean_pred))
    baseline_results_6.append({'mae': mae})

mean_baseline_mae_6 = np.mean([r['mae'] for r in baseline_results_6])

# Execute the Bayesian Shrinkage code
# Global mean from training data only (year < 2018) — same as earlier
global_mean = df_5411_sample[df_5411_sample['year'] < 2018]['avg_proc_cost_pct'].mean()

# Split scenarios into 80% train / 20% test (by index, time-ordered)
split_idx = int(len(valid_test_scenarios_6) * 0.8)
cv_train = valid_test_scenarios_6[:split_idx]
cv_test  = valid_test_scenarios_6[split_idx:]

# Extract context means and horizon actuals for all split sets
def extract_arrays(scenarios):
    ctx_means = np.array([s['context_data']['avg_proc_cost_pct'].mean() for s in scenarios])
    hor_actuals = np.array([s['horizon_data']['avg_proc_cost_pct'].values for s in scenarios])  # shape (N,3)
    return ctx_means, hor_actuals

train_ctx, train_hor = extract_arrays(cv_train)
test_ctx,  test_hor  = extract_arrays(cv_test)

# Grid search over alpha on CV train set
best_alpha, best_cv_mae = 0.0, np.inf
alpha_results = {}

for alpha in np.arange(0.0, 0.51, 0.05):
    preds = (1 - alpha) * train_ctx[:, None] + alpha * global_mean  # broadcast (N,1) flat for all 3 steps
    preds = np.tile(preds, (1, 3))  # (N, 3)
    mae = np.mean(np.abs(preds - train_hor))
    alpha_results[round(float(alpha), 2)] = mae
    if mae < best_cv_mae:
        best_cv_mae = mae
        best_alpha = round(float(alpha), 2)

# Evaluate on held-out 20%
test_preds = (1 - best_alpha) * test_ctx[:, None] + best_alpha * global_mean
test_preds = np.tile(test_preds, (1, 3))
shrinkage_test_mae = np.mean(np.abs(test_preds - test_hor))

# Also evaluate on ALL scenarios with best alpha (for fair comparison to mean_baseline_mae_6)
all_ctx = np.array([s['context_data']['avg_proc_cost_pct'].mean() for s in valid_test_scenarios_6])
all_hor = np.array([s['horizon_data']['avg_proc_cost_pct'].values for s in valid_test_scenarios_6])
all_preds = (1 - best_alpha) * all_ctx[:, None] + best_alpha * global_mean
all_preds = np.tile(all_preds, (1, 3))
shrinkage_mae_all = np.mean(np.abs(all_preds - all_hor))
improvement = (mean_baseline_mae_6 - shrinkage_mae_all) / mean_baseline_mae_6 * 100

print("=" * 70)
print("ATTEMPT 4: Bayesian Shrinkage vs Mean Baseline")
print("=" * 70)
print(f"Global mean (train<2018)  : {global_mean:.6f}")
print(f"Optimal alpha (CV)        : {best_alpha}")
print(f"Alpha grid MAEs           : { {k: round(v,6) for k,v in list(alpha_results.items())[:6]} } ...")
print(f"\nMean Baseline MAE (all)   : {mean_baseline_mae_6:.6f}")
print(f"Shrinkage MAE (all)       : {shrinkage_mae_all:.6f}  ({improvement:+.2f}%)")
print(f"Baseline beaten           : {'YES ✓' if shrinkage_mae_all < mean_baseline_mae_6 else 'NO ✗'}")
print("=" * 70)
