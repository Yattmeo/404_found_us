#!/usr/bin/env python3
import sys
sys.path.insert(0, 'ml_pipeline/Matt_EDA/Supervised learning')

import pandas as pd
import numpy as np
from knn_lr_models import KNNWeekwiseLinearRegression

# Create a small test case
test_data = pd.DataFrame({
    'merchant_id': [1, 1, 1, 2, 2, 2],
    'split_year': [2018, 2018, 2018, 2018, 2018, 2018],
    'week_of_year': [1, 2, 3, 1, 2, 3],
    'cost_percent': [0.1, 0.2, 0.3, 0.15, 0.25, 0.35],
    'feature1': [1.0, 2.0, 3.0, 1.5, 2.5, 3.5]
})

query_data = test_data[test_data['merchant_id'] == 1].copy()
pool_data = test_data.copy()

feature_cols = ['cost_percent', 'feature1']
model = KNNWeekwiseLinearRegression(feature_cols=feature_cols, k_neighbors=1, trajectory_weeks=[1, 2])

try:
    pred = model.predict(
        query_merchant_id=1,
        query_data=query_data,
        context_weeks=[1, 2],
        eval_weeks=[3],
        all_weekly_df=test_data,
        feature_cols=feature_cols,
        pool_weekly_df=pool_data
    )
    print(f"Prediction successful: {pred}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
