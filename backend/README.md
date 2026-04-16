# Backend

FastAPI application (`backend:8000`) — interchange fee calculation, merchant CRUD, transaction uploads, and ML pipeline orchestration.

> Part of the **404 Found Us** platform. See the [root README](../README.md) for the full architecture.

---

## Endpoints

All endpoints are prefixed with `/api/v1` by the nginx proxy. Swagger docs at `/api/v1/docs`.

### Calculations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/calculations/transaction-costs` | Upload CSV → enriched CSV with interchange & network costs (streaming) |
| POST | `/calculations/merchant-fee` | Calculate current interchange rates from transactions |
| POST | `/calculations/desired-margin` | Calculate rate needed for a target margin |
| POST | `/calculations/desired-margin-details` | Full pipeline — fee calc + 4 ML forecasts + profitability curve |

### Transactions

| Method | Path | Description |
|--------|------|-------------|
| POST | `/transactions/upload` | Upload CSV/Excel with validation |
| GET | `/transactions` | List transactions (paginated) |
| GET | `/transactions/{id}` | Get transaction by ID |

### Merchants

| Method | Path | Description |
|--------|------|-------------|
| GET | `/merchants` | List merchants |
| GET | `/merchants/{id}` | Get merchant by ID |
| POST | `/merchants` | Create merchant |

### MCC Codes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/mcc-codes` | List MCC codes |
| GET | `/mcc-codes/search` | Search MCC codes |
| GET | `/mcc-codes/{code}` | Get MCC code details |

### Merchant Quote

| Method | Path | Description |
|--------|------|-------------|
| POST | `/merchant-quote` | Generate quote with ML insights (used by merchant-frontend) |

---

## Modules

```
backend/modules/
├── cost_calculation/    Interchange & network cost computation
│   ├── controller.py
│   ├── service.py
│   └── schemas.py
└── merchant_quote/      Quote generation with ML pipeline orchestration
    ├── controller.py
    ├── service.py
    └── schemas.py
```

---

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Entry point — FastAPI app, CORS, lifespan (creates DB tables on startup) |
| `config.py` | `ML_SERVICE_URL`, DB config, file upload limits |
| `database.py` | SQLAlchemy engine + session factory |
| `models.py` | ORM models: `Transaction`, `Merchant`, `CalculationResult`, `UploadBatch` |
| `routes.py` | All `/api/v1` endpoint definitions |
| `schemas.py` | Pydantic request/response models |
| `services.py` | `DataProcessingService`, `MerchantFeeCalculationService`, `MCCService` |
| `validators.py` | CSV/Excel row validation |

---

## ML Integration

The `/calculations/desired-margin-details` endpoint orchestrates 4 sequential calls to the ML service via `httpx`:

1. `POST /ml/getCompositeMerchant` — KNN: find 5 nearest merchants
2. `POST /ml/GetTPVForecast` — conformal monthly TPV prediction
3. `POST /ml/GetCostForecast` — M9 v2 3-month cost forecast
4. `POST /ml/GetProfitForecast` — Monte Carlo profit simulation

The `/calculations/transaction-costs` endpoint also triggers a background `POST /ml/process` call (rate optimisation + TPV prediction + KNN engines).

---

## Cost Structure

Reads Visa & Mastercard fee schedule JSONs from `cost_structure/` (mounted read-only in Docker):

- `visa_Card.JSON` / `visa_Network.JSON`
- `masterCard_Card.JSON` / `masterCard_Network.JSON`

---

## Development

```bash
# Restart after code changes (volumes are mounted)
docker restart ml-backend

# Rebuild after requirements.txt or Dockerfile changes
docker compose build backend --no-cache
docker compose up -d --force-recreate backend
```

---

## Testing

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Tests are under `tests/integration/` and use an isolated SQLite test database with FastAPI dependency overrides.
