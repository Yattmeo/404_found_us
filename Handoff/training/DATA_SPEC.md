# Training Data Specification

**System:** GetCostForecast (proc\_cost) & GetTPVForecast  
**Last Updated:** April 2026  
**Audience:** Data engineering team responsible for retraining the ML service models

---

## 1. Overview

Both forecasting models are trained from a single monthly-aggregated CSV per MCC
(Merchant Category Code). Raw transaction data is first aggregated into this format
using `prepare_data.py`, then each training script consumes it independently.

```
Raw transaction data
        │
        │  (apply cost_type CSV — assigns cost_type_ID and proc_cost per transaction)
        │
        ▼
Annotated transaction CSV
        │
        ▼
 prepare_data.py
        │
        ├──► {mcc}_monthly_v2.csv ──► proc_cost/train.py ──► ml_service/artifacts/proc_cost/
        │
        └──► {mcc}_monthly_v2.csv ──► tpv/train.py       ──► ml_service/artifacts/tpv/
```

---

## 2. Cost Type Reference CSV

> **The JSON fee schedules (`cost_structure/*.JSON`) and the generated
> `cost_type_id.csv` are subject to change** as fee programs are updated.
> Whenever the JSON files change, regenerate `cost_type_id.csv` and re-run the
> full data preparation and training pipeline (see Section 5). See Section 2.6
> for a checklist of everything that must be updated.

The cost type reference CSV maps each cost-type combination to a numeric `cost_type_ID`
and its associated fee rates. It must be generated from the JSON files in
`cost_structure/` and then applied to raw transaction data to add the
`cost_type_ID` and `proc_cost` columns required by `prepare_data.py`.

### 2.1 Source Files

| File | Contents |
|------|----------|
| `cost_structure/visa_Card.JSON` | Visa interchange (card-level) rates: percent and fixed fee per card type, fee program, and MCC |
| `cost_structure/visa_Network.JSON` | Visa network assessment and processing fees per card type |
| `cost_structure/masterCard_Card.JSON` | Mastercard interchange rates per card type, fee program, and MCC |
| `cost_structure/masterCard_Network.JSON` | Mastercard network assessment fees (flat rate + large-transaction surcharge) |

### 2.2 Output CSV Format

The generated cost type CSV must have exactly the following columns:

| Column | Type | Description |
|--------|------|-------------|
| `cost_type_ID` | int | Sequential integer ID starting at 1, unique per row |
| `card_network` | str | `Visa` or `Mastercard` |
| `card_brand` | str | Card tier: `Credit`, `Debit`, `Prepaid`, or `Super Premium Credit` |
| `fee_program` | str | `Small Ticket Fee Program (All)` or `Industry Fee Program (All)` |
| `min_transaction_amt` | float | Lower bound (inclusive) of the transaction amount range (dollars) |
| `max_transaction_amt` | float | Upper bound (inclusive) of the transaction amount range (dollars) |
| `mcc` | int or `N/A` | MCC this row applies to; `N/A` for Small Ticket rows (apply to all MCCs) |
| `card_fee_percent` | float | Card interchange percent rate (e.g. `1.60` for 1.60%, **not** `0.0160`) |
| `card_fee_dollars` | float | Card interchange fixed fee in dollars (e.g. `0.15`) |
| `network_fee_percent` | float | Network assessment percent rate (same units as card_fee_percent) |
| `network_fee_dollars` | float | Network assessment fixed fee in dollars |
| `subtotal_fee_percent` | float | `card_fee_percent + network_fee_percent` |
| `subtotal_fee_dollars` | float | `card_fee_dollars + network_fee_dollars` |

> **Important:** All `_percent` columns store the rate as a plain percentage value
> (e.g. `1.73`, **not** `0.0173`). The `%` and `$` symbol prefixes in the sample
> CSV are display formatting only and must be stripped when reading programmatically.

### 2.3 Generation Rules

#### Card fees (`*_Card.JSON`)

