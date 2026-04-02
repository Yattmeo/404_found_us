import pandas as pd
import numpy as np
import sys
import json

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

# Now execute the new code
ewma_maes, trend_maes, lastval_maes, recent_maes = [], [], [], []

for s in valid_test_scenarios_6:
    ctx = s['context_data']['avg_proc_cost_pct'].values      # len 6
    hor = s['horizon_data']['avg_proc_cost_pct'].values      # len 3

    # Method 1: EWMA alpha=0.4
    alpha = 0.4
    weights = np.array([(1 - alpha) ** i for i in range(5, -1, -1)])
    weights /= weights.sum()
    ewma_pred = np.dot(weights, ctx)
    ewma_maes.append(np.mean(np.abs(hor - ewma_pred)))

    # Method 2: Linear trend extrapolation
    slope, intercept = np.polyfit(np.arange(6), ctx, 1)
    trend_preds = np.array([slope * (6 + h) + intercept for h in range(3)])
    trend_maes.append(np.mean(np.abs(hor - trend_preds)))

    # Method 3: Last-value naive
    lastval_maes.append(np.mean(np.abs(hor - ctx[-1])))

    # Method 4: Recent-3-month mean
    recent_mean = np.mean(ctx[-3:])
    recent_maes.append(np.mean(np.abs(hor - recent_mean)))

ewma_mae      = np.mean(ewma_maes)
trend_mae     = np.mean(trend_maes)
lastval_mae   = np.mean(lastval_maes)
recent_mae    = np.mean(recent_maes)

print('=' * 70)
print('ATTEMPT 3: Simple Methods vs Mean Baseline (context_len=6, horizon_len=3)')
print('=' * 70)
print(f'Mean Baseline MAE       : {mean_baseline_mae_6:.6f}')
print(f'EWMA (alpha=0.4)        : {ewma_mae:.6f}  ({(mean_baseline_mae_6-ewma_mae)/mean_baseline_mae_6*100:+.2f}%)')
print(f'Linear Trend            : {trend_mae:.6f}  ({(mean_baseline_mae_6-trend_mae)/mean_baseline_mae_6*100:+.2f}%)')
print(f'Last-Value Naive        : {lastval_mae:.6f}  ({(mean_baseline_mae_6-lastval_mae)/mean_baseline_mae_6*100:+.2f}%)')
print(f'Recent-3-Month Mean     : {recent_mae:.6f}  ({(mean_baseline_mae_6-recent_mae)/mean_baseline_mae_6*100:+.2f}%)')
print('=' * 70)
all_maes = {'EWMA': ewma_mae, 'Trend': trend_mae, 'Last-Value': lastval_mae, 'Recent-Mean': recent_mae}
best_method = min(all_maes, key=all_maes.get)
best_mae = all_maes[best_method]
if best_mae < mean_baseline_mae_6:
    print(f'BASELINE BEATEN ✓ — {best_method}: {best_mae:.6f} ({(mean_baseline_mae_6-best_mae)/mean_baseline_mae_6*100:+.2f}%)')
else:
    print(f'NO METHOD BEATS BASELINE ✗ — Best: {best_method} = {best_mae:.6f}')
print('=' * 70)

# Write output to file
with open('cell_output.txt', 'w') as f:
    f.write('=' * 70 + '\n')
    f.write('ATTEMPT 3: Simple Methods vs Mean Baseline (context_len=6, horizon_len=3)\n')
    f.write('=' * 70 + '\n')
    f.write(f'Mean Baseline MAE       : {mean_baseline_mae_6:.6f}\n')
    f.write(f'EWMA (alpha=0.4)        : {ewma_mae:.6f}  ({(mean_baseline_mae_6-ewma_mae)/mean_baseline_mae_6*100:+.2f}%)\n')
    f.write(f'Linear Trend            : {trend_mae:.6f}  ({(mean_baseline_mae_6-trend_mae)/mean_baseline_mae_6*100:+.2f}%)\n')
    f.write(f'Last-Value Naive        : {lastval_mae:.6f}  ({(mean_baseline_mae_6-lastval_mae)/mean_baseline_mae_6*100:+.2f}%)\n')
    f.write(f'Recent-3-Month Mean     : {recent_mae:.6f}  ({(mean_baseline_mae_6-recent_mae)/mean_baseline_mae_6*100:+.2f}%)\n')
    f.write('=' * 70 + '\n')
    if best_mae < mean_baseline_mae_6:
        f.write(f'BASELINE BEATEN ✓ — {best_method}: {best_mae:.6f} ({(mean_baseline_mae_6-best_mae)/mean_baseline_mae_6*100:+.2f}%)\n')
    else:
        f.write(f'NO METHOD BEATS BASELINE ✗ — Best: {best_method} = {best_mae:.6f}\n')
    f.write('=' * 70 + '\n')
