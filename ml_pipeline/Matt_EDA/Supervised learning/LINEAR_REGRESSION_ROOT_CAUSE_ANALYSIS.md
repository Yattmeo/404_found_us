# Linear Regression Underperformance: Root Cause Analysis

## Executive Summary
Linear regression models are performing **34% worse** than the baseline constant mean:
- **Baseline MAE**: 0.2748 ✓
- **Linear Regression MAE**: 0.3688 ✗ (34% worse)
- **Ridge Regression MAE**: 0.3688 ✗ (identical, regularization doesn't help)

This analysis identifies the root causes and proposes solutions.

---

## Problem Specification

### Test Configuration
```
Pool: 35,888 records (all merchants, all prior years + context weeks)
Test: 16 merchants in 2019 with complete data
Context: Weeks 1-4 (4 weeks observed)
Eval: Weeks 5-16 (12 weeks to forecast)
Features: transaction count, total amount, proc costs, cost_type splits, cost_stdev
```

### Key Metrics
```
Baseline (context mean):
  - MAE: 0.2748 ± 0.1532 std
  - MAPE: 57.7%

Linear Regression:
  - MAE: 0.3688 ± 0.1144 std
  - MAPE: 57.2%
  - Δ MAE: +0.0940 (+34.2%)

Ridge Regression (alpha=1):
  - MAE: 0.3688 ± 0.1144 std
  - MAPE: 57.2%
  - Δ MAE: +0.0940 (+34.2%)
  - Note: Identical to LR, so regularization doesn't address the core problem
```

---

## Root Cause Analysis

### 1. **CRITICAL: Flawed Residual Learning Strategy** ⚠️

#### Problem
The model predicts residuals from the **context mean**, not absolute values:
```python
# Training target:
y = (merged['cost_percent'] - merged['context_mean']).fillna(0).values

# Prediction:
pred = context_mean + residual
```

#### Why This Fails
- The baseline **already uses the context mean** as its prediction
- By design, the model is trying to improve upon context_mean with a residual adjustment
- **The residuals are noisy deviations around zero** (by definition: centered at 0)
- If the residual model predicts anything other than exactly 0, it drifts from the baseline
- **Best-case scenario**: Model learns residuals ≈ 0 → Results in context_mean (baseline)
- **Actual scenario**: Model learns noisy residuals → Overshoots/undershoots baseline

#### Visual Evidence
The box plot (cell 23) shows:
- Baseline has tight distribution (median=0.25, range mostly 0.04-0.43)
- Linear models have wider distributions (Q1=0.32, Q3=0.45, max=0.70)
- **Linear models are adding noise rather than signal**

---

### 2. **Limited Feature Predictiveness**

#### Problem
Available features are static measurements within each week:
```
Features available:
  - total_transactions: count of transactions
  - total_amount: total transaction value
  - total_proc_cost: total processing cost
  - cost_percent_stdev: standard deviation
  - cost_type_1 through cost_type_61: cost breakdowns by transaction type
```

#### Issues
1. **No lagged features**: The model uses week N features to predict week N+1
   - But there's **no historical lag** - features are only available for weeks with data
   - For ahead-of-time forecasting, need lagged features from prior weeks
   - Current implementation: `source_week = eval_week - 1` → predicts from adjacent week only

2. **Weekly aggregation loss**: 
   - Original transaction data has daily granularity
   - Aggregated to weekly level for training
   - Loss of temporal patterns within weeks

3. **Features don't capture trend**: 
   - Only current-week statistics available
   - No trend indicator (is cost_percent increasing/decreasing?)
   - No momentum/acceleration features

4. **Cost type features may be sparse or correlated**:
   - 61 cost_type features (cost_type_1 through cost_type_61)
   - Many merchants may only use a few cost types
   - Sparsity leads to overfitting in pool data, poor generalization to test merchants

---

### 3. **Feature Cascade Problem**

#### Problem - Current Implementation
```python
# For eval weeks not in merchant's actual data:
current_values[eval_week] = features  # Store for next iteration

# But "features" haven't been updated!
# They're from source_week or zeros
current_values[eval_week] = features  # ← Still contains stale/zero values
```

#### This Creates Cascading Errors
```
Week 5 prediction:
  Use actual features from week 4 → predictions use real context features

Week 6 prediction:
  Use features from week 5 (not available) → falls back to prev iteration's features
  Which are from week 4 since week 5 was never updated properly

Week 7-16 predictions:
  Chain of cascading feature staleness
  All using context features that become increasingly irrelevant for future predictions
```

#### Example
For merchant in year 2019 predicting weeks 5-16:
- Week 5: features from week 4 (1 week ahead) - reasonable
- Week 6: features should be from week 5, but not available, reuses week 4 features (2 weeks stale)
- Week 7-16: increasing staleness to 10+ weeks old

**Degradation hypothesis**: Predictions become worse further ahead because features are increasingly stale

---

### 4. **Feature Mismatch: Pool vs. Test Distribution**

#### Problem
Pool data contains merchants from **all years** (2015-2018, then 2019 context through week 8).
Test data is 16 specific merchants from **2019 only**.

#### Distribution Mismatch
- Pool merchants' behavior may differ from 2019 merchants
- 2019 cost_percent distribution may not match historical patterns
- Model trained on diverse merchants, applied to specific cohort
- No per-merchant adaptation in training

#### Effect on Linear Models
- Baseline (context mean) **adapts per merchant** by computing their specific mean
- Linear model uses **global weekly coefficients** trained on pool data
- Context mean captures merchant-specific baseline; LR tries to adjust globally
- If test merchants' dynamics differ from pool → LR coefficients become misaligned

---

### 5. **Insufficient Regularization (for Ridge)**

#### Problem
Ridge regression uses alpha=1.0, which may not be strong enough.

However, this explains **why Ridge doesn't help**:
- The real problem isn't overfitting
- The problem is the fundamental strategy: predicting residuals from context mean
- Ridge reduces magnitudes but still can't fix the strategy issue
- Result: Ridge learns even smaller residuals ≈ 0 → but still worse than baseline

Gradient: Stronger regularization (alpha=10 or 100) would push residuals closer to 0 → closer to baseline performance, but never better.

---

### 6. **Small Test Set and High Variance**

#### Problem
- Only 16 merchants meet data quality criteria
- Enough to measure baseline performance
- Possibly not enough to validate LR benefits
- LR has higher std on MAE (0.1144 vs 0.1532) but higher median (0.3907 vs 0.2501)
- Suggests LR works well for some merchants, poorly for others

---

## Why Baseline Wins: Context Mean Strategy

The baseline constant mean works because:

1. **It's adaptive**: Computes each merchant's average from their actual context weeks
2. **It's stable**: Takes mean, not affected by single outliers (vs. using week 4 features for prediction)
3. **It's unbiased**: No model assumptions, just average of observed data
4. **It's robust**: Works for all merchants, doesn't assume pool generalization

For stable cost metrics where recent history is predictive, this is **hard to beat**.

---

## Solutions & Recommendations

### Priority 1: Rethink the Modeling Strategy
**Problem**: Residual learning from context mean is fundamentally flawed for beating baseline

**Solutions**:
1. **Direct prediction** (not relative to context mean):
   ```python
   # Train: week_N_features → week_N+1_cost_percent (absolute value)
   # Predict: use learned trend from pool data
   # For test merchant: cold-start with pool mean, then adapt with context
   ```

2. **Hybrid approach**: 
   ```python
   # prediction = α * (pool_model_prediction) + β * (context_mean)
   # Learn α, β weights, allowing flexibility
   ```

3. **Seasonal decomposition**:
   ```python
   # Decompose: cost_percent = seasonality + trend + residual
   # Model trend/seasonality separately, predict individual components
   ```

### Priority 2: Feature Engineering
1. **Add lagged features**:
   - Week t-1, t-2, t-3 values for all features (where available)
   - Trend: (week_t - week_t-1) & (week_t-1 - week_t-2)
   - Volatility: std of past 4 weeks

2. **Add temporal features**:
   - Day of week effects (if daily data available)
   - Week-of-year seasonality (sine/cosine encoding)

3. **Reduce feature dimensionality**:
   - PCA on cost_type features (61 → 5-10 components)
   - Or select only high-variance cost types

4. **Normalize/standardize features**:
   - Currently using raw values within models
   - May cause coefficient instability

### Priority 3: Model Architecture
1. **Separate models by merchant segment**:
   - High-cost vs. low-cost merchants
   - Different seasonal patterns
   - Train separate models for each segment

2. **Time series methods**:
   - Instead of per-week linear regression
   - Use ARIMA/SARIMA (already in notebook!)
   - Or exponential smoothing for each merchant

3. **Ensemble**:
   - Combine baseline + SARIMA + LR with learned weights
   - Use cross-validation to optimize weights

### Priority 4: Validation Strategy
1. **Cross-validation on pool data**:
   - Before running on test set, validate improvement on pool
   - Holdout validation set from historical data
   
2. **Per-merchant analysis**:
   - Identify which merchants LR helps vs. hurts
   - Understand the pattern

3. **Ablation studies**:
   - Train without cost_type features
   - Train without sparse features
   - Identify which features help/hurt

---

## Immediate Action Items

### 1. Quick Fix: Direct Prediction Model
Try training on absolute cost_percent instead of residuals:

```python
# Modified WeekwiseLinearRegression
class DirectPredictionLR:
    def train(self, pool_weekly_df):
        for source_week in range(1, 53):
            target_week = source_week + 1 if source_week < 52 else 1
            
            source_data = pool_weekly_df[pool_weekly_df['week_of_year'] == source_week]
            target_data = pool_weekly_df[pool_weekly_df['week_of_year'] == target_week]
            
            merged = source_data.merge(target_data, on='merchant_id', how='inner')
            X = merged[source_features].fillna(0).values
            y = merged['cost_percent'].fillna(0).values  # ← DIRECT, not residual
            
            model = LinearRegression()
            model.fit(X, y)
            self.models[source_week] = model
    
    def predict(self, ...):
        for eval_week in eval_weeks:
            source_week = eval_week - 1 if eval_week > 1 else 52
            # ... get features ...
            pred = self.models[source_week].predict(features)[0]  # ← Direct prediction
            pred = np.clip(pred, 0, 1)  # Ensure valid range
            predictions.append(pred)
        return np.array(predictions)
```

Expected outcome: At least comparable to baseline, possibly better.

### 2. Fallback Strategy
If supervised models continue to underperform:
- Use SARIMA (already in notebook) as primary
- Use baseline constant mean as secondary
- Ensemble the two approaches

### 3. Investigate Merchant Segments
Analyze:
- Which merchants have LR MAE > baseline?
- Are they high-cost or low-cost?
- Different transaction patterns?
- Can we identify a rule to choose baseline vs. LR per merchant?

---

## Conclusion

The linear regression models are failing because:

1. **Strategic flaw**: Predicting residuals from context mean (which is already the test set's best predictor)
2. **Feature limitations**: No lagged/trend features, limited temporal information
3. **Distribution mismatch**: Pool data from many years/merchants, test is specific 2019 cohort
4. **Architecture issue**: Week-wise independent models, no time series structure

**Key insight**: The baseline constant mean is actually quite hard to beat for weekly cost prediction because:
- Cost metrics are relatively stable
- Recent context is highly predictive
- No clear weekly-to-weekly drift pattern

**Recommendation**: Pivot to direct prediction or ensemble approaches that acknowledge baseline strength rather than trying to improve upon its residuals.

---

## References
- Notebook: `ml_pipeline/Matt_EDA/Supervised learning/Unified SARIMA vs Supervised Benchmark.ipynb`
- Model code: lines 1008-1324 (WeekwiseLinearRegression, WeekwiseRidgeRegression)
- Evaluation: lines 1384-1534
- Results visualization: cells 22-24
