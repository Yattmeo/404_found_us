# Monte Carlo Profit Forecast Changes

This document describes what should be changed to current files:
- `ml_service/modules/profit_forecast/service.py`
- `ml_service/modules/profit_forecast/models.py`

## 1) Cost Sampling Logic (service.py)

### Before
- Cost percentage samples were drawn from a single Gaussian distribution:
  - `cost_samples = Normal(cost_pct_mid, sigma_cost)`
- Then clamped at zero.

### After
- Added `_sample_cost_pct_soft_guardrail(...)` and switched cost sampling to a CI-shaped soft guardrail approach:
  - Central mass inside CI via truncated normal.
  - Explicit lower and upper tails via exponential sampling.
  - Still enforces `cost_pct >= 0`.

### Why this was changed
- Better represents tail risk outside calibrated conformal intervals.
- Avoids over-reliance on symmetric Gaussian assumptions for cost distributions.


## 2) `_simulate_profit_month` Signature + Inputs (service.py)

### Before
- `_simulate_profit_month(...)` did not accept per-month cost CI bounds.

### After
- Added optional inputs:
  - `cost_pct_ci_lower: float | None = None`
  - `cost_pct_ci_upper: float | None = None`
- These bounds are used by the new soft-guardrail sampler.

### Why this was changed
- Allows month-specific uncertainty shaping instead of only half-width-based Gaussian spread.


## 3) Per-Month Cost CI Wiring (service.py)

### Before
- Loop computed `cost_hw` and passed only midpoint + half-width to simulator.

### After
- Loop now computes and passes:
  - `cost_ci_lower`
  - `cost_ci_upper`
  - `cost_hw`
- Falls back to midpoint +/- global half-width when per-month bounds are missing.

### Why this was changed
- Makes each month's sampling consistent with available CI information.


## 4) Break-Even Fee Rate Robustness (service.py)

### Before
- `worst_cost_upper` was derived only from `cost_pct_mid + global_half_width`.

### After
- `worst_cost_upper` now prefers per-month `proc_cost_pct_ci_upper`.
- Falls back to `proc_cost_pct_mid + global_half_width` if CI upper is missing.

### Why this was changed
- Uses the best available uncertainty bound per month.
- Improves robustness when per-month CI fields are partially missing.


## 5) Metadata Enrichment (models.py + service.py)

### Before
- `SimulationMetadata` ended at `correlation_assumed`.

### After
- Added fields:
  - `cost_sampling_strategy`
  - `cost_ci_tail_probability`
  - `cost_ci_hard_clip`
- `service.py` now populates these fields in response metadata.

### Why this was changed
- Improves transparency and auditability of simulation assumptions.
- Makes the response explicit about tail handling behavior.


## 6) Imports and Dependencies (service.py)

### Before
- `norm` was imported inside `_simulate_profit_month`.
- No use of `truncnorm`.

### After
- Top-level import: `from scipy.stats import norm, truncnorm`.
- `truncnorm` is used for bounded central CI sampling in cost simulation.

### Why this was changed
- Supports the new CI-shaped cost sampling implementation.


## Functional Summary
- No endpoint contract changes at request level.
- Response structure is backward compatible with additive metadata fields.
- Profit simulation behavior is intentionally more tail-aware and risk-sensitive than current production.
