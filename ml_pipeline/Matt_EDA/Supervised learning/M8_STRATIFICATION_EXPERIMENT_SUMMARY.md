# M8 Stratification Experiment Summary

## Scope

This note summarizes the volatility / risk stratification experiments explored around `m8_pipeline_c6.ipynb` for the M8 / M9 / M10 conformal interval pipeline.

Primary objective:

- reduce overall interval conservatism
- give stable merchants tighter intervals
- push wider penalties onto genuinely volatile merchants
- keep joint coverage at or above the 90% target

Baseline for comparison:

- existing pool-local conformal intervals from the M8 / M9 / M10 pipeline
- most important deployment benchmark was M9 pool-local conformal, because it was the strongest practical interval baseline


## Dataset / Split Context

- Context length: `CONTEXT_LEN = 6`
- Horizon length: `HORIZON_LEN = 3`
- Merchant-level split: 60% train, 20% calibration/validate, 20% test
- Final conformal evaluation used:
  - `train_ci`: train merchants, horizon year before calibration year
  - `cal_ci`: validate merchants, calibration year
  - `test_ci`: test merchants, final held-out year

Important point:

- Earlier volatility stratification in the SVD notebook was not useful because `CONTEXT_LEN = 1`, which made context volatility nearly degenerate.
- In `m8_pipeline_c6.ipynb`, `CONTEXT_LEN = 6`, so volatility stratification became meaningful enough to test seriously.


## Experiment Timeline

### 1. Two-Bucket CoV Stratification

First idea:

- use context CoV as the volatility signal
- split merchants into `Low` and `High` volatility buckets
- estimate separate conformal widths per bucket

What it was trying to do:

- protect stable merchants from being over-covered by residuals coming from more volatile merchants

Observed issue:

- the binary split was too coarse
- it did not separate moderate merchants from genuinely unstable tail merchants very well
- this motivated trying more than two buckets


### 2. Multi-Bucket CoV Stratification

Next step:

- generalize the binary setup to 3 to 5 CoV buckets
- estimate conformal widths separately per bucket

What changed:

- low / mid / high style bins were introduced
- bucket-specific quantiles replaced the single global quantile

Observed issue:

- equal-size multi-bucket schemes often widened the overall average interval
- too many merchants were pushed into medium or high-width groups
- the design goal was directionally right, but the bucket geometry was not aligned with the data


### 3. Auto-Selected Quantile Buckets

Next step:

- automatically choose the number of buckets by minimizing average width subject to meeting coverage

Why this was tried:

- avoid hand-picking `2`, `3`, or `4` buckets without evidence

Observed issue:

- auto-selection over equal-size quantile buckets still did not reliably reduce conservatism overall
- it improved some buckets locally but often made the global mean width worse


### 4. Asymmetric Tail-Aware CoV Buckets

Next step:

- stop using equal-size bucketing
- define asymmetric percentile schemes such as `50/85`, `60/90`, `70/90`, `70/95`
- keep a large stable bucket and isolate only the volatile tail

What changed:

- bucket edges were based on percentiles of calibration CoV
- only the most volatile minority was supposed to receive the largest widths
- bucket widths were forced to be monotone from stable to volatile

Why this mattered:

- volatility in this problem behaves more like a tail phenomenon than a symmetric segmentation problem


### 5. Effective Half-Width Fix

Important measurement fix:

- interval comparison was corrected to use effective half-width after lower-bound clipping at zero
- this replaced misleading comparisons against raw conformal radii

Why this mattered:

- before this correction, some stratified schemes looked worse than they really were
- after the fix, the best CoV-based stratified scheme showed a small but real improvement


### 6. Best CoV-Only Result

Best observed CoV-only scheme:

- `low-mid-high_70_90`

Representative result after effective-width correction:

- M8:
  - joint coverage about `0.903`
  - average half-width about `3.8712`
  - baseline pool-local half-width about `4.0225`
- M9:
  - joint coverage about `0.902`
  - average half-width about `3.8809`
  - baseline pool-local half-width about `4.0183`
- M10:
  - joint coverage about `0.902`
  - average half-width about `3.8809`
  - baseline pool-local half-width about `4.0183`

Interpretation:

- this was the clearest success among all stratification attempts
- the gain was modest, but it was real
- it matched the desired behavior:
  - stable merchants got much tighter widths
  - volatile merchants took much wider widths
  - overall average width came down slightly while coverage remained above target

Representative bucket widths for that run:

- low volatility: about `2.964`
- mid volatility: about `7.407`
- high volatility: about `11.044`


## Residual-Aware Follow-Up Attempts

After the CoV-only version showed a small improvement, several more ambitious variants were tested.