Each JSON entry defines `percent_rate` and `fixed_rate` for a `(card_type, product, mcc)` combination:

- `product` maps to `fee_program` — the two programs are:
  - `"Small Ticket Fee Program (All)"` — amount range `[0, 5]`, applies to all MCCs (`mcc: null`)
  - `"Industry Fee Program (All)"` — amount range `[5, ∞]`, applies to a specific MCC
- `mcc: null` in the JSON → `mcc = N/A` in the output CSV
- Some Visa entries include a `"min_fee"` field; this is informational and does not affect the stored percent/fixed rates

Amount sub-tiers exist for certain (card_network, card_brand, mcc) combinations and are
already enumerated as separate rows in the JSON (each with its own `percent_rate` and `fixed_rate`).
Each such JSON entry becomes a separate row in the cost_type CSV with its own `cost_type_ID`.

#### Network fees (`*_Network.JSON`)

Visa network fees differ by card type (Debit vs Credit). Sum all applicable network fee
entries for the card type to get `network_fee_percent` and `network_fee_dollars`:

| Visa card type | network_fee_percent | network_fee_dollars |
|---------------|---------------------|---------------------|
| Debit / Prepaid | 0.13% | $0.0155 (APF) |
| Credit / Super Premium Credit | 0.14% | $0.0195 (APF) |

Mastercard network fees apply universally; the large-transaction surcharge (`+0.01%` for
amounts ≥ $1,000) is handled by creating separate amount-tier rows:

| Mastercard amount range | network_fee_percent | network_fee_dollars |
|------------------------|---------------------|---------------------|
| < $1,000 | 0.13% | $0.025 |
| ≥ $1,000 | 0.14% | $0.025 |

#### ID assignment

Assign `cost_type_ID` as a sequential integer (starting at 1) after sorting rows by:
`card_network` → `fee_program` → `mcc` → `card_brand` → `min_transaction_amt`.
The current reference CSV uses IDs 1–61; maintain this ordering convention when regenerating (new rows are appended at the end with the next available IDs).

### 2.4 Applying the Cost Type CSV to Raw Transactions

For each transaction, match a single `cost_type_ID` row using these rules in order:

1. **card_network**: match `card_brand` column in the transaction to `card_network` in the
   cost_type CSV. Values are `Mastercard` or `Visa` (case-sensitive).

2. **card_brand** (tier): normalise the transaction's `card_type` string to the cost_type
   CSV's `card_brand` field:

   | Transaction `card_type` (examples) | Cost-type `card_brand` |
   |-------------------------------------|------------------------|
   | `debit (prepaid)`, `prepaid` | `Prepaid` |
   | `debit` | `Debit` |
   | `credit` | `Credit` |
   | `super premium credit`, `world elite` | `Super Premium Credit` |

3. **fee_program**: if `amount ≤ 5` → `Small Ticket Fee Program (All)`;
   if `amount > 5` → `Industry Fee Program (All)`.

4. **mcc**: for Industry rows, match the transaction's `mcc` to the cost_type row's `mcc`.
   Small Ticket rows (`mcc = N/A`) apply to any MCC.

5. **amount range**: `min_transaction_amt ≤ amount ≤ max_transaction_amt`.

If no row matches (e.g. an unsupported MCC), exclude that transaction or flag it.

### 2.5 Computing `proc_cost`

Once the matching `cost_type_ID` row is found, compute:

```
proc_cost = amount × subtotal_fee_percent + subtotal_fee_dollars
```

where `subtotal_fee_percent` is the stored value (e.g. `1.73`, **not** `0.0173`).

Example (sample transaction — ID 31, Mastercard Prepaid, MCC 5499, amount $77):
```
proc_cost = 77.0 × 1.73 + 0.18 = 133.39
```

This means `proc_cost / amount = subtotal_fee_percent ≈ 1.73`, so `avg_proc_cost_pct`
in the monthly CSV represents the **average fee rate in percent units** (typical range
1.0–3.0 for the supported MCCs).

