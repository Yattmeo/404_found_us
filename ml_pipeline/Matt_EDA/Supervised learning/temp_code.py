# Attempt 3: Simple time-series methods — EWMA, trend, last-value, recent-half-mean

ewma_maes, trend_maes, lastval_maes, recent_maes = [], [], [], []

for s in valid_test_scenarios_6:
    ctx = s['context_data']['avg_proc_cost_pct'].values      # len 6
    hor = s['horizon_data']['avg_proc_cost_pct'].values      # len 3

    # Method 1: EWMA alpha=0.4 — exponential weights over 6 context months
    alpha = 0.4
    weights = np.array([(1 - alpha) ** i for i in range(5, -1, -1)])  # oldest to newest
    weights /= weights.sum()
    ewma_pred = np.dot(weights, ctx)
    ewma_maes.append(np.mean(np.abs(hor - ewma_pred)))

    # Method 2: Linear trend extrapolation — polyfit over context, extrapolate t+1/2/3
    slope, intercept = np.polyfit(np.arange(6), ctx, 1)
    trend_preds = np.array([slope * (6 + h) + intercept for h in range(3)])
    trend_maes.append(np.mean(np.abs(hor - trend_preds)))

    # Method 3: Last-value naive — predict context[-1] flat
    lastval_maes.append(np.mean(np.abs(hor - ctx[-1])))

    # Method 4: Recent-3-month mean — mean of last 3 context months flat
    recent_mean = np.mean(ctx[-3:])
    recent_maes.append(np.mean(np.abs(hor - recent_mean)))

ewma_mae      = np.mean(ewma_maes)
trend_mae     = np.mean(trend_maes)
lastval_mae   = np.mean(lastval_maes)
recent_mae    = np.mean(recent_maes)

print("=" * 70)
print("ATTEMPT 3: Simple Methods vs Mean Baseline (context_len=6, horizon_len=3)")
print("=" * 70)
print(f"Mean Baseline MAE       : {mean_baseline_mae_6:.6f}")
print(f"EWMA (alpha=0.4)        : {ewma_mae:.6f}  ({(mean_baseline_mae_6-ewma_mae)/mean_baseline_mae_6*100:+.2f}%)")
print(f"Linear Trend            : {trend_mae:.6f}  ({(mean_baseline_mae_6-trend_mae)/mean_baseline_mae_6*100:+.2f}%)")
print(f"Last-Value Naive        : {lastval_mae:.6f}  ({(mean_baseline_mae_6-lastval_mae)/mean_baseline_mae_6*100:+.2f}%)")
print(f"Recent-3-Month Mean     : {recent_mae:.6f}  ({(mean_baseline_mae_6-recent_mae)/mean_baseline_mae_6*100:+.2f}%)")
print("=" * 70)
all_maes = {'EWMA': ewma_mae, 'Trend': trend_mae, 'Last-Value': lastval_mae, 'Recent-Mean': recent_mae}
best_method = min(all_maes, key=all_maes.get)
best_mae = all_maes[best_method]
if best_mae < mean_baseline_mae_6:
    print(f"BASELINE BEATEN ✓ — {best_method}: {best_mae:.6f} ({(mean_baseline_mae_6-best_mae)/mean_baseline_mae_6*100:+.2f}%)")
else:
    print(f"NO METHOD BEATS BASELINE ✗ — Best: {best_method} = {best_mae:.6f}")
print("=" * 70)
