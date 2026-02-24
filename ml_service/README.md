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

## Alternative Model Approaches

You are not required to use pgvector or PostgreSQL at all. Pick the approach that fits your model.

---

### Option A — Return results only (no storage)

The simplest option. Your model computes a result and returns it. Nothing is saved.  
Use this if your model is stateless or you don't need to persist anything.

```python
# service.py
class RateOptimisationService:
    @staticmethod
    def optimise(df, metrics, db):
        recommended_rate = metrics["effective_rate"] * 1.05  # your logic here
        return RateOptimisationResult(recommended_rate=recommended_rate)
```

Just return a valid instance of your schema — done.

---

### Option B — Pre-trained model file (scikit-learn / XGBoost / LightGBM)

Train your model locally, save it to a file, load it at runtime.

1. Save your model outside Docker (on your machine):
```python
import joblib
joblib.dump(model, "tpv_model.pkl")
```

2. Place the file in `ml_service/models/tpv_model.pkl`

3. Load and use it in `service.py`:
```python
import joblib
from pathlib import Path

_MODEL = joblib.load(Path(__file__).parent.parent.parent / "models" / "tpv_model.pkl")

class TPVPredictionService:
    @staticmethod
    def predict(df, metrics, db):
        X = [[metrics["total_payment_volume"], metrics["slope"] or 0.0]]
        predicted = float(_MODEL.predict(X)[0])
        return TPVPredictionResult(predicted_tpv=predicted, prediction_horizon="next_30_days")
```

> The `ml_service/models/` folder is inside the Docker volume — the file is available inside the container automatically.

---

### Option C — PyTorch / TensorFlow model

Same as Option B but load with `torch.load()` or `tf.saved_model.load()`.

```python
import torch
from pathlib import Path

_MODEL = torch.load(Path(__file__).parent.parent.parent / "models" / "tpv_lstm.pt")
_MODEL.eval()

class TPVPredictionService:
    @staticmethod
    def predict(df, metrics, db):
        import torch
        x = torch.tensor([[
            metrics["total_payment_volume"],
            metrics["effective_rate"],
            metrics["slope"] or 0.0,
        ]], dtype=torch.float32)
        with torch.no_grad():
            predicted = float(_MODEL(x).item())
        return TPVPredictionResult(predicted_tpv=predicted, prediction_horizon="next_30_days")
```

Add `torch` or `tensorflow` to `ml_service/requirements.txt` and rebuild.

---

### Option D — Time-series models (ARIMA / Prophet)

Fit directly on the `df` at request time. No pre-training needed.

**Prophet example:**
```python
# requirements.txt: prophet
from prophet import Prophet
import pandas as pd

class TPVPredictionService:
    @staticmethod
    def predict(df, metrics, db):
        ts = (
            df.rename(columns={"transaction_date": "ds", "amount": "y"})
              .groupby("ds", as_index=False)["y"].sum()
        )
        ts["ds"] = pd.to_datetime(ts["ds"])
        m = Prophet()
        m.fit(ts)
        future = m.make_future_dataframe(periods=30)
        forecast = m.predict(future)
        predicted = float(forecast["yhat"].iloc[-1])
        return TPVPredictionResult(predicted_tpv=predicted, prediction_horizon="next_30_days")
```

---

### Option E — Save results to a CSV file

If you want to write output to a file instead of (or in addition to) the database:

```python
import pandas as pd
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

class RateOptimisationService:
    @staticmethod
    def optimise(df, metrics, db):
        result_df = df.copy()
        result_df["recommended_rate"] = metrics["effective_rate"] * 1.05
        result_df.to_csv(OUTPUT_DIR / f"rate_optimisation_mcc{metrics['mcc']}.csv", index=False)
        return RateOptimisationResult(recommended_rate=metrics["effective_rate"] * 1.05)
```

> Create `ml_service/outputs/` and add it to `.gitignore` if you don't want output files committed.

---

### Option F — Fit a model and store it to PostgreSQL (pgvector)

See the **Storing Vectors and Cluster Data in PostgreSQL** section below. Use this if you need nearest-neighbour search or want to persist embeddings across requests.

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

## Storing Vectors and Cluster Data in PostgreSQL

Two tables are already defined in `ml_service/models.py` and created automatically on startup. You do not need to create them manually.

### Table 1 — `merchant_cluster_vectors`
One row per merchant per calculation run. Written by the **Cluster Assignment Engine**.

| Column | Type | Description |
|---|---|---|
| `merchant_id` | String | Merchant identifier (optional) |
| `mcc` | Integer | Merchant Category Code |
| `cluster_id` | Integer | Assigned cluster (filled by assignment engine) |
| `cluster_label` | String | Human-readable cluster name |
| `total_cost` | Float | From cost metrics |
| `total_payment_volume` | Float | From cost metrics |
| `effective_rate` | Float | From cost metrics |
| `slope` | Float | From cost metrics |
| `cost_variance` | Float | From cost metrics |
| `embedding` | vector(8) | pgvector feature vector |

**To write a row** (inside your `service.py`):
```python
from models import MerchantClusterVector

record = MerchantClusterVector(
    mcc                  = metrics["mcc"],
    cluster_id           = 0,
    cluster_label        = "My Cluster",
    total_cost           = metrics["total_cost"],
    total_payment_volume = metrics["total_payment_volume"],
    effective_rate       = metrics["effective_rate"],
    slope                = metrics.get("slope"),
    cost_variance        = metrics.get("cost_variance"),
    embedding            = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],  # must be length VECTOR_DIM
)
db.add(record)
db.commit()
```

---

### Table 2 — `cluster_centroids`
One row per cluster. Written by the **Cluster Generation Engine**, read by the **Cluster Assignment Engine**.

| Column | Type | Description |
|---|---|---|
| `cluster_id` | Integer (unique) | Cluster index |
| `cluster_label` | String | Human-readable name |
| `centroid` | vector(8) | pgvector centroid vector |

**To write centroids** (inside your `service.py`):
```python
from models import ClusterCentroid

existing = db.query(ClusterCentroid).filter_by(cluster_id=0).first()
if existing:
    existing.centroid      = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    existing.cluster_label = "High-Volume Grocery"
else:
    db.add(ClusterCentroid(
        cluster_id    = 0,
        cluster_label = "High-Volume Grocery",
        centroid      = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
    ))
db.commit()
```

---

### Nearest-Neighbour Search (pgvector)

To find the closest centroid to a feature vector, use the `<->` (L2 distance) operator:

```python
from sqlalchemy import text
from models import ClusterCentroid

feature_vec = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
vec_str = "[" + ",".join(str(v) for v in feature_vec) + "]"

nearest = (
    db.query(ClusterCentroid)
    .order_by(text(f"centroid <-> '{vec_str}'::vector"))
    .first()
)
# nearest.cluster_id, nearest.cluster_label
```

> Swap `<->` for `<=>` to use cosine similarity instead of L2 distance.

---

### Changing the Vector Size

The vector dimension is set in `ml_service/config.py`:
```python
VECTOR_DIM: int = 8   # change this to match your feature vector length
```

If you change `VECTOR_DIM` you must also update `_build_feature_vector()` in  
`ml_service/modules/cluster_generation/service.py` to return a list of the same new length.  
Then rebuild and restart: `docker compose build ml-service && docker compose up ml-service`

---

## After Making Changes

Restart the container to pick up edits:
```bash
docker restart ml-service
```

Swagger UI for all ML endpoints: `http://localhost/ml/docs`
