Method 6 is a calibrated persistence model, not a full tree model.

What Method 6 does:
1. For each horizon separately (t+1, t+2, t+3), it fits a robust linear model using only one input: current-month TCR.
2. It uses Huber regression (robust to outliers) on train data only.
3. Prediction form is:
$$
\hat y_{t+h} = a_h \cdot y_t + b_h
$$
where $a_h$ and $b_h$ are learned per horizon.

In your notebook, this is implemented in Cell 39 in prototype.ipynb.

Why it works:
1. Your baseline is persistence:
$$
\hat y_{t+h}^{\text{baseline}} = y_t
$$
That assumes slope $=1$ and intercept $=0$ for all horizons.
2. Method 6 relaxes that rigid assumption and learns the best slope/intercept from historical data.
3. The fitted slopes are very small (about 0.013 to 0.018) and intercepts are around 2.45 to 2.48.
4. That means the model learned strong mean reversion: future TCR tends to pull toward a stable level, instead of exactly following current TCR.
5. Huber makes this stable when TCR has heavy tails/outliers.

Why it beats baseline in your run:
1. Baseline overreacts to extreme current TCR values (because it copies $y_t$ directly).
2. Method 6 dampens that by shrinking predictions toward a learned central level.
3. Under strict leakage-safe split and unseen merchants, this lower-variance behavior generalizes better.
4. Result: Method 6 MAE (1.4620) is slightly better than baseline MAE (1.4706).

Intuition:
1. Baseline says “tomorrow looks exactly like today.”
2. Method 6 says “today matters, but mostly as a weak signal around a long-run level.”
3. In your data, that second statement is more accurate.