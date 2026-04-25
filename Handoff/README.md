# 404 Found Us — FYP 2026

Merchant pricing intelligence platform. Calculates interchange & network fees, forecasts processing costs and transaction volumes, and recommends optimal merchant rates.

> Full architecture diagrams (Mermaid) are in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│             Nginx  (:${NGINX_PORT:-80})                             │
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
│ pricing   │ │ quotation    │ │ merchant  │   │ cost + vol  │
│ tools     │ │ tool         │ │ CRUD, tx  │   │ + profit    │
│           │ │              │ │ upload    │   │ forecasting │
└───────────┘ └──────────────┘ └─────┬─────┘   └──────┬──────┘
                                     │                 │
                          ┌──────────┘                 │
                          │                            │
                          ▼                            ▼
                    ┌──────────┐              ┌──────────────────┐
                    │PostgreSQL│              │  Trained Model   │
                    │  16      │              │  Artifacts       │
                    │ :5432    │              │                  │
                    │          │              │  proc_cost/      │
                    │ app data │◄─────────── │  (4 MCCs × 3     │
                    │ + KNN    │  shared DB   │   horizons)      │
                    └──────────┘              │  tpv/ (4 MCCs)   │
                                             └──────────────────┘
```

All port numbers shown are defaults. Each service port is configurable via `.env` — see [Environment variables](#environment-variables).

### Data Flow — Rates Quotation Tool

```
User: MCC + Transactions CSV + Desired Margin (bps) + [Current Rate] + [Fixed Fee]
        │
        ▼
  DesiredMarginCalculator.jsx
        │
        ▼
  Backend /api/v1/calculations/desired-margin-details
        │
        ├─► Calculate interchange & network costs from transactions
        │
        ├─► ML Service /ml/getCompositeMerchant     (KNN: 5 nearest merchants)
        │
        ├─► ML Service /ml/GetTPVForecast            (Conformal monthly TPV prediction)
        │
        ├─► ML Service /ml/GetCostForecast           (processing-cost forecast → 3-month cost %)
        │
        ├─► ML Service /ml/GetProfitForecast         (Monte Carlo: cost + TPV + fee + fixed fee)
        │
        ▼
  Backend assembles: recommended rate, profitability curve,
  cost & volume forecasts, estimated profit range
        │
        ▼
  DesiredMarginResults.jsx — Charts: Cost Forecast, Volume Trend, Probability Curve
```

### Data Flow — Profitability Calculator

```
User: MCC + Transactions CSV + [Current Rate] + [Fixed Fee]
        │  (desired margin hardcoded at 1.5%)
        ▼
  EnhancedMerchantFeeCalculator.jsx
        │
        ▼
  Backend /api/v1/calculations/desired-margin-details
        │
        │  (Same ML pipeline as Rates Quotation — 4 sequential ML calls)
        │
        ▼
  ResultsPanel.jsx — Charts: Cost Forecast, Volume Trend, Probability Curve
                   + Processing Volume, Fee Revenue
