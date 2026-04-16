# 404 Found Us — FYP 2026

Merchant pricing intelligence platform. Calculates interchange & network fees, forecasts processing costs and transaction volumes, and recommends optimal merchant rates.

> Full architecture diagrams (Mermaid) are in [ARCHITECTURE.md](ARCHITECTURE.md).

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
│ pricing   │ │ quotation    │ │ merchant  │   │ cost + vol  │
│ tools     │ │ tool         │ │ CRUD, tx  │   │ + profit    │
│           │ │              │ │ upload    │   │ forecasting │
└───────────┘ └──────────────┘ └─────┬─────┘   └──────┬──────┘
                                     │                 │
                          ┌──────────┘                 │
                          │                            │
                          ▼                            ▼
                    ┌──────────┐              ┌──────────────┐
                    │PostgreSQL│              │ Trained Model│
                    │  16      │              │ Artifacts    │
                    │ :5432    │              │              │
                    │          │              │ m9/  (cost)  │
                    │ 3.88M tx │◄─────────── │ tpv/ (volume)│
                    │ + KNN    │  shared DB   │              │
                    └──────────┘              └──────────────┘
```

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
        ├─► ML Service /ml/GetCostForecast           (M9 v2 → 3-month cost %)
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

| Container | Build Context | Internal Port | Purpose |
|-----------|--------------|---------------|---------|
| **ml-postgres** | `postgres:16` | 5432 | PostgreSQL 16 — all application data & KNN tables |
| **ml-backend** | `./backend` | 8000 | FastAPI — fee calculation, merchant CRUD, tx upload, ML orchestration |
| **ml-frontend** | `./frontend` | 3000 | React CRA — Sales pricing tools (served at `/sales`) |
| **ml-merchant-frontend** | `./merchant-frontend` | 3001 | Vite + React + TS — Online quotation tool (served at `/merchant`) |
| **ml-nginx** | `nginx:alpine` | **80** | Reverse proxy — sole public port |
| **ml-service** | `./ml_service` | 8001 | FastAPI — KNN rate quoting, cost/volume/profit/TPV forecasting |

---

## Project Structure

```
404_found_us/
├── docker-compose.yml          Service orchestration (6 containers)
├── ARCHITECTURE.md             Full architecture docs with Mermaid diagrams
├── backend/                    FastAPI backend (fee calc, merchant CRUD, ML orchestration)
│   ├── app.py                  Entry point, CORS, lifespan
│   ├── routes.py               All /api/v1 endpoints
│   ├── services.py             DataProcessing, MerchantFeeCalculation, MCC services
│   ├── models.py               ORM: transactions, merchants, calculation_results, upload_batches
│   ├── schemas.py              Pydantic request/response models
│   ├── validators.py           CSV/Excel row validation
│   └── modules/
│       ├── cost_calculation/   Interchange cost computation
│       └── merchant_quote/     Quote generation with ML pipeline
├── ml_service/                 FastAPI ML microservice
│   ├── app.py                  Entry point, initialises M9 + TPV caches
│   ├── routes.py               All /ml endpoints
│   ├── artifacts/
│   │   ├── m9/5411/{1,3,6}/    M9 v2 cost forecast models
│   │   └── tpv/{4121,5411,5499,5812}/  TPV forecast models
│   └── modules/
│       ├── knn_rate_quote/     KNN-based rate quotation (PostgreSQL-backed)
│       ├── cost_forecast/      M9 v2 artifact-based cost prediction
│       ├── tpv_forecast/       Conformal TPV prediction
│       ├── volume_forecast/    SARIMAX weekly volume forecast
│       ├── profit_forecast/    Monte Carlo profit simulation
│       ├── rate_optimisation/  Rate optimisation engine
│       └── tpv_prediction/     TPV prediction engine
├── frontend/                   React CRA — Sales calculator UI (served at /sales)
├── merchant-frontend/          Vite + React + TS — Merchant quotation UI (served at /merchant)
├── nginx/                      Reverse proxy config (default.conf)
├── cost_structure/             Visa & Mastercard fee schedule JSONs (mounted ro)
├── data/                       Sample/test CSV datasets
└── archive/                    Archived dead/legacy code
```

---

## Getting Started

```bash
# Start all services
docker compose up --build -d
```

KNN transaction data (~3.88M rows) is already seeded in PostgreSQL. No additional migration steps required.

| URL | What |
|-----|------|
| http://localhost/sales/ | Sales pricing tools |
| http://localhost/merchant/ | Online quotation tool |
| http://localhost/api/v1/docs | Backend API docs (Swagger) |
| http://localhost/ml/docs | ML Service API docs (Swagger) |

---

## API Reference

### Backend (`/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/calculations/transaction-costs` | Interchange & network cost enrichment (streams CSV) |
| POST | `/calculations/merchant-fee` | Calculate merchant fees from transactions |
| POST | `/calculations/desired-margin` | Calculate desired margin rate |
| POST | `/calculations/desired-margin-details` | **Full pipeline** — fee calc + 4 ML forecasts + profitability |
| POST | `/transactions/upload` | Upload transaction CSV/Excel |
| GET | `/transactions` | List transactions (paginated) |
| GET | `/transactions/{id}` | Get transaction by ID |
| POST | `/projections/revenue` | ML-driven revenue projection |
| POST | `/merchant-quote` | Generate merchant quote with ML insights |
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
| GET | `/cost-forecast/health` | M9 v2 cost forecast health check |
| POST | `/GetCostForecast` | M9 v2 monthly cost forecast (conformal intervals) |
| POST | `/GetTPVForecast` | Conformal TPV forecast |
| POST | `/GetVolumeForecast` | SARIMAX weekly volume forecast |
| POST | `/GetProfitForecast` | Monte Carlo profit simulation |

---

## Key Data Assets

| Asset | Location | Description |
|-------|----------|-------------|
| Transaction + KNN data | PostgreSQL `mldb` | ~3.88M KNN rows + application tables |
| M9 cost models | `ml_service/artifacts/m9/` | HuberRegressor + conformal interval artifacts per MCC/horizon |
| TPV forecast models | `ml_service/artifacts/tpv/` | Trained TPV models per MCC |
| Fee schedules | `cost_structure/*.JSON` | Visa & Mastercard card-level and network-level fees |

---

## Notes

- **All data lives in PostgreSQL** — KNN data was migrated from SQLite and is now served entirely from `mldb`.
- **M9 cost forecast** loads pre-trained artifacts from `ml_service/artifacts/m9/`. Without artifacts it falls back to `base_cost_rate` from fee-schedule JSONs with drift factors.
- **Cost forecast** interpolates 3 monthly M9 forecasts into 12 weekly points to match the SARIMAX volume forecast horizon.
- **Archive folder** contains dead/legacy code preserved for reference — see `archive/` for details.
- Browser-friendly diagram pack: [presentation/index.html](presentation/index.html)

Quick local preview:

```bash
python -m http.server 8000
```

Then open: `http://localhost:8000/presentation/index.html`

Current `/sales` probability chart behavior:

- Chart title: `Probability of Profitability`
- Y-axis fixed to `0%` to `100%`
- Curve approaches an asymptote at `97.5%` (does not touch `100%`)
- Current rate (if provided) and suggested rate shown as vertical marker lines
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
