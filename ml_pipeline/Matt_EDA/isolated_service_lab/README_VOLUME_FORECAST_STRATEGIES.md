# Volume Forecast Improvement Backlog

This document captures planned strategies to improve handling of:

- weeks with no transactions
- anomalous (spike/drop) weeks

The goal is to stage these changes incrementally without destabilizing current
GetVolumeForecast behavior.

## 1) No-Transaction Week Handling

### 1.1 Distinguish true zero vs missing week

Current evaluation may use epsilon fill for missing actual alignment weeks.
For modeling, explicitly separate:

- true_zero_week: merchant active but no transactions occurred
- missing_week: data unavailable or not yet landed

Planned fields:

- weekly_total_proc_value
- is_missing_week
- is_true_zero_week

### 1.2 Two-stage forecasting for intermittent activity

Use a hurdle-style setup:

1. Activity model: predict probability of active week, P(active)
2. Amount model: predict E(amount | active)
3. Final weekly expectation: P(active) * E(amount | active)

Benefits:

- handles intermittent merchants better than single-value regression
- avoids forcing SARIMA to explain many structural zeros

### 1.3 Recency and gap features

Add sparse-activity context features:

- weeks_since_last_txn
- active_weeks_last_4
- active_weeks_last_8
- active_weeks_last_13
- rolling_nonzero_ratio

These can be used in exogenous SARIMAX mode and for calibration gating.

### 1.4 Sparse-series fallback policy

When recent activity is very low, switch to intermittent-demand fallback
instead of standard SARIMA-only extrapolation.

Candidate trigger examples:

- active_week_ratio_context < 0.5
- matched_calibration_points < 3

Candidate fallback families:

- Croston-style
- TSB-style
- flat baseline with uncertainty inflation

## 2) Anomalous Week Handling

### 2.1 Robust anomaly detection

Use merchant-level robust detectors:

- Median/MAD z-score
- IQR outlier rule
- optional peer-relative deviation vs composite neighbors

Flag both positive spikes and sharp drops.

### 2.2 Training-time winsorization with flags

Do not silently discard outliers. Instead:

- cap extreme training points to robust bounds (for fitting stability)
- preserve original values in diagnostics
- include anomaly indicator features

Planned fields:

- was_anomaly
- anomaly_type (spike/drop)
- anomaly_magnitude

### 2.3 Robust calibration objective

Current calibration is RMSE-based with candidate mode selection.
Future enhancement:

- robust loss for calibration fitting (for example Huber)
- quantile-aware calibration option for skewed merchants

This reduces the influence of one or two extreme onboarding weeks.

## 3) Confidence Interval and Risk Controls

### 3.1 Context-quality-dependent uncertainty

Inflate confidence interval width when:

- sparse recent activity
- many missing weeks
- high anomaly density

### 3.2 Segment-specific calibration defaults

Define policy by merchant scale and stability cohort:

- low volume intermittent
- medium volume mixed
- high volume stable

Allow different preferred calibration modes by segment.

## 4) Evaluation and Monitoring Enhancements

### 4.1 Metric slicing

Report separate metrics for:

- observed active weeks only
- zero-actual weeks
- anomaly-flagged weeks
- sparse vs non-sparse merchants

### 4.2 Calibration mode diagnostics

Track per merchant:

- selected mode
- candidate RMSE values
- improvement vs raw

### 4.3 Cost-aware metrics

Add weighted metrics where active weeks carry more weight than no-transaction
weeks if business impact is higher on active volume weeks.

## 5) Suggested Implementation Order

1. Add missing/zero week semantics + recency features.
2. Add anomaly flags and training-time winsorization.
3. Add calibration diagnostics to integration outputs.
4. Add two-stage activity/amount forecasting path.
5. Add intermittent-demand fallback for sparse merchants.
6. Add robust calibration objective options.

## 6) Current Service State Reference

Current GetVolumeForecast already includes guarded calibration mode selection:

- guarded_linear
- guarded_scale
- guarded_shift
- skipped_no_improvement and other skip states

This backlog extends that foundation rather than replacing it.
