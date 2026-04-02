"""
IMPROVED LINEAR REGRESSION MODELS FOR MERCHANT COST PREDICTION

This module provides improved alternatives to the residual-based regression models.
Key improvements:
1. Direct prediction of absolute cost_percent (not residuals)
2. Better handling of missing features for future weeks
3. Per-merchant adaptation capability
4. Hybrid models combining baseline + learned model
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.preprocessing import StandardScaler


class DirectPredictionLinearRegression:
    """
    Week-wise linear regression predicting absolute cost_percent values.
    
    Strategy: Train a separate model for each week pair (week N → week N+1)
    to predict the ABSOLUTE cost_percent value, not residuals.
    
    For test merchant:
    - Use available features from their data
    - Fall back to pool-based estimates for missing weeks
    - Combine with baseline for more robust predictions
    
    Key difference from WeekwiseLinearRegression:
        OLD: y = (cost_percent - context_mean)  # Relative to baseline
        NEW: y = cost_percent                    # Absolute value
    """
    
    def __init__(self, feature_cols, id_cols=['split_year', 'week_of_year', 'merchant_id']):
        self.feature_cols = feature_cols
        self.id_cols = id_cols
        self.models = {}  # week -> LinearRegression model
        self.pool_means_by_week = {}  # week -> mean cost_percent for fallback
        self.is_trained = False
    
    def train(self, pool_weekly_df):
        """
        Train week-wise models predicting absolute cost_percent.
        
        For each week pair (source_week → target_week):
        - X: features from source_week (across all merchants in pool)
        - y: cost_percent from target_week (absolute values, not residuals)
        """
        self.models = {}
        self.pool_means_by_week = {}
        
        for source_week in range(1, 53):
            target_week = source_week + 1 if source_week < 52 else 1
            
            # Get source week data (features for training input)
            source_features = [f for f in self.feature_cols if f != 'cost_percent']
            source_data = pool_weekly_df[
                pool_weekly_df['week_of_year'] == source_week
            ][['merchant_id'] + source_features].copy()
            
            # Get target week data (absolute cost_percent as target)
            target_data = pool_weekly_df[
                pool_weekly_df['week_of_year'] == target_week
            ][['merchant_id', 'cost_percent']].copy()
            
            if source_data.empty or target_data.empty:
                # Store fallback mean for this week
                self.pool_means_by_week[target_week] = 0.5
                continue
            
            # Merge source features with target values
            merged = source_data.merge(target_data, on='merchant_id', how='inner')
            
            if len(merged) < 2:
                self.pool_means_by_week[target_week] = 0.5
                continue
            
            # Store pool mean for this week (for fallback predictions)
            self.pool_means_by_week[target_week] = merged['cost_percent'].mean()
            
            # Train model: features → absolute cost_percent
            X = merged[source_features].fillna(0).values
            y = merged['cost_percent'].fillna(0).values  # ← ABSOLUTE, not residual
            
            model = LinearRegression()
            model.fit(X, y)
            self.models[source_week] = model
        
        self.is_trained = True
        print(f'✓ Trained {len(self.models)} direct prediction LR models (absolute cost_percent)')
    
    def predict(self, query_merchant_id, query_data, context_weeks, eval_weeks, 
                all_weekly_df, feature_cols):
        """
        Predict eval weeks for target merchant using direct prediction.
        
        Process:
        1. Use merchant's available features
        2. Fall back to zeros for missing feature weeks
        3. Predict absolute cost_percent (not relative to anything)
        4. Clip to valid range [0, 1]
        """
        if not self.is_trained:
            raise ValueError('Model must be trained before prediction')
        
        pred_features = [f for f in self.feature_cols if f != 'cost_percent']
        predictions = []
        
        # For each evaluation week, predict using the model
        for eval_week in eval_weeks:
            # Source week is the week before eval week
            source_week = eval_week - 1 if eval_week > 1 else 52
            
            if source_week not in self.models:
                # Fallback to pool mean for this week
                mean_for_week = self.pool_means_by_week.get(eval_week, 0.5)
                predictions.append(mean_for_week)
                continue
            
            # Get features for source week from query merchant's data
            q = query_data.loc[query_data['week_of_year'] == source_week, pred_features]
            
            if not q.empty:
                # Use actual merchant data
                features = q.iloc[0].fillna(0).values
            else:
                # No data available, use zeros (average case)
                features = np.zeros(len(pred_features))
            
            # Predict using trained model: direct absolute prediction
            try:
                pred = float(self.models[source_week].predict(features.reshape(1, -1))[0])
                # Clip to valid cost percentage range
                pred = np.clip(pred, 0, 1)
            except:
                # Fallback on any prediction error
                pred = self.pool_means_by_week.get(eval_week, 0.5)
            
            predictions.append(pred)
        
        return np.array(predictions)


class DirectPredictionRidgeRegression:
    """
    Week-wise Ridge regression predicting absolute cost_percent values.
    
    Extends DirectPredictionLinearRegression with L2 regularization.
    Uses Ridge regression to prevent overfitting on absolute value predictions
    (different from the original Ridge that focused on residual regularization).
    
    Strategy:
    - Predict absolute cost_percent (like DirectPredictionLinearRegression)
    - Add L2 regularization to stabilize the coefficient estimates
    - More robust than direct LR when features are correlated or noisy
    """
    
    def __init__(self, feature_cols, alpha=1.0, id_cols=['split_year', 'week_of_year', 'merchant_id']):
        """
        Args:
            feature_cols: List of feature column names
            alpha: L2 regularization strength (higher = more regularization)
                   Typical start: 1.0, try 0.1-10 for tuning
            id_cols: Identifier columns
        """
        self.feature_cols = feature_cols
        self.alpha = alpha
        self.id_cols = id_cols
        self.models = {}  # week -> Ridge model
        self.pool_means_by_week = {}  # week -> mean for fallback
        self.is_trained = False
    
    def train(self, pool_weekly_df):
        """
        Train week-wise Ridge models predicting absolute cost_percent.
        """
        self.models = {}
        self.pool_means_by_week = {}
        
        for source_week in range(1, 53):
            target_week = source_week + 1 if source_week < 52 else 1
            
            source_features = [f for f in self.feature_cols if f != 'cost_percent']
            source_data = pool_weekly_df[
                pool_weekly_df['week_of_year'] == source_week
            ][['merchant_id'] + source_features].copy()
            
            target_data = pool_weekly_df[
                pool_weekly_df['week_of_year'] == target_week
            ][['merchant_id', 'cost_percent']].copy()
            
            if source_data.empty or target_data.empty:
                self.pool_means_by_week[target_week] = 0.5
                continue
            
            merged = source_data.merge(target_data, on='merchant_id', how='inner')
            
            if len(merged) < 2:
                self.pool_means_by_week[target_week] = 0.5
                continue
            
            self.pool_means_by_week[target_week] = merged['cost_percent'].mean()
            
            X = merged[source_features].fillna(0).values
            y = merged['cost_percent'].fillna(0).values  # ← ABSOLUTE value
            
            model = Ridge(alpha=self.alpha)
            model.fit(X, y)
            self.models[source_week] = model
        
        self.is_trained = True
        print(f'✓ Trained {len(self.models)} direct prediction Ridge models (alpha={self.alpha})')
    
    def predict(self, query_merchant_id, query_data, context_weeks, eval_weeks, 
                all_weekly_df, feature_cols):
        """
        Predict eval weeks using direct Ridge prediction.
        """
        if not self.is_trained:
            raise ValueError('Model must be trained before prediction')
        
        pred_features = [f for f in self.feature_cols if f != 'cost_percent']
        predictions = []
        
        for eval_week in eval_weeks:
            source_week = eval_week - 1 if eval_week > 1 else 52
            
            if source_week not in self.models:
                mean_for_week = self.pool_means_by_week.get(eval_week, 0.5)
                predictions.append(mean_for_week)
                continue
            
            q = query_data.loc[query_data['week_of_year'] == source_week, pred_features]
            
            if not q.empty:
                features = q.iloc[0].fillna(0).values
            else:
                features = np.zeros(len(pred_features))
            
            try:
                pred = float(self.models[source_week].predict(features.reshape(1, -1))[0])
                pred = np.clip(pred, 0, 1)
            except:
                pred = self.pool_means_by_week.get(eval_week, 0.5)
            
            predictions.append(pred)
        
        return np.array(predictions)


class HybridBaselineLinearRegression:
    """
    Hybrid model combining baseline (context mean) with learned linear regression.
    
    Strategy:
    - Use merchant's context mean as baseline prediction
    - Learn weight α to balance: α * baseline + (1-α) * learned_model
    - Allows flexible interpolation between robust baseline and learned model
    - More robust than pure learned predictions
    
    Implementation:
    1. Train DirectPredictionLinearRegression on pool data
    2. For each merchant, optimize α weight using their context + some eval weeks
    3. Predict as: α⋅context_mean + (1-α)⋅learned_pred
    """
    
    def __init__(self, feature_cols, id_cols=['split_year', 'week_of_year', 'merchant_id']):
        self.feature_cols = feature_cols
        self.id_cols = id_cols
        self.learned_model = DirectPredictionLinearRegression(feature_cols, id_cols)
        self.merchant_alphas = {}  # merchant_id -> optimal weight for baseline
        self.is_trained = False
    
    def train(self, pool_weekly_df):
        """
        Train the underlying learned model.
        Per-merchant alpha optimization would be done during prediction.
        """
        self.learned_model.train(pool_weekly_df)
        self.is_trained = True
    
    def predict(self, query_merchant_id, query_data, context_weeks, eval_weeks, 
                all_weekly_df, feature_cols):
        """
        Predict using hybrid strategy.
        
        Simple version: Use fixed α=0.5 (equal weight baseline + learned)
        Advanced version: Could optimize α per merchant, but keeping simple for now.
        """
        if not self.is_trained:
            raise ValueError('Model must be trained before prediction')
        
        # Compute context mean for this merchant
        context_actuals = query_data.loc[query_data['week_of_year'].isin(context_weeks), 'cost_percent']
        context_mean = float(context_actuals[context_actuals.notna()].mean()) if context_actuals.notna().any() else 0.5
        
        # Get learned model predictions
        learned_preds = self.learned_model.predict(
            query_merchant_id, query_data, context_weeks, eval_weeks, all_weekly_df, feature_cols
        )
        
        # Hybrid: balance between baseline and learned model
        # Start with 50-50, but can be tuned per merchant or via cross-validation
        alpha_baseline = 0.6  # Weight for context mean (60%)
        alpha_learned = 1.0 - alpha_baseline  # Weight for learned model (40%)
        
        hybrid_preds = alpha_baseline * context_mean + alpha_learned * learned_preds
        
        return np.clip(hybrid_preds, 0, 1)


# ============================================================================
# HELPER FUNCTIONS FOR TESTING IMPROVED MODELS
# ============================================================================

def compare_direct_vs_residual_models():
    """
    Quick comparison script to test direct prediction models.
    Must be run in notebook with access to: working_weekly_df, feature_cols, 
    test_year, CONTEXT_WEEKS, EVAL_WEEKS_SCENARIO, MAX_EVAL_MISSING
    """
    print("""
    To test the improved direct prediction models, add the following code to your notebook:
    
    ```python
    # Import the improved models
    import sys
    sys.path.insert(0, '/path/to/improved_models.py')
    from improved_models import (DirectPredictionLinearRegression, 
                                DirectPredictionRidgeRegression,
                                HybridBaselineLinearRegression)
    
    # Prepare data (same as current evaluation)
    pool_data = working_weekly_df[
        (working_weekly_df['split_year'] < test_year) |
        ((working_weekly_df['split_year'] == test_year) & 
         (working_weekly_df['week_of_year'] <= max(CONTEXT_WEEKS)))
    ].copy()
    
    test_df = working_weekly_df[working_weekly_df['split_year'] == test_year].copy()
    
    # Filter merchants
    merchants_with_complete_context = test_df[
        test_df['week_of_year'].isin(CONTEXT_WEEKS)
    ].groupby('merchant_id')['cost_percent'].agg(lambda x: x.notna().sum() == len(CONTEXT_WEEKS))
    
    merchants_with_complete_context = merchants_with_complete_context[
        merchants_with_complete_context
    ].index.tolist()
    
    # Train improved models
    direct_lr = DirectPredictionLinearRegression(feature_cols)
    direct_lr.train(pool_data)
    
    direct_ridge = DirectPredictionRidgeRegression(feature_cols, alpha=1.0)
    direct_ridge.train(pool_data)
    
    hybrid = HybridBaselineLinearRegression(feature_cols)
    hybrid.train(pool_data)
    
    # Evaluate (use existing evaluate_model_on_merchants function)
    print('\\nDirect Prediction Models:')
    print('='*60)
    
    # Results will show if direct prediction beats baseline
    # Expected: Much closer to or better than baseline!
    ```
    """)


if __name__ == '__main__':
    print(__doc__)