### 2.6 Change Propagation Checklist

When `cost_structure/*.JSON` files are updated (new fee programs, new MCCs, revised rates,
or changed amount tiers), follow this checklist in order:

| # | Action | Detail |
|---|--------|--------|
| 1 | **Regenerate `cost_type_id.csv`** | Apply the generation rules in Section 2.3. Save to `cost_structure/cost_type_id.csv`. Note the new row count N. |
| 2 | **Re-annotate raw transactions** | Re-apply the updated CSV to all raw transaction data (Section 2.4) to recompute `cost_type_ID` and `proc_cost` for every transaction. Old annotated files are invalid. |
| 3 | **Re-run `prepare_data.py`** | Regenerates all `{mcc}_monthly_v2.csv` files with the new N fingerprint columns. `prepare_data.py` reads N automatically from the CSV — no code change needed. |
| 4 | **Retrain all models** | Run `proc_cost/train.py` and `tpv/train.py` for all MCCs. Existing artifacts are incompatible with a different N and must be overwritten. |
| 5 | **Verify hot-reload** | Confirm the ml-service reloads the new artifacts within 60 seconds (`docker logs ml-service --tail 20`). |

> **If only fee rates changed** (but N stays the same and no existing `cost_type_ID` is
> reassigned), steps 1–4 are still required because `proc_cost` values will differ, making
> old monthly CSVs and artifacts stale.

> **If N changes** (rows added or removed), the monthly CSVs and all trained artifacts are
> structurally incompatible with the old versions and must be fully regenerated.

---

## 3. Raw Transaction Input

### 3.1 File

| Property | Value |
|----------|-------|
| Default path | `training/data/processed_transactions_4mcc.csv` |
| Format | UTF-8 CSV, one row per transaction |

### 3.2 Column Requirements

`prepare_data.py` reads only six columns. The remaining columns in the raw file are
consumed upstream (during cost_type CSV application) or not used at all.

#### Required by `prepare_data.py`

| Column | Type | Description |
|--------|------|-------------|
| `merchant_id` | int | Merchant identifier (must be stable across months) |
| `date` | datetime string | Transaction date — any format parseable by pandas (e.g. `2010-01-01 00:09:00`). Also accepted as `transaction_date`. |
| `amount` | float | Transaction amount in dollars (must be > 0) |
| `mcc` | int | Merchant Category Code — used to filter transactions per training run |
| `cost_type_ID` | int | Cost-type identifier (1–N); **added by the cost_type CSV application step**, not present in the original raw transaction data |
| `proc_cost` | float | Processing cost computed from the matched cost_type row; **added by the cost_type CSV application step** |

#### Required upstream (cost_type CSV application only, not read by `prepare_data.py`)

| Column | Type | Description |
|--------|------|-------------|
| `card_brand` | str | Card network (`Mastercard` or `Visa`) — used to match `card_network` in cost_type CSV |
| `card_type` | str | Card tier string (e.g. `debit (prepaid)`, `credit`) — normalised to match `card_brand` in cost_type CSV |

#### Not used at any stage of training

| Column | Notes |
|--------|-------|
| `transaction_id` | Not read by any training script; may be retained for audit trail |
| `year` | Redundant — `prepare_data.py` derives year from the `date` column |
| `week` | Not consumed by any training script |

### 3.3 Minimum Data Requirements

| Requirement | Minimum |
|-------------|---------|
| MCCs with data | 1 (can train per-MCC independently) |
| Merchants per MCC | ≥ 30 (need enough for 60/20/20 split + conformal) |
| Months of history per merchant | ≥ 6 (for context\_len=6 scenarios) |
| Distinct years in dataset | ≥ 3 (need ≥ 2 horizon years for conformal calibration) |

---

## 4. Monthly Aggregated Input (`{mcc}_monthly_v2.csv`)

This is the file produced by `prepare_data.py` and consumed by both training scripts.

