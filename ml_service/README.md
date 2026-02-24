# ML Service — Integration Guide

## Overview

The ML service runs as a separate Docker container (`ml-service:8001`).  
It receives an enriched CSV + cost metrics from the backend automatically after every `/calculations/transaction-costs` call, then runs 4 engines in sequence.

Each engine is a self-contained module under `ml_service/modules/`:

| Module folder | Your job |
|---|---|
| `rate_optimisation/` | Suggest an optimal interchange rate |
| `tpv_prediction/` | Forecast future total payment volume |
| `cluster_generation/` | Cluster merchants by behaviour |
| `cluster_assignment/` | Assign a new merchant to an existing cluster |

---

## What You Receive (Inputs)

Every engine receives the same two inputs:

### `df` — pandas DataFrame (the enriched CSV)
Columns available:

| Column | Description |
|---|---|
| `transaction_date` | Date of transaction |
| `merchant_id` | Merchant identifier |
| `amount` | Transaction amount ($) |
| `card_type` | Visa / Mastercard / Amex |
| `card_brand` | Card network |
| `card_cost` | Interchange card fee ($) |
| `network_cost` | Network fee ($) |
| `total_cost` | `card_cost + network_cost` ($) |
| `match_found` | Whether a fee rule was matched |

### `metrics` — dict
```python
{
    "mcc":                   5499,      # Merchant Category Code
    "total_cost":            123.45,    # Sum of all transaction costs
    "total_payment_volume":  7500.00,   # Sum of all transaction amounts
    "effective_rate":        1.646,     # total_cost / total_payment_volume × 100
    "slope":                 0.013,     # Linear regression slope of costs over time
    "cost_variance":         0.0004,    # Variance of individual transaction costs
}
```

---

## Where to Add Your Model Logic

**The only file you need to edit is `service.py` inside your module.**

```
ml_service/modules/<your_module>/
    service.py     ← PUT YOUR MODEL LOGIC HERE
    schemas.py     ← add/change output fields here if needed
    controller.py  ← do not touch
    __init__.py    ← do not touch
```

### Steps

**1. Open your `service.py`**  
Find the stub method (e.g. `predict()`, `optimise()`, `generate()`, `assign()`).  
Replace the stub logic with your model.

**2. Update `schemas.py` if your output fields change**  
The schema defines what the API returns. Add or remove fields to match your model output.  
Your `service.py` method must return an instance of that schema.

**3. If you have a pre-trained model file (`.pkl`, `.joblib`, `.pt`, etc.)**  
- Create the folder `ml_service/models/` if it doesn't exist
- Place your model file there
- Load it in `service.py` using `joblib.load()` or `torch.load()` etc.

Example:
```python
import joblib
from pathlib import Path

MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "your_model.pkl"
_model = joblib.load(MODEL_PATH)
```

**4. If you need extra Python packages**  
Add them to `ml_service/requirements.txt`, then rebuild:
```bash
docker compose build ml-service
docker compose up ml-service
```

---

## Testing Your Engine in Isolation (Postman)

Each engine has its own endpoint you can call directly without going through the backend:

```
POST http://localhost/ml/rate-optimisation
POST http://localhost/ml/tpv-prediction
POST http://localhost/ml/cluster-generation
POST http://localhost/ml/cluster-assignment
```

**Postman setup — form-data body:**

| Key | Type | Value |
|---|---|---|
| `enriched_csv` | File | upload a `*_enriched.csv` file from the backend |
| `mcc` | Text | `5499` |
| `total_cost` | Text | `123.45` |
| `total_payment_volume` | Text | `7500.00` |
| `effective_rate` | Text | `1.646` |
| `slope` | Text | `0.013` (optional) |
| `cost_variance` | Text | `0.0004` (optional) |

> To get an enriched CSV to test with, call `POST /api/v1/calculations/transaction-costs?mcc=5499`  
> with one of the files from `input_files/` — the response body is the enriched CSV.

---

## After Making Changes

Restart the container to pick up edits:
```bash
docker restart ml-service
```

Swagger UI for all ML endpoints: `http://localhost/ml/docs`