```

---

## Services (6 containers)

All service ports are configurable via `.env`. The defaults below match the out-of-the-box values.

| Container | Build Context | Env var | Default port | Purpose |
|-----------|--------------|---------|-------------|------|
| **ml-postgres** | `postgres:16` | — | 5432 | PostgreSQL 16 — all application data & KNN tables |
| **ml-backend** | `./backend` | `BACKEND_PORT` | 8000 | FastAPI — fee calculation, merchant CRUD, tx upload, ML orchestration |
| **ml-frontend** | `./frontend` | `FRONTEND_PORT` | 3000 | React CRA — Sales pricing tools (served at `/sales`) |
| **ml-merchant-frontend** | `./merchant-frontend` | `MERCHANT_PORT` | 3001 | Vite + React + TS — Online quotation tool (served at `/merchant`) |
| **ml-nginx** | `nginx:alpine` | `NGINX_PORT` | **80** | Reverse proxy — sole public port |
| **ml-service** | `./ml_service` | `ML_PORT` | 8001 | FastAPI — KNN rate quoting, cost/volume/profit/TPV forecasting |

To run on different ports, edit the relevant variables in `.env` before `docker compose up`. All Dockerfiles use shell-form `CMD` so env vars expand at startup. The nginx config is generated from `nginx/default.conf.template` via the official nginx `envsubst` entrypoint.

---

## Project Structure

```
Handoff/
├── .env.example                Template — copy to .env and fill in values
├── docker-compose.yml          Service orchestration (6 containers)
├── e2e_test.py                 End-to-end smoke test (13 checks against live stack)
├── ARCHITECTURE.md             Full architecture docs with Mermaid diagrams
├── backend/                    FastAPI backend
│   ├── app.py                  Entry point, CORS, lifespan
│   ├── config.py               Settings loaded from env vars
│   ├── routes.py               All /api/v1 endpoints
│   ├── services.py             DataProcessing, MerchantFeeCalculation, MCC services
│   ├── models.py               ORM: transactions, merchants, calculation_results
│   ├── schemas.py              Pydantic request/response models
│   ├── validators.py           CSV/Excel row validation
│   ├── tests/                  Integration tests (SQLite, FastAPI overrides)
│   └── modules/
│       ├── cost_calculation/   Interchange & network cost computation
│       └── merchant_quote/     Quote generation with ML pipeline
├── ml_service/                 FastAPI ML microservice
│   ├── app.py                  Entry point, initialises proc_cost + TPV caches
│   ├── config.py               Settings loaded from env vars
│   ├── routes.py               All /ml endpoints
│   ├── seed_knn_data.py        Loads knn_seed.csv into PostgreSQL at startup
│   ├── artifacts/
│   │   ├── proc_cost/
│   │   │   ├── 4121/{1,3,6}/   Processing-cost models — MCC 4121 (taxi)
│   │   │   ├── 5411/{1,3,6}/   Processing-cost models — MCC 5411 (grocery)
│   │   │   ├── 5499/{1,3,6}/   Processing-cost models — MCC 5499 (misc food)
│   │   │   └── 5812/{1,3,6}/   Processing-cost models — MCC 5812 (restaurants)
│   │   └── tpv/
│   │       ├── 4121/            TPV forecast models — MCC 4121
│   │       ├── 5411/            TPV forecast models — MCC 5411
│   │       ├── 5499/            TPV forecast models — MCC 5499
│   │       └── 5812/            TPV forecast models — MCC 5812
│   ├── data/
│   │   ├── README.md           KNN seed data schema docs
│   │   └── knn_seed.csv        (not included) — place here before docker compose up
│   └── modules/
│       ├── knn_rate_quote/     KNN-based rate quotation (PostgreSQL-backed)
│       ├── cost_forecast/      Artifact-based processing-cost prediction
│       ├── tpv_forecast/       Conformal TPV prediction
│       ├── volume_forecast/    SARIMAX weekly volume forecast
│       ├── profit_forecast/    Monte Carlo profit simulation
│       ├── rate_optimisation/  Rate optimisation engine
│       └── tpv_prediction/     TPV prediction engine
├── frontend/                   React CRA — Sales calculator UI (served at /sales)
├── merchant-frontend/          Vite + React + TS — Merchant quotation UI (served at /merchant)
├── nginx/
│   ├── default.conf            Static reference (not mounted at runtime)
│   └── default.conf.template   Envsubst template — processed by nginx:alpine on startup
├── cost_structure/
│   ├── cost_type_id.csv        Maps cost type IDs 1–61 to fee line items
│   ├── masterCard_Card.JSON    Mastercard card-level fee schedule
│   ├── masterCard_Network.JSON Mastercard network-level fee schedule
│   ├── visa_Card.JSON          Visa card-level fee schedule
│   └── visa_Network.JSON       Visa network-level fee schedule
└── training/                   Offline training pipeline (run outside Docker)
    ├── DATA_SPEC.md            Full data schema, pipeline, and change-propagation docs
    ├── prepare_data.py         Annotate raw transactions + aggregate to monthly data
    ├── requirements.txt        Training-only Python dependencies
    ├── proc_cost/
    │   ├── config.py           MCCs, horizons, artifact output path
    │   └── train.py            Train HuberRegressor + conformal interval models
    └── tpv/
        ├── config.py           MCCs, artifact output path
        └── train.py            Train TPV forecast models