### 4.1 File Naming

```
training/data/{mcc}_monthly_v2.csv
```

One file per supported MCC. Supported MCCs: **4121, 5411, 5499, 5812**

### 4.2 Column Schema

#### Identity columns

| Column | Type | Description |
|--------|------|-------------|
| `merchant_id` | int | Merchant identifier |
| `year` | int | Calendar year (e.g. `2023`) |
| `month` | int | Calendar month, 1–12 |

#### Target columns

| Column | Type | Model | Description |
|--------|------|-------|-------------|
| `avg_proc_cost_pct` | float | proc\_cost | **Primary target.** Average fee rate for the month: `mean(proc_cost / amount)`. Equals approximately `subtotal_fee_percent` (in percent units, typical range **1.0–3.0** for supported MCCs). |
| `total_processing_value` | float | TPV | **Primary target.** Sum of `amount` across all transactions in the month (dollars). |

#### Statistical cost-percentage features

| Column | Type | Derivation |
|--------|------|------------|
| `std_proc_cost_pct` | float | `std(proc_cost / amount)` within the month |
| `median_proc_cost_pct` | float | `median(proc_cost / amount)` within the month |
| `iqr_proc_cost_pct` | float | 75th percentile − 25th percentile of `proc_cost / amount` |

#### Transaction volume & amount features

| Column | Type | Derivation |
|--------|------|------------|
| `transaction_count` | int | Number of transactions in the month |
| `avg_transaction_value` | float | `mean(amount)` for the month |
| `std_txn_amount` | float | `std(amount)` for the month |
| `median_txn_amount` | float | `median(amount)` for the month |
| `n_unique_cost_types` | int | Number of distinct `cost_type_ID` values seen |

#### Cost-type fingerprint columns

| Column | Type | Derivation |
|--------|------|------------|
| `cost_type_1_pct` … `cost_type_N_pct` | float | Fraction of transactions (by row count) with that `cost_type_ID`. Each in [0, 1]. Columns for IDs not seen in a month are `0.0`. **N equals the number of rows in `cost_structure/cost_type_id.csv`** (currently 61). If the CSV changes, N changes and all downstream artifacts must be retrained. |

> **What is `cost_type_ID`?**  
> Each transaction is assigned a cost-type ID during the pre-processing step (see Section 2).
> The ID encodes the combination of card network, card tier, fee program, MCC, and transaction
> amount range that determines the applicable interchange and network fee rates. The distribution
> of cost types across a merchant's transactions — the "cost-type fingerprint" — is a strong
> predictor of their average processing cost and is used for kNN peer-group matching during training.
>
> **`prepare_data.py` reads `COST_TYPE_IDS` directly from `cost_structure/cost_type_id.csv` at
> runtime**, so the fingerprint column set automatically reflects the current CSV without a code
> change. However, a change in N invalidates existing monthly CSVs and trained artifacts — a full
> retrain is required (see Section 2.6).

#### Derived column (TPV model only)

| Column | Type | Derivation |
|--------|------|------------|
| `log_tpv` | float | `log1p(total_processing_value)` — **computed automatically** by `tpv/train.py` at load time. Do NOT include this column in the CSV; it will be overwritten if present. |

### 4.3 Full Column Order (reference)

```
merchant_id, year, month,
avg_proc_cost_pct, std_proc_cost_pct, median_proc_cost_pct, iqr_proc_cost_pct,
total_processing_value, transaction_count, avg_transaction_value,
std_txn_amount, median_txn_amount, n_unique_cost_types,
cost_type_1_pct, cost_type_2_pct, ..., cost_type_N_pct
```

Total columns: **3 + 4 + 6 + N** where N = number of rows in `cost_structure/cost_type_id.csv` (currently 61, giving **74** columns).

### 4.4 Data Quality Rules

| Rule | Detail |
|------|--------|
| No duplicate `(merchant_id, year, month)` tuples | Each merchant has at most one row per month |
| `avg_proc_cost_pct` must not be NaN | Rows where `proc_cost / amount` cannot be computed are dropped by `prepare_data.py` |
| `total_processing_value` must be > 0 | Months with zero TPV should be excluded |
| `merchant_id` must be stable | The same merchant must use the same ID across all months |
| `year` and `month` must be integers | No fractional values |
| Months must be consecutive for at least 6 months per merchant | Training generates sliding-window scenarios; gaps in months cause fewer scenarios |

---

## 5. Workflow

### Step 0: Environment setup

```bash
cd Handoff/training
pip install -r requirements.txt
```

### Step 1: Generate the cost type CSV

This is a one-time step (or repeated whenever `cost_structure/` JSON files are updated).
No script is provided — generate the CSV using the rules in Section 2:

1. For each JSON entry in `visa_Card.JSON` and `masterCard_Card.JSON`, combine with the
   corresponding network fees from `visa_Network.JSON` / `masterCard_Network.JSON`.
2. Compute `subtotal_fee_percent = card_fee_percent + network_fee_percent` and
   `subtotal_fee_dollars = card_fee_dollars + network_fee_dollars`.
3. Assign sequential `cost_type_ID` values (sort by network → program → mcc → card_brand → amount tier).
4. Save as `cost_structure/cost_type_id.csv` with the exact column names from Section 2.2.

The current reference file is provided at `cost_structure/cost_type_id.csv` (currently 61 rows; this count will change if the fee schedule changes — see Section 2.6).

### Step 2: Apply the cost type CSV to raw transaction data

For each transaction in the raw file, match a `cost_type_ID` using the lookup logic in
Section 2.4, then compute `proc_cost` using the formula in Section 2.5. Add both as new
columns to produce the annotated transaction CSV.

Input: raw transaction file (columns: `transaction_id`, `merchant_id`, `date`, `amount`,
`mcc`, `card_brand`, `card_type`, `year`, `week`)

Output: annotated file with two additional columns: `cost_type_ID`, `proc_cost`

Save as: `training/data/processed_transactions_4mcc.csv`

### Step 3: Aggregate to monthly training data

```bash
python prepare_data.py \
    --input data/processed_transactions_4mcc.csv \
    --output-dir data
# Produces: data/4121_monthly_v2.csv, data/5411_monthly_v2.csv, etc.
```

To process a single MCC only:
```bash
python prepare_data.py --mcc 5411
```

### Step 4: Train proc\_cost model (run per MCC)

```bash
cd proc_cost
python train.py --mcc 5411 --data-path ../data/5411_monthly_v2.csv
python train.py --mcc 5499 --data-path ../data/5499_monthly_v2.csv
python train.py --mcc 4121 --data-path ../data/4121_monthly_v2.csv
python train.py --mcc 5812 --data-path ../data/5812_monthly_v2.csv
```

Artifacts are written to:  
`ml_service/artifacts/proc_cost/{mcc}/{ctx_len}/`

### Step 5: Train TPV model (run per MCC)

```bash
cd ../tpv
python train.py --mcc 5411 --data-path ../data/5411_monthly_v2.csv
python train.py --mcc 5499 --data-path ../data/5499_monthly_v2.csv
python train.py --mcc 4121 --data-path ../data/4121_monthly_v2.csv
python train.py --mcc 5812 --data-path ../data/5812_monthly_v2.csv
```

Artifacts are written to:  
`ml_service/artifacts/tpv/{mcc}/{ctx_len}/`

### Step 6: Hot-reload (no container restart needed)

The ml-service polls `config_snapshot.json` every 60 seconds. When its `mtime` changes
(which happens whenever training writes new artifacts), the service automatically reloads
the in-memory models. No container restart is required.

To verify the reload:
```bash
docker logs ml-service --tail 20
# Look for: "Reloading proc_cost artifacts for mcc=5411 ctx_len=3"
```

---

## 6. Output Artifacts

Each `(mcc, ctx_len)` pair produces a directory with these files:

| File | Description |
|------|-------------|
| `models.pkl` | `List[HuberRegressor]` — one model per forecast horizon (3 total) |
| `scaler.pkl` | `StandardScaler` fitted on the training feature matrix |
| `cal_residuals.pkl` | `Dict[int, List[float]]` — merchant\_id → calibration residuals for per-merchant conformal intervals |
| `global_q90.pkl` | `float` — fallback q90 when merchant-level residuals are unavailable |
| `risk_models.pkl` | `List[GradientBoostingRegressor]` — risk score models for stratified conformal |
| `strat_knot_x.pkl` | `np.ndarray` — stratification spline knots (optional, absent if stratification was not beneficial) |
| `strat_q_vals.pkl` | `np.ndarray` — stratification quantile values per knot (optional) |
| `config_snapshot.json` | Training metadata: MCC, context length, window, coverage target, model parameters, training date. Triggers hot-reload on change. |

Supported context lengths: **1, 3, 6** (months of history provided by the merchant).

---

## 7. Model Hyperparameters (reference)

### proc\_cost model

| Parameter | Value |
|-----------|-------|
| Architecture | HuberRegressor (point forecast) + GBR (risk/uncertainty) |
| Huber epsilon | 1.35 |
| Huber max\_iter | 500 |
| Features (point model) | 7 (context mean/std/momentum, kNN pool mean, intra-std, log-txn-count, mean-median gap) |
| GBR n\_estimators | 120 |
| GBR learning\_rate | 0.05 |
| GBR max\_depth | 2 |
| Merchant split | 60% train / 20% val / 20% test (merchant-level, seed=42) |
| Conformal coverage target | 90% |

### TPV model

| Parameter | Value |
|-----------|-------|
| Architecture | HuberRegressor in log-space + GBR (risk/uncertainty) |
| Target transformation | `log1p(total_processing_value)` → back-transformed with `expm1` |
| Features (point model) | 11 (context mean/std/momentum, pool mean, txn amount std, log-txn-count, avg-median-txn gap, last month, log-avg-txn-val, momentum-tc, momentum-atv) |
| GBR n\_estimators | 120 |
| GBR learning\_rate | 0.05 |
| GBR max\_depth | 2 |
| Conformal space | Dollar-space residuals |
| Conformal coverage target | 90% |

---

## 8. Retraining Schedule

**Recommended cadence:** Monthly, after the previous month's transactions are finalized.

Suggested cron (host machine, run from `Handoff/training/`):

```cron
# 1st of each month at 02:00 — aggregate data then train all MCCs
0 2 1 * * cd /path/to/Handoff/training && \
  python prepare_data.py && \
  for mcc in 4121 5411 5499 5812; do \
    python proc_cost/train.py --mcc $mcc --data-path data/${mcc}_monthly_v2.csv && \
    python tpv/train.py --mcc $mcc --data-path data/${mcc}_monthly_v2.csv; \
  done
```

Training duration per MCC is typically 2–10 minutes depending on dataset size.
The ml-service hot-reloads artifacts within 60 seconds of completion.

---

## 9. Adding a New MCC

1. Ensure transactions for the new MCC exist in the annotated transaction CSV.
2. Verify the MCC has entries in the cost_type CSV (all four card networks/tiers); add rows to `cost_structure/cost_type_id.csv` and regenerate if needed (see Section 2).
3. Run `prepare_data.py --mcc <new_mcc>` to generate `data/<new_mcc>_monthly_v2.csv`.
4. Run both training scripts for the new MCC.
5. Add the MCC to the `SUPPORTED_MCCS` list in both `proc_cost/config.py` and `tpv/config.py`.
6. Add the MCC to `SUPPORTED_MCCS` in `ml_service/modules/cost_forecast/config.py` and `ml_service/modules/tpv_forecast/config.py`.
7. Rebuild the ml-service container (`docker compose build ml-service && docker compose up -d ml-service`).
