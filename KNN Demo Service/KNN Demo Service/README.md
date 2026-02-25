# KNN Rate Quote Service (Demo)

Lightweight demo for a KNN-based merchant rate quotation service. It supports
inputs as a transactions dataframe, metrics-only, or a combination of both.

## Files

- knn_rate_quote_service.py: service implementation
- make_sql.py: initializes the local SQLite database
- rate_quote.sqlite: local SQLite database (created on first run)
- test_knn_rate_quote_service.py: smoke test script

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Initialize the SQLite database by running the initialization script or by instantiating the service:

```bash
python make_sql.py
```

Or from the project root:

```bash
/Users/yattmeo/Desktop/SMU/Code/404_found_us/.venv/bin/python ml_pipeline/Matt_EDA/KNN\ Demo\ Service/make_sql.py
```

You can also initialize the database implicitly by instantiating the service:

```python
from knn_rate_quote_service import KNNRateQuoteService

service = KNNRateQuoteService()
print(service.db_path)
```

## Smoke Test

```bash
/Users/yattmeo/Desktop/SMU/Code/404_found_us/.venv/bin/python ml_pipeline/Matt_EDA/KNN\ Demo\ Service/test_knn_rate_quote_service.py
```

## Usage

### 1) Transactions dataframe input with card type filtering

```python
import pandas as pd
from knn_rate_quote_service import KNNRateQuoteService

service = KNNRateQuoteService()

df = pd.DataFrame(
    {
        "transaction_date": ["2019-01-03", "2019-01-14", "2019-01-20"],
        "amount": [12.5, 49.9, 7.2],
        "cost_type_ID": [1, 2, 1],
        "card_type": ["visa", "mastercard", "visa"],
    }
)

# Get quote for Visa transactions only
result = service.quote(df=df, mcc=5411, card_type="visa")
print(result)

# Get quote for Mastercard transactions only
result = service.quote(df=df, mcc=5411, card_type="mastercard")
print(result)

# Get quote for both Visa and Mastercard
result = service.quote(df=df, mcc=5411, card_type="both")
print(result)
```

### 2) Metrics-only input with card type

```python
from knn_rate_quote_service import KNNRateQuoteService

service = KNNRateQuoteService()

# Quote with Visa-only reference pool
result = service.quote(
    df=None,
    mcc=5411,
    card_type="visa",
    monthly_txn_count=200,
    avg_amount=45.0,
    as_of_date="2019-06-30",
)
print(result)
```

### 3) Both dataframe and metrics with card type

If you pass both, the dataframe provides the cost-type mix (filtered by card_type) 
and the metrics can override totals if desired.

```python
import pandas as pd
from knn_rate_quote_service import KNNRateQuoteService

service = KNNRateQuoteService()

df = pd.DataFrame(
    {
        "transaction_date": ["2019-01-03", "2019-01-14", "2019-01-20"],
        "amount": [12.5, 49.9, 7.2],
        "cost_type_ID": [1, 2, 1],
        "card_type": ["visa", "visa", "visa"],
    }
)

result = service.quote(
    df=df,
    mcc=5411,
    card_type="visa",
    monthly_txn_count=500,
    avg_amount=60.0,
)
print(result)
```

## Notes

- The service expects 62 cost types from cost_type_id_18feb.csv.
- The SQLite DB is created next to the service as rate_quote.sqlite.
- The service builds the pool-by-month once on initialization.
- Card type filtering: pass `card_type="visa"`, `card_type="mastercard"`, or `card_type="both"` (default) to the `quote()` method.
- When filtering by card type, the reference pool is built from merchants with that card type.
- **as_of_date behavior**: If `as_of_date` is beyond the available data range, the service automatically maps it to the same month in the most recent available year. For example, if data ends in 2019-10 and you request 2021-06-30, it will use 2019-06 patterns.
