# 404 Found Us — FYP 2026

Merchant pricing intelligence platform. Calculates interchange & network fees, forecasts processing costs and transaction volumes, and recommends optimal merchant rates.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Nginx  (:80)                                 │
│  Reverse proxy — single entry point for all traffic                 │
├────────────┬───────────────┬───────────────┬────────────────────────┤
│  /sales/*  │  /merchant/*  │   /api/v1/*   │       /ml/*            │
└─────┬──────┴──────┬────────┴───────┬───────┴─────────┬──────────────┘
      │             │                │                 │
      ▼             ▼                ▼                 ▼
┌───────────┐ ┌──────────────┐ ┌───────────┐   ┌─────────────┐
│ Frontend  │ │  Merchant    │ │  Backend  │   │ ML Service  │
│ React CRA │ │  Frontend    │ │  FastAPI  │   │  FastAPI    │
│ :3000     │ │  Vite + TS   │ │  :8000    │   │  :8001      │
│           │ │  :3001       │ │           │   │             │
│ Sales     │ │ Online       │ │ Fee calc, │   │ KNN quotes, │
│ pricing   │ │ quotation    │ │ merchant  │   │ cost & vol  │
│ tools     │ │ tool         │ │ CRUD, tx  │   │ forecasting │
│           │ │              │ │ upload    │   │             │
└───────────┘ └──────────────┘ └─────┬─────┘   └──────┬──────┘
                                     │                 │
                          ┌──────────┤          ┌──────┴──────┐
                          │          │          │             │
                          ▼          ▼          ▼             ▼
                    ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐
                    │PostgreSQL│ │ Cost   │ │Postgres│ │M9 Forecast   │
                    │ pgvector │ │Structure││pgvector│ │Service       │
                    │ :5432    │ │ JSONs  │ │:5432   │ │FastAPI :8092 │
                    │          │ │(Visa / │ │        │ │              │
                    │ 3.88M tx │ │Master) │ │ KNN tx │ │Monthly cost  │
                    │ rows     │ │        │ │ data   │ │forecast (M9) │
                    └──────────┘ └────────┘ └────────┘ └──────────────┘
```

### Data Flow — Rate Quotation

```
User submits transactions
        │
        ▼
  Backend /api/v1/calculations/desired-margin-details
        │
        ├──► ML Service /ml/getCompositeMerchant     (KNN: 5 nearest merchants)
        │         │
        │         ▼
        ├──► ML Service /ml/GetCostForecast           (M9 → 12 weekly cost %)
        │         │
        │         └──► M9 Forecast Service :8092      (monthly forecast, interpolated to weekly)
        │
        ├──► ML Service /ml/GetVolumeForecast         (SARIMA → 12 weekly TPV $) # Wait for Matthew
        │
        ▼
  Backend pairs 12 cost + 12 volume weeks
  → profitability curve, estimated profit, recommended rate
        │
        ▼
  Frontend renders charts: Cost Forecast, Volume Trend, Probability Curve
```

---

## Services (7 containers)

| Container | Build Context | Internal Port | Purpose |
|-----------|--------------|---------------|---------|
| **ml-postgres** | `pgvector/pgvector:pg16` | 5432 | PostgreSQL + pgvector — transaction data & KNN tables |
| **ml-backend** | `./backend` | 8000 | FastAPI — fee calculation, merchant CRUD, tx upload, ML orchestration |
| **ml-frontend** | `./frontend` | 3000 | React CRA — Sales pricing tools (served at `/sales`) |
| **ml-merchant-frontend** | `./merchant-frontend` | 3001 | Vite + React + TS — Online quotation tool (served at `/merchant`) |
| **ml-nginx** | `nginx:alpine` | **80** | Reverse proxy — sole public port |
| **ml-service** | `./ml_service` | 8001 | FastAPI — KNN rate quoting, cost & volume forecasting |
| **m9-forecast-service** | `./ml_pipeline/Matt_EDA/services/GetAvgProcCostForecast Service v2` | 8092 | FastAPI — M9 monthly cost forecast (HuberRegressor + conformal intervals) |

---

## Project Structure

```
404_found_us/
├── backend/                  FastAPI backend (fee calc, merchant CRUD, ML orchestration)
├── frontend/                 Sales React frontend (CRA, served at /sales)
├── merchant-frontend/        Merchant React frontend (Vite + TS, served at /merchant)
├── ml_service/               ML microservice (KNN, cost forecast, volume forecast)
│   └── modules/
│       ├── knn_rate_quote/       KNN rate quote engine (PostgreSQL-backed)
│       ├── cost_forecast/        M9 v2 cost forecast proxy + SARIMA legacy
│       ├── volume_forecast/      SARIMA/SARIMAX volume forecast
│       ├── m9_forecast/          M9 forecast service proxy layer
│       ├── rate_optimisation/    Rate optimisation engine (stub)
│       ├── tpv_prediction/       TPV prediction engine (stub)
│       ├── cluster_generation/   Cluster generation (scaffold)
│       └── cluster_assignment/   Cluster assignment (scaffold)
├── nginx/                    Reverse proxy config (default.conf)
├── cost_structure/           Visa & Mastercard fee schedule JSONs
├── KNN Demo Service/         Source SQLite DB (mounted read-only into ml-service)
├── ml_pipeline/              EDA notebooks, modelling, pre-processing
│   ├── Matt_EDA/                 EDA analysis, service prototypes, clustering
│   ├── forecasting/              SARIMA notebooks & scripts
│   ├── pre-processing/           SQL extraction, train/test splits
│   └── tree_models/              Tree-based model prototypes
├── docker-compose.yml
└── data/                     Data loading scripts
```

---

## Getting Started

```bash
# 1. Start all services
docker compose up --build -d

# 2. Seed KNN reference data (first run only)
docker compose exec ml-service python migrate_sqlite_to_postgres.py

# 3. Load transaction data (first run only)
python data/load_to_postgres.py
```

| URL | What |
|-----|------|
| http://localhost/sales/ | Sales pricing tools |
| http://localhost/merchant/ | Online quotation tool |
| http://localhost/api/v1/docs | Backend API docs |
| http://localhost/ml/docs | ML Service API docs |

---

## API Reference

### Backend (`/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/calculations/merchant-fee` | Calculate merchant fees from transactions |
| POST | `/calculations/desired-margin` | Calculate desired margin rate |
| POST | `/calculations/desired-margin-details` | **Full pipeline** — fee calc + ML forecasts + profitability |
| POST | `/calculations/transaction-costs` | Interchange & network cost enrichment (streams CSV) |
| POST | `/transactions/upload` | Upload transaction CSV/Excel |
| POST | `/projections/revenue` | ML-driven revenue projection |
| POST | `/merchant-quote` | Generate merchant quote |
| GET | `/merchants` | List merchants |
| GET | `/mcc-codes` | List MCC codes |

### ML Service (`/ml`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/process` | Run full ML pipeline (rate opt → TPV → KNN) |
| POST | `/knn-rate-quote` | KNN rate quote engine |
| POST | `/getQuote` | Match 5 similar merchants, return cost history |
| POST | `/getCompositeMerchant` | Match 5 similar merchants, return composite features |
| POST | `/GetCostForecast` | 12-week cost forecast (M9 monthly → weekly interpolation) |
| POST | `/GetVolumeForecast` | 12-week volume forecast (SARIMA) |
| POST | `/rate-optimisation` | Rate optimisation engine (stub) |
| POST | `/tpv-prediction` | TPV prediction engine (stub) |

---

## Key Data Assets

| Asset | Location | Description |
|-------|----------|-------------|
| Transaction data | PostgreSQL `mldb` | ~3.88M rows, loaded via `data/load_to_postgres.py` |
| KNN reference DB | `KNN Demo Service/KNN Demo Service/rate_quote.sqlite` | Source for `knn_transactions` + `knn_cost_type_ref` tables |
| Fee schedules | `cost_structure/*.JSON` | Visa & Mastercard card-level and network-level fees |
| Pre-processed splits | `ml_pipeline/pre-processing/` | Train/test/validate CSVs for MCCs 4121, 5411, 5812 |

---

## Notes

- **KNN Demo Service folder** must be kept — `docker-compose.yml` mounts it read-only into `ml-service`. The SQLite database is the source for KNN data migration.
- **`migrate_sqlite_to_postgres.py`** is a one-off data tool, safe to re-run (`if_exists="replace"`).
- **M9 forecast service** runs in degraded mode without trained artifacts — falls back to `base_cost_rate` from cost-structure JSONs with drift factors and CI widening.
- **Cost forecast** interpolates 3 monthly M9 forecasts into 12 weekly points to match the SARIMA volume forecast horizon.

### Additional ML endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/ml/getQuote` | KNN quote service endpoint |
| `POST` | `/ml/getCompositeMerchant` | KNN composite merchant profile endpoint |
| `POST` | `/ml/GetCostForecast` | Cost forecast service endpoint |
| `POST` | `/ml/GetVolumeForecast` | Volume forecast service endpoint |

---

## Architecture And Mermaid Documentation

Architecture and runtime diagrams are maintained in [presentation/README.md](presentation/README.md).

- Markdown Mermaid sources: [presentation](presentation)
- Browser-friendly diagram pack: [presentation/index.html](presentation/index.html)

Quick local preview:

```bash
python -m http.server 8000
```

Then open: `http://localhost:8000/presentation/index.html`

Current `/sales` probability chart behavior (no current rate path):

- Chart title: `Probability of Profitability`
- Y-axis fixed to `0%` to `100%`
- Curve approaches an asymptote at `97.5%` (does not touch `100%`)
- Suggested rate is shown as a vertical marker line
- X-axis label is `Rate (%)` with de-cluttered "nice" tick labels

---

## Backend Integration Tests

Integration tests are now scaffolded under `backend/tests/integration` and use an isolated SQLite test database with FastAPI dependency overrides.

### Test files

- `backend/tests/conftest.py`
- `backend/tests/integration/test_api_integration.py`

### Run locally (inside `backend/`)

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

### What is covered

- Root + health endpoints
- Merchant create/get/list flow
- Transaction CSV upload + list flow
- Merchant fee + desired margin calculation endpoints (success + validation)
- MCC list/search/get endpoints (including error cases)
