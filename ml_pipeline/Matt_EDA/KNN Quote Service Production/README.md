# KNN Quote Service Production

Production-oriented FastAPI service with two endpoints:

1. `/getQuote`
Purpose: match an onboarding merchant to 5 similar historical merchants and return each neighbor's next 3 months of historical `proc_cost_pct`.

2. `/getCompositeMerchant`
Purpose: match an onboarding merchant to 5 similar historical merchants and return a composite weekly feature history for downstream modeling.

## At A Glance

Stack:
- FastAPI
- pandas
- sklearn `NearestNeighbors`
- SQLAlchemy (external DB) or SQLite (local file) — selected at startup via env vars

Shared matching controls:
- `k = 5`
- Distance metric: Euclidean
- Repository filters: `mcc`, `card_types`

Repository schema required:
- `transactions`: `date`, `amount`, `merchant_id`, `mcc`, `card_brand`, `card_type`, `cost_type_ID`, `proc_cost`
- `cost_type_ref`: `cost_type_ID`

## Quick Start

1. Install dependencies

```bash
pip install -r requirements.txt
```

2. Start the service

```bash
uvicorn app:app --reload --port 8080
```

3. Check health

```bash
curl http://127.0.0.1:8080/health
```

4. Run tests before deploying

```bash
python -m pytest -q
```

## Environment Variables

Exactly one of the two database variables must be set. The service raises a `RuntimeError` at startup if neither is provided.

### Database (required — pick one)

| Variable | When to use | Example value |
|---|---|---|
| `DB_CONNECTION_STRING` | Any external / managed database (PostgreSQL, MySQL, MSSQL, …) | `postgresql://user:pass@host:5432/dbname` |
| `TRANSACTIONS_AND_COST_TYPE_DB_PATH` | Local SQLite file mounted into the container | `/data/merchant_quotes.sqlite` |

`DB_CONNECTION_STRING` takes priority. If both are set, `TRANSACTIONS_AND_COST_TYPE_DB_PATH` is ignored.

The target database must expose two tables:
- `transactions`: `transaction_id`, `date`, `amount`, `merchant_id`, `mcc`, `card_brand`, `card_type`, `cost_type_ID`, `proc_cost`
- `cost_type_ref`: `cost_type_ID`

### Optional

| Variable | Purpose | Default |
|---|---|---|
| `PROC_COST_SERVICE_URL` | External processing-cost enrichment URL used when onboarding data lacks `proc_cost` | Not set (falls back to local heuristic) |

## Endpoint Comparison

| Endpoint | Main job | Input mode | Output grain |
|---|---|---|---|
| `/getQuote` | return 3-month analog cost paths | dataframe or metrics-only | 5 neighbor forecasts |
| `/getCompositeMerchant` | return composite weekly feature history | dataframe only | weekly multi-year series |

## Endpoint 1: getQuote

Path: `/getQuote`  
Method: `POST`

### What It Does

- Builds a query feature vector for the onboarding merchant.
- Matches it to 5 similar historical merchant cases.
- Looks up each matched merchant's next 3 months of historical `proc_cost_pct`.

### Input

```json
{
  "onboarding_merchant_txn_df": [
    {
      "transaction_date": "2019-06-01",
      "amount": 52.1,
      "cost_type_ID": 2,
      "card_type": "visa"
    }
  ],
  "avg_monthly_txn_count": 500,
  "avg_monthly_txn_value": 48.0,
  "mcc": 5411,
  "card_types": ["visa"],
  "as_of_date": "2019-06-30T00:00:00"
}
```

### Input Rules

- `mcc` is required.
- `card_types` defaults to `["both"]` if omitted or empty.
- `onboarding_merchant_txn_df` is optional.
- If `onboarding_merchant_txn_df` is omitted, both `avg_monthly_txn_count` and `avg_monthly_txn_value` are required.
- If `as_of_date` is omitted in dataframe mode, the latest month in the onboarding dataframe is used.

Recommended onboarding dataframe fields:
- `transaction_date` or `date`
- `amount`
- `cost_type_ID`
- `card_type` optional
- `proc_cost` optional

### Matching Logic

Reference pool:
- Load historical transactions filtered by `mcc` and `card_types`.
- Build monthly merchant features:
  - `pct_ct_*`
  - `total_transactions`
  - `avg_amount`
  - `proc_cost_pct`
- Build month-specific merchant cases.
- Keep only cases with a full 3-month future horizon.

Query vector:
- Dataframe mode:
  - use `pct_ct_* + total_transactions + avg_amount`
- Metrics-only mode:
  - use `total_transactions + avg_amount`
  - ignore `pct_ct_*`

Neighbor selection:
- Fit `NearestNeighbors`
- Use Euclidean distance
- Return 5 nearest cases

Forecast generation:
- For each matched case, look up that merchant's `proc_cost_pct` in months `+1`, `+2`, `+3`

### Output

```json
{
  "neighbor_forecasts": [
    {
      "merchant_id": 11429,
      "forecast_proc_cost_pct_3m": [0.0211, 0.0208, 0.0215]
    }
  ],
  "context_len_wk": 4,
  "horizon_len_wk": 12,
  "k": 5,
  "end_month": "2019-06"
}
```

Output fields:
- `neighbor_forecasts`
- `context_len_wk`
- `horizon_len_wk`
- `k`
- `end_month`

### Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant API as FastAPI /getQuote
    participant Repo as Repository (SQLite or external DB)
    participant PCS as Proc Cost Service
    participant FE as Feature Engineering
    participant KNN as NearestNeighbors

    C->>API: POST /getQuote
    API->>Repo: load_transactions(mcc, card_types)
    Repo-->>API: reference_txn
    API->>API: strict card_type filter safeguard
    API->>Repo: load_cost_type_ids()
    Repo-->>API: cost_type_ids
    API->>FE: build_monthly_features(reference_txn)
    FE-->>API: monthly_ref
    API->>FE: build_pool_by_month(monthly_ref)
    FE-->>API: pool_by_month

    alt onboarding df present
        API->>PCS: enrich(df) if proc_cost missing/null
        PCS-->>API: enriched onboarding df
        API->>FE: build query vector from df
        FE-->>API: query_vec
    else metrics only
        API->>FE: build query vector from totals/value only
        FE-->>API: query_vec
    end

    API->>KNN: fit + kneighbors
    KNN-->>API: 5 matched cases
    API->>FE: lookup_horizon_proc_cost_pct
    FE-->>API: 3-month proc_cost_pct per neighbor
    API-->>C: response
```

## Endpoint 2: getCompositeMerchant

Path: `/getCompositeMerchant`  
Method: `POST`

### What It Does

- Uses the onboarding dataframe's observed month range as the matching window.
- Finds 5 similar historical merchants over that same month window.
- Uses those 5 merchants to build a composite weekly feature history across full repository history.

This endpoint is intended for downstream model training, not direct quote output.

### Input

```json
{
  "onboarding_merchant_txn_df": [
    {"transaction_date": "2019-01-03", "amount": 20.0, "cost_type_ID": 1, "card_type": "visa"},
    {"transaction_date": "2019-01-20", "amount": 50.0, "cost_type_ID": 2, "card_type": "visa"},
    {"transaction_date": "2019-02-03", "amount": 25.0, "cost_type_ID": 1, "card_type": "visa"},
    {"transaction_date": "2019-02-18", "amount": 60.0, "cost_type_ID": 2, "card_type": "visa"}
  ],
  "mcc": 5411,
  "card_types": ["visa"]
}
```

### Input Rules

- `onboarding_merchant_txn_df` is required.
- `mcc` is required.
- `card_types` defaults to `["both"]` if omitted or empty.
- There is no metrics-only mode.
- Invalid onboarding dates are dropped. If no valid dates remain, the request fails.

### Matching Logic

Window definition:
- `matching_start_month` = earliest month in onboarding dataframe
- `matching_end_month` = latest month in onboarding dataframe

Pool construction:
- Load repository transactions filtered by `mcc` and `card_types`
- Build monthly merchant features
- Keep only merchants with full coverage across every month in the onboarding window
- Average monthly features over that window for each eligible merchant

Query construction:
- Build onboarding monthly features over the same window
- Average them across the onboarding window

Feature set used for kNN:
- `pct_ct_*`
- `total_transactions`
- `avg_amount`

### Composite Weekly Feature Logic

After matching the 5 neighbors:
- Use all historical transactions for those 5 merchants
- Map each transaction to:
  - `calendar_year`
  - `week_of_year`

Week rule:
- strict 52-week year
- `week_of_year = floor((day_of_year - 1) / 7) + 1`
- values above 52 are capped at 52

Merchant-week features built first:
- `weekly_txn_count`
- `weekly_total_proc_value`
- `weekly_avg_txn_value`
- `weekly_avg_txn_cost_pct`
- `pct_ct_*`

Then aggregate across the 5 neighbors for each `(calendar_year, week_of_year)`:
- means for core weekly metrics
- standard deviations for core weekly metrics
- means for `pct_ct_*`

Important note:
- there are no `pct_ct_*` standard deviation fields

### Output

```json
{
  "composite_merchant_id": "composite_mcc_5411_2019-01_2019-02",
  "matched_neighbor_merchant_ids": [1101, 1102, 1103, 1104, 1105],
  "k": 5,
  "matching_start_month": "2019-01",
  "matching_end_month": "2019-02",
  "weekly_features": [
    {
      "calendar_year": 2018,
      "week_of_year": 1,
      "weekly_txn_count_mean": 1.8,
      "weekly_txn_count_stdev": 0.4,
      "weekly_total_proc_value_mean": 43.2,
      "weekly_total_proc_value_stdev": 6.1,
      "weekly_avg_txn_value_mean": 24.0,
      "weekly_avg_txn_value_stdev": 3.7,
      "weekly_avg_txn_cost_pct_mean": 0.0214,
      "weekly_avg_txn_cost_pct_stdev": 0.0012,
      "neighbor_coverage": 5,
      "pct_ct_means": {"pct_ct_1": 0.5, "pct_ct_2": 0.5}
    }
  ]
}
```

Each weekly row contains:
- `calendar_year`
- `week_of_year`
- `weekly_txn_count_mean`
- `weekly_txn_count_stdev`
- `weekly_total_proc_value_mean`
- `weekly_total_proc_value_stdev`
- `weekly_avg_txn_value_mean`
- `weekly_avg_txn_value_stdev`
- `weekly_avg_txn_cost_pct_mean`
- `weekly_avg_txn_cost_pct_stdev`
- `neighbor_coverage`
- `pct_ct_means`

### Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant API as FastAPI /getCompositeMerchant
    participant Repo as Repository (SQLite or external DB)
    participant PCS as Proc Cost Service
    participant FE as Feature Engineering
    participant KNN as NearestNeighbors

    C->>API: POST /getCompositeMerchant
    API->>API: derive matching window from onboarding df
    API->>Repo: load_transactions(mcc, card_types)
    Repo-->>API: reference_txn
    API->>API: strict card_type filter safeguard
    API->>Repo: load_cost_type_ids()
    Repo-->>API: cost_type_ids
    API->>FE: build_monthly_features(reference_txn)
    FE-->>API: monthly_ref
    API->>API: build window-aligned pool
    API->>PCS: enrich(df) if proc_cost missing/null
    PCS-->>API: enriched onboarding df
    API->>API: build onboarding query vector over window
    API->>KNN: fit + kneighbors
    KNN-->>API: 5 matched merchant_ids
    API->>API: build weekly merchant features over full history
    API->>API: aggregate to composite weekly output
    API-->>C: response
```

## Processing Cost Enrichment

If `PROC_COST_SERVICE_URL` is set:
- onboarding transactions are posted to that service when `proc_cost` is missing or null

If unavailable or invalid:
- local heuristic fallback is used

Expected external request body:

```json
{
  "transactions": []
}
```

Expected external response body:

```json
{
  "transactions": []
}
```

Returned transactions must include `proc_cost`.

## Example Requests

Quote request:

```bash
curl -X POST http://127.0.0.1:8080/getQuote \
  -H "Content-Type: application/json" \
  -d '{
    "onboarding_merchant_txn_df": [
      {"transaction_date": "2019-06-01", "amount": 52.1, "cost_type_ID": 2, "card_type": "visa"},
      {"transaction_date": "2019-06-02", "amount": 22.0, "cost_type_ID": 1, "card_type": "visa"}
    ],
    "avg_monthly_txn_count": 500,
    "avg_monthly_txn_value": 48.0,
    "mcc": 5411,
    "card_types": ["visa"],
    "as_of_date": "2019-06-30T00:00:00"
  }'
```

Composite merchant request:

```bash
curl -X POST http://127.0.0.1:8080/getCompositeMerchant \
  -H "Content-Type: application/json" \
  -d '{
    "onboarding_merchant_txn_df": [
      {"transaction_date": "2019-01-03", "amount": 20.0, "cost_type_ID": 1, "card_type": "visa"},
      {"transaction_date": "2019-01-20", "amount": 50.0, "cost_type_ID": 2, "card_type": "visa"},
      {"transaction_date": "2019-02-03", "amount": 25.0, "cost_type_ID": 1, "card_type": "visa"},
      {"transaction_date": "2019-02-18", "amount": 60.0, "cost_type_ID": 2, "card_type": "visa"}
    ],
    "mcc": 5411,
    "card_types": ["visa"]
  }'
```

## Rapid Deployment

Recommended single-host command:

```bash
uvicorn app:app --host 0.0.0.0 --port 8080 --workers 2
```

Pre-deploy checklist:
- set **exactly one** database env var:
  - `DB_CONNECTION_STRING=<sqlalchemy-url>` for an external DB, **or**
  - `TRANSACTIONS_AND_COST_TYPE_DB_PATH=<path-to-sqlite>` for a local file
- set `PROC_COST_SERVICE_URL` if external processing-cost enrichment is required
- run `python -m pytest -q`
- verify `/health`

### Docker (recommended)

```bash
# External database (Option A)
docker compose up --build
# → edit DB_CONNECTION_STRING in docker-compose.yml first

# Local SQLite file (Option B)
mkdir -p data
cp /path/to/your.sqlite data/
# → set TRANSACTIONS_AND_COST_TYPE_DB_PATH=/data/your.sqlite in docker-compose.yml
docker compose up --build
```

## Adaptation Guide

Common adaptation points:

1. Change repository backend
- `SQLAlchemyMerchantRepository` handles any SQLAlchemy-compatible DB — set `DB_CONNECTION_STRING`
- `SQLiteMerchantRepository` handles a local file — set `TRANSACTIONS_AND_COST_TYPE_DB_PATH`
- To add a new backend (e.g. REST API), implement the `MerchantRepository` protocol in `repository.py` and wire it into `_build_repository()` in `app.py`
- Keep `load_transactions` and `load_cost_type_ids` signatures consistent

2. Change kNN behavior
- Adjust `k`
- Change matching feature set
- Change context/horizon for `/getQuote`

3. Change weekly composite features
- Add or remove merchant-week metrics
- Add more mean/stdev aggregates
- Preserve `calendar_year + week_of_year` if downstream models need stable weekly indexing

4. Replace processing-cost enrichment behavior
- Integrate production external service
- Add retries, timeout policies, and observability

## Production Notes

- Add auth before external exposure.
- Add request logging and correlation IDs.
- Add request size limits because onboarding dataframes can be large.
- Monitor latency, 4xx/5xx rates, and enrichment-service failures.
- Prefer PostgreSQL or another external DB for multi-instance production over SQLite.
