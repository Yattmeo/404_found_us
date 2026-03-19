# Tree-Based TCR Forecasting Prototype Report

## Abstract
This report summarizes a strict leakage-safe forecasting study for merchant TCR, where each prediction uses one input month t to forecast t+1, t+2, and t+3. The objective was to test whether tree-based methods could outperform a persistence baseline under realistic holdout conditions. The final evaluation protocol enforces merchant disjointness and temporal safety. Across all tested methods, a calibrated persistence approach (Method 6) produced the best overall MAE and was selected for follow-up development.

## Problem Statement
Given features available at month t, predict merchant TCR for the next three months. This is a multi-horizon regression task intended for operational forecasting where only current-month information is available at inference time.

## Data and Supervised Framing
The notebook uses merchant-month records from the local SQLite dataset and constructs supervised targets by shifting TCR by +1, +2, and +3 months per merchant. Rows with incomplete future targets are removed. Calendar features are included from the current month only.

## Leakage-Safe Evaluation Design
The study uses a strict split to prevent both temporal and entity leakage:
- Test merchants are fully held out from training.
- Test rows are restricted to 2019 input months.
- Training input months are capped at 2018-09 so that training labels do not include 2019 target months.
- Hyperparameter tuning is run on training data only, with grouped cross-validation where needed.

This protocol ensures that measured performance reflects realistic generalization to unseen merchants and future periods.

## Baseline and Model Families
The primary benchmark is persistence: predict all future horizons as the current-month TCR. This baseline is intentionally simple and difficult to beat under strict conditions.

The notebook evaluates:
- Decision Tree, Random Forest, Extra Trees, Gradient Boosting, and XGBoost (when available).
- Additional methods designed to improve robustness and calibration, including delta modeling, horizon-specific modeling, winsorized targets, recency weighting, residual correction, blending, and linear calibration.

## Metrics and Decision Rule
The primary selection metric is overall MAE (mean across t+1, t+2, t+3), supported by RMSE and R2. A method is considered viable only if it improves on baseline under the strict split.

## Key Results
Under strict leakage-safe evaluation, many high-capacity tree variants did not consistently beat persistence. Method 6, which applies horizon-wise robust linear calibration from current-month TCR to each forecast horizon, achieved the best overall MAE among all tracked methods and slightly improved over baseline.

Interpretation:
- Persistence captures strong short-term signal in this dataset.
- Complex residual structures are comparatively weak under merchant-disjoint generalization.
- Small but stable gains are achievable through calibration rather than full nonlinear replacement.

## Selected Method and Handoff
Method 6 (Linear Calibration) is selected as the archival handoff model because it offers:
- Best overall MAE in the final scoreboard.
- Strong interpretability through horizon-specific coefficients and intercepts.
- Low implementation complexity and reduced overfitting risk.

Further development will continue in a separate notebook, focusing on robustness checks, recalibration frequency, and deployment-style monitoring.

## Limitations
- Results are sensitive to strict merchant holdout and the available feature set at month t.
- Gains over baseline are modest; operational significance should be assessed with downstream business thresholds.
- No production retraining cadence or drift response policy is finalized in this notebook.

## Conclusion
This prototype demonstrates that strict evaluation materially changes model ranking and that persistence remains a strong reference. The study recommends Method 6 as the most practical improvement path: calibrated persistence that is leakage-safe, interpretable, and incrementally better than baseline.