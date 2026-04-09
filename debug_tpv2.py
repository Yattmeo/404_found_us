"""Debug: trace TPV feature vector and prediction."""
import numpy as np
import joblib
from pathlib import Path
from modules.tpv_forecast.service import (
    _aggregate_transactions,
    _select_context_window,
    _build_feature_vector,
    _resolve_bundle,
    _compute_pool_info,
    _REPO,
)
from datetime import date

# Build the same synthetic rows the backend sends
rows = []
for m_offset in (3, 2, 1):
    today = date(2026, 4, 9)
    m = today.month - m_offset
    y = today.year + (m - 1) // 12
    m = ((m - 1) % 12) + 1
    for wk_day in (1, 8, 15, 22):
        day = date(y, m, wk_day)
        for _ in range(120):
            rows.append({
                "transaction_date": day.isoformat(),
                "amount": 3603.34,
                "proc_cost": 18.017,
                "cost_type_ID": 1,
                "card_type": "both",
                "monthly_txn_count": 1063100,
            })

# 1. Aggregate
all_months = _aggregate_transactions(rows)
print(f"Aggregated months: {len(all_months)}")
for ms in all_months:
    print(f"  {ms.year}-{ms.month:02d}: TPV=${ms.total_processing_value:,.2f}, "
          f"txn_count={ms.transaction_count}, avg_txn=${ms.avg_transaction_value:.2f}, "
          f"std_txn=${ms.std_txn_amount:.2f}, median=${ms.median_txn_amount:.2f}")

# 2. Context window
ctx = _select_context_window(all_months)
ctx_len = len(ctx)
print(f"\nContext window: {ctx_len} months")

# 3. Bundle
bundle = _resolve_bundle(5499, ctx_len)
print(f"Bundle found: {bundle is not None}")
if bundle:
    print(f"  trained_at: {bundle.trained_at}")
    print(f"  n_models: {len(bundle.models)}")

# 4. Pool info
flat_pool_mean, knn_pool_mean, peer_ids = _compute_pool_info(
    _REPO, 5499, ["both"], ctx
)
print(f"\nPool means: flat={flat_pool_mean:.4f}, knn={knn_pool_mean:.4f}")
print(f"Peer IDs: {peer_ids}")

# 5. Feature vector
X_raw = _build_feature_vector(ctx, knn_pool_mean)
print(f"\nRaw feature vector: {X_raw[0]}")
print(f"Feature names: [c_mean, c_std, momentum, pool_mean, txn_amount_std, log_txn, avg_median_gap, last_month, log_avg_txn_val, mom_tc, mom_atv]")

X_scaled = bundle.scaler.transform(X_raw)
print(f"Scaled feature vector: {X_scaled[0]}")

# 6. Predictions
for h in range(3):
    log_pred = bundle.models[h].predict(X_scaled)[0]
    dollar_pred = np.expm1(log_pred)
    print(f"\nHorizon {h+1}: log_pred={log_pred:.4f}, dollar_pred=${dollar_pred:,.2f}")

# 7. Compare with training data range
print(f"\nScaler mean: {bundle.scaler.mean_}")
print(f"Scaler scale: {bundle.scaler.scale_}")
print(f"\nFeature 0 (c_mean): input={X_raw[0][0]:.4f}, training_mean={bundle.scaler.mean_[0]:.4f}")
print(f"  Difference: {X_raw[0][0] - bundle.scaler.mean_[0]:.4f} (in log1p space)")
print(f"  Input dollar equivalent: ${np.expm1(X_raw[0][0]):,.2f}")
print(f"  Training mean dollar equivalent: ${np.expm1(bundle.scaler.mean_[0]):,.2f}")