### 7. Leak-Free Holdout Selection

Change:

- scheme selection was moved off final test and onto a calibration holdout split

Why this was added:

- avoid selecting a volatility scheme directly on test results
- separate model design from final evaluation

Outcome:

- conceptually correct and worth keeping as a validation principle
- however, holdout wins did not always survive the final test guard


### 8. Residual-Aware Linear Risk Model

Change:

- instead of bucketing directly on CoV, build a small risk model using context-derived features:
  - context CoV
  - range / mean
  - slope / mean
  - last-step jump / mean
- train the model to predict log residual size

Why this was tried:

- CoV alone might be too weak or too blunt as a risk signal
- richer context dynamics might separate stable and unstable merchants better

Outcome:

- promising on holdout
- did not beat the practical deployment guard on final test
- final deployed state reverted to the baseline pool-local interval


### 9. Non-Linear Risk Model + Cross-Fitted Residual Targets

Change:

- replace the linear residual-risk model with a boosted-tree regressor
- train it on cross-fitted out-of-fold residuals from `train_ci`

Why this was tried:

- reduce optimism from using a single calibration split
- allow non-linear interactions in the risk score

Observed behavior:

- stronger holdout results than the simpler linear model
- best holdout scheme was often `low-mid-high_60_90`
- holdout improvements were materially larger than the CoV-only gain
- but the final deployment guard still rejected the scheme on test

Key interpretation:

- better model flexibility improved holdout fit
- but the gain did not generalize reliably to the final test year


### 10. Peer-Pool Composition Features

Change:

- add peer-pool structure into the risk features, including:
  - flat-pool vs k-NN-pool gap
  - context mean vs k-NN-pool gap

Why this was tried:

- some risk may come from how unusual the merchant is relative to peers, not just from its own context volatility

Outcome:

- technically reasonable extension
- still failed the final practical-gain test


### 11. Horizon-Specific Risk Models

Change:

- fit separate residual-risk models for `t+1`, `t+2`, and `t+3`
- aggregate them into a scenario-level risk score

Why this was tried:

- stability can differ by forecast horizon
- the same merchant may be easy at `t+1` and harder at `t+3`

Outcome:

- increased modeling sophistication
- did not produce a test-approved deployed improvement


### 12. Continuous Width Adjustment Instead of Hard Buckets

Change:

- move from stepwise bucket widths to a monotone continuous width curve over the learned risk score
- percentile schemes became knot placements rather than pure bucket boundaries

Why this was tried:

- hard buckets may overreact to arbitrary edge placements
- a continuous rule should be smoother and potentially more robust

Outcome:

- still failed the final deployment guard
- final notebook state reverted to the baseline pool-local conformal interval


## What Worked Best

Best practical result observed across all stratification work:

- the simpler CoV-only asymmetric stratification with effective-width accounting
- especially the `low-mid-high_70_90` scheme

Why it is still the strongest result:

- it produced a real, interpretable improvement on the final evaluation
- it was easier to explain than the more complex learned-risk approaches
- later residual-aware methods tended to look better on holdout than they did on final test


## What Did Not Generalize Reliably

The following families were explored but did not survive the final practical-gain guard:

- linear residual-risk models
- boosted-tree residual-risk models
- cross-fitted residual-risk targets
- peer-pool composition risk features
- horizon-specific risk models
- continuous width adjustment rules

Common pattern:

- they often improved calibration-holdout width while maintaining coverage
- but the advantage did not remain strong enough on the final held-out test year


## Main Lessons Learned

1. Measurement details matter.

- correcting raw radius comparisons to effective half-width after clipping was essential
- without this, the better CoV-only scheme would have looked worse than it really was

2. Simpler stratification generalized better than more complex learned-risk methods.

- the CoV-only asymmetric scheme was modest but robust
- more flexible methods increased apparent holdout gains but not test robustness

3. The problem appears to involve temporal drift, not just poor risk scoring.

- later schemes frequently succeeded on calibration holdout and failed at the final test guard
- that suggests the rank ordering of merchant risk is not fully stable across years

4. Practical-gain rules were useful.

- they prevented the notebook from deploying stratified schemes that were interesting analytically but not actually better in final evaluation


## Recommended Default Going Forward

If the goal is a practical notebook result today, the best default is:

- revert to the simpler CoV-only asymmetric stratification
- use effective half-width accounting
- prefer the `low-mid-high_70_90` style scheme that previously showed the small final improvement

If future work continues, the most promising next direction is not necessarily more model complexity. It is more likely to be:

- analyzing why holdout and final test merchant risk rankings drift across years
- adding regime or year-sensitive signals
- testing whether the calibration year is structurally different from the final test year