```

---

## Getting Started

Copy `.env.example` to `.env` and adjust any values, then start the stack:

```bash
cp .env.example .env
# Fill in the change_me_* values before proceeding
docker compose up --build -d
```

| URL | What |
|-----|------|
| http://localhost/sales/ | Sales pricing tools |
| http://localhost/merchant/ | Online quotation tool |
| http://localhost/api/v1/docs | Backend API docs (Swagger) |
| http://localhost/ml/docs | ML Service API docs (Swagger) |

> **KNN endpoints** (`/ml/getCompositeMerchant`, `/ml/getQuote`) require `ml_service/data/knn_seed.csv` to exist before `docker compose up`. Without it, all other features work normally and KNN endpoints return 400. See [Quickstart from Scratch — Step 6](#step-6--optional-seed-knn-data).

### Environment variables

All configuration is driven by `.env`. Copy `.env.example` and fill in the values marked `change_me_*` before deploying.

| Variable | Default | What it controls |
|----------|---------|------------------|
| `POSTGRES_USER` | pguser | PostgreSQL username |
| `POSTGRES_PASSWORD` | *(change me)* | PostgreSQL password — **change in production** |
| `POSTGRES_DB` | mldb | Database name |
| `DATABASE_URL` | *(derived from above)* | SQLAlchemy connection string |
| `SECRET_KEY` | *(change me)* | JWT signing key — **change in production** |
| `CORS_ORIGINS` | http://localhost | Allowed CORS origins |
| `ML_SERVICE_URL` | http://ml-service:8001 | Backend → ML service URL (internal Docker network) |
| `COST_STRUCTURE_DIR` | /app/cost_structure | Path to fee-schedule JSONs inside backend container |
| `KNN_SEED_CSV_PATH` | /data/knn_seed.csv | CSV seeded into PostgreSQL at ml-service startup |
| `PROC_COST_ARTIFACTS_BASE_PATH` | /app/artifacts/proc_cost | Where ml-service reads proc_cost models |
| `TPV_ARTIFACTS_BASE_PATH` | /app/artifacts/tpv | Where ml-service reads TPV models |
| `ARTIFACT_POLL_INTERVAL_S` | 60 | How often ml-service polls for new artifacts (hot-reload) |
| `DEFAULT_N_SIMULATIONS` | 10000 | Monte Carlo simulation count |
| `ML_PIPELINE_TIMEOUT_S` | 45 | Per-ML-call timeout the backend waits (seconds) |
| `NGINX_PORT` | 80 | Public host port |
| `BACKEND_PORT` | 8000 | uvicorn bind port inside backend container |
| `ML_PORT` | 8001 | uvicorn bind port inside ml-service container |
| `FRONTEND_PORT` | 3000 | `serve` port inside frontend container |
| `MERCHANT_PORT` | 3001 | `serve` port inside merchant-frontend container |

---

## Quickstart from Scratch (Fresh Data, No Model Artifacts)

Use this guide when you have **raw transaction data but no pre-trained models**. It walks through generating the cost-type reference, preparing training data, training both model families, then starting the application.

### Prerequisites

- Docker + Docker Compose v2 installed
- Python 3.11+ with a virtual environment (`python -m venv .venv && source .venv/bin/activate`)
- Training dependencies installed: `pip install -r training/requirements.txt`

### Step 1 — Prepare your raw data

Place your raw transaction CSV(s) into `training/data/`. The required columns are documented in [training/DATA_SPEC.md](training/DATA_SPEC.md).

At minimum you need:
- `transaction_date` (YYYY-MM-DD or similar parseable date)
- `mcc` (4-digit merchant category code)
- `card_scheme` (`VISA` or `MASTERCARD`)
- `card_type` (maps to card-level fee schedule)
- `transaction_amount` (numeric, in SGD)
- Enough volume to cover the MCCs you want to train (see `training/*/config.py` for the list)

### Step 2 — Verify the cost-type reference CSV

The file `cost_structure/cost_type_id.csv` maps cost type IDs (1–N) to interchange/network fee line items. It is already present and was generated from the Visa and Mastercard JSON fee schedules.

If you have updated fee schedules, regenerate it by following Section 2 of [training/DATA_SPEC.md](training/DATA_SPEC.md), then replace `cost_structure/cost_type_id.csv`.

### Step 3 — Annotate transactions and aggregate

```bash
cd training

# Annotate raw transactions with cost-type percentages and aggregate to monthly data.
# Edit INPUT_PATH and OUTPUT_PATH at the top of prepare_data.py if your file names differ.
python prepare_data.py
```

Outputs (paths configurable in the script):
- `training/data/annotated_transactions.csv` — row-level, with `cost_type_1_pct … cost_type_61_pct` columns
- `training/data/monthly_aggregated.csv` — one row per (MCC, year-month)

### Step 4 — Train processing-cost models

```bash
cd training/proc_cost
python train.py
```

Artifacts are written to `ml_service/artifacts/proc_cost/<MCC>/<horizon>/`. Each MCC × horizon (1, 3, 6 months) gets its own HuberRegressor + conformal interval files.

Edit `training/proc_cost/config.py` to change which MCCs or horizons are trained.

### Step 5 — Train TPV forecast models

```bash
cd training/tpv
python train.py
```

Artifacts are written to `ml_service/artifacts/tpv/<MCC>/`. Edit `training/tpv/config.py` to change MCCs.

### Step 6 — (Optional) Seed KNN data

The KNN composite merchant endpoint requires a seed CSV loaded into PostgreSQL at startup. Place it at:

```
ml_service/data/knn_seed.csv
```

See [ml_service/data/README.md](ml_service/data/README.md) for the exact column schema. The ml-service reads this file at startup from the path set in `KNN_SEED_CSV_PATH` (`.env`).

Without this file the KNN endpoints (`/ml/getCompositeMerchant`, `/ml/getQuote`) return 400. All other features (cost forecast, TPV forecast, profit forecast) are unaffected.

### Step 7 — Start the application

```bash
# From the Handoff/ directory
cp .env.example .env      # if not already done — fill in change_me_* values
docker compose up --build -d
```

The ml-service automatically polls `ARTIFACT_POLL_INTERVAL_S` seconds (default 60) for new artifacts, so models trained while the stack is running will be picked up without a restart.

### Step 8 — Verify

```bash
# Quick smoke test — runs 13 checks against the live stack
python e2e_test.py
```

All 13 checks should pass if KNN seed data is present. Without KNN seed data, 12/13 pass (check #12 returns 400 — expected).

### Summary of outputs

| Step | Output | Consumed by |
|------|--------|-------------|
| 3 | `training/data/monthly_aggregated.csv` | Steps 4 and 5 |
| 4 | `ml_service/artifacts/proc_cost/` | ml-service `cost_forecast` module |
| 5 | `ml_service/artifacts/tpv/` | ml-service `tpv_forecast` module |
| 6 | `ml_service/data/knn_seed.csv` | ml-service `knn_rate_quote` module |

---

### Retraining on new data

Models hot-reload — you do not need to restart the stack. Simply:

1. Re-run `prepare_data.py` with updated source CSVs.
2. Re-run `training/proc_cost/train.py` and/or `training/tpv/train.py`.
3. Wait up to `ARTIFACT_POLL_INTERVAL_S` seconds for ml-service to detect new artifacts.

For full details on the training pipeline, data schemas, and change-propagation checklist, see [training/DATA_SPEC.md](training/DATA_SPEC.md).

---

## API Reference

### Backend (`/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/calculations/merchant-fee` | Calculate merchant fees from transactions |
| POST | `/calculations/desired-margin` | Calculate desired margin rate |
| POST | `/calculations/desired-margin-details` | **Full pipeline** — fee calc + 4 ML forecasts + profitability |
| POST | `/transactions/upload` | Upload transaction CSV/Excel |
| GET | `/transactions` | List transactions (paginated, filterable by merchant) |
| GET | `/merchants` | List merchants |
| GET | `/merchants/{id}` | Get merchant by ID |
| POST | `/merchants` | Create merchant |
| GET | `/mcc-codes` | List MCC codes |
| GET | `/mcc-codes/search` | Search MCC codes |
| GET | `/mcc-codes/{code}` | Get MCC code details |

### ML Service (`/ml`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/process` | Orchestrator — runs rate opt → TPV → KNN engines |
| POST | `/rate-optimisation` | Rate optimisation engine |
| POST | `/tpv-prediction` | TPV prediction engine |
| POST | `/knn-rate-quote` | KNN rate quote engine |
| POST | `/getQuote` | Match 5 similar merchants, return cost history |
| POST | `/getCompositeMerchant` | Match 5 similar merchants, return composite features |
| GET | `/cost-forecast/health` | Processing-cost forecast health check |
| POST | `/GetCostForecast` | Monthly processing-cost forecast (conformal intervals) |
| POST | `/GetTPVForecast` | Conformal TPV forecast |
| POST | `/GetVolumeForecast` | SARIMAX weekly volume forecast |
| POST | `/GetProfitForecast` | Monte Carlo profit simulation |

---

## Key Data Assets

| Asset | Location | Description |
|-------|----------|-------------|
| Application + KNN data | PostgreSQL `mldb` | Merchants, transactions, calculation results, KNN seed table |
| Processing-cost models | `ml_service/artifacts/proc_cost/` | HuberRegressor + conformal intervals per MCC (4121, 5411, 5499, 5812) × horizon (1, 3, 6 months) |
| TPV forecast models | `ml_service/artifacts/tpv/` | TPV models per MCC (4121, 5411, 5499, 5812) |
| Fee schedules | `cost_structure/*.JSON` | Visa & Mastercard card-level and network-level fees |
| Cost type reference | `cost_structure/cost_type_id.csv` | Maps cost type IDs 1–61 to fee line items; consumed by training pipeline |
| KNN seed data | `ml_service/data/knn_seed.csv` | Processed transactions seeded into PostgreSQL at startup (not included) |

---

## Notes

- **Processing-cost forecast fallback:** Without artifacts in `ml_service/artifacts/proc_cost/`, the ml-service falls back to `base_cost_rate` from the fee-schedule JSONs with drift factors. Train and deploy artifacts to get conformal interval forecasts.
- **Cost forecast interpolation:** 3 monthly forecast points are interpolated into 12 weekly points to align with the SARIMAX volume forecast horizon.
- **Port configurability:** All Dockerfiles use shell-form `CMD` so `${VAR:-default}` env vars expand at container startup. nginx reads from `nginx/default.conf.template` (processed by the official nginx `envsubst` entrypoint) — nginx’s own variables (`$host`, `$scheme`, `$remote_addr`, etc.) are lowercase and unbraced and are not affected by envsubst.
- **Archive folder:** Contains dead/legacy code preserved for reference.

---

## Backend Integration Tests

Integration tests live under `backend/tests/integration/` and use an isolated SQLite database with FastAPI dependency overrides.

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

---

## End-to-End Live Test

`e2e_test.py` tests the full running stack through nginx. Run it after `docker compose up --build -d`:

```bash
# Requires httpx
pip install httpx

python e2e_test.py
```

### What is covered (13 checks)

| # | Endpoint | Expected |
|---|----------|----------|
| 1 | `POST /api/v1/merchants` | 201 |
| 2 | `GET  /api/v1/merchants/:id` | 200 |
| 3 | `GET  /api/v1/merchants` | 200 |
| 4 | `POST /api/v1/transactions/upload` (CSV) | 200, stored=5 |
| 5 | `GET  /api/v1/transactions` | 200, count=5 |
| 6 | `POST /api/v1/calculations/merchant-fee` | 200 |
| 7 | `GET  /api/v1/docs` (Swagger UI) | 200 |
| 8 | `GET  /ml/cost-forecast/health` | 200 |
| 9 | `GET  /ml/docs` (Swagger UI) | 200 |
| 10 | `POST /ml/GetCostForecast` | 200 |
| 11 | `POST /ml/GetTPVForecast` | 200 |
| 12 | `POST /ml/getCompositeMerchant` | 400 (expected — no KNN seed data present) |
| 13 | `POST /ml/GetProfitForecast` | 200 |

> **Check #12:** Returns 400 when `ml_service/data/knn_seed.csv` is absent. Place the seed CSV and restart the stack to enable KNN. See [ml_service/data/README.md](ml_service/data/README.md) for the required column schema.
