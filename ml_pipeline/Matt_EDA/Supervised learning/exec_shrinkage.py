# Cell execution script for Bayesian Shrinkage
import sys
import os

# Ensure we're using the correct path
os.chdir('/Users/yattmeo/Desktop/SMU/Code/404_found_us/ml_pipeline/Matt_EDA/Supervised learning')

# Execute the code (assuming kernel has all required variables)
exec('''
# Attempt 4: Bayesian Shrinkage — blend context_mean towards global_mean
# pred = (1 - alpha) * context_mean + alpha * global_mean
# Find optimal alpha via 80/20 cross-validation on valid_test_scenarios_6

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
print(f"\\nMean Baseline MAE (all)   : {mean_baseline_mae_6:.6f}")
print(f"Shrinkage MAE (all)       : {shrinkage_mae_all:.6f}  ({improvement:+.2f}%)")
print(f"Baseline beaten           : {'YES ✓' if shrinkage_mae_all < mean_baseline_mae_6 else 'NO ✗'}")
print("=" * 70)
''')
