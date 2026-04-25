# Production Handoff Guide — 404 Found Us

> **Audience:** Receiving engineering team responsible for deploying and maintaining this system.  
> **Date:** April 2026  

---

## System Summary

A merchant pricing intelligence platform composed of five Docker services orchestrated via `docker-compose`:

| Service | Tech | Port | Role |
|---|---|---|---|
| `nginx` | nginx:alpine | 80 | Reverse proxy / single entry point |
| `backend` | FastAPI (Python 3.9) | 8000 | Fee calculation, merchant CRUD, CSV processing |
| `ml-service` | FastAPI (Python 3.11) | 8001 | KNN rate quoting, TPV/cost/profit forecasting |
| `frontend` | React CRA (Node 18) | 3000 | Sales team portal |
| `merchant-frontend` | Vite + React + TS (Node 18) | 3001 | Merchant-facing quotation portal |
| `postgres` | PostgreSQL 16 | 5432 | Shared database |

Entry points served through nginx:
- `/sales/` → Sales frontend  
- `/merchant/` → Merchant frontend  
- `/api/v1/` → Backend API (Swagger at `/api/v1/docs`)  
- `/ml/` → ML service (Swagger at `/ml/docs`)

---

## What Works Now

- Full Docker Compose stack runs with a single `docker compose up --build`
- Modular ML engine: each ML capability (KNN, TPV, cost, profit, volume forecast) lives in its own subfolder under `ml_service/modules/`
- Backend modules cleanly separated under `backend/modules/` (cost_calculation, merchant_quote)
- Fee structures (Visa/Mastercard interchange + network) are JSON files in `cost_structure/` — no hardcoded rates
- Swagger/OpenAPI docs auto-generated for both API services
- One integration test suite exists for the backend (`backend/tests/`)
- Model artifacts stored under `ml_service/artifacts/` (committed to repo — see note below)

---

## What Must Be Done Before Handoff / Production Deployment

### 1. Security — Critical

**a. Rotate all hardcoded credentials**

The following are exposed in source and must be replaced with environment-injected secrets before any deployment:

| Location | Issue |
|---|---|
| `docker-compose.yml` lines 6–7 | `POSTGRES_USER=pguser`, `POSTGRES_PASSWORD=pgpassword` in plaintext |
| `ml_service/app.py` line 57 | Hardcoded fallback DB URL with `pgpassword` |
| `ml_service/config.py` line 8 | Same hardcoded fallback |
| `ml_service/seed_knn_data.py` line 42 | Same hardcoded fallback |
| `backend/database.py` line 12 | Hardcoded fallback DB URL |
| `backend/config.py` line 6 | Fallback `SECRET_KEY = 'dev-secret-key-change-in-production'` |

**Action:** Create a `.env` file (never committed) and load it via `docker-compose`. Use Docker secrets or a secrets manager (AWS Secrets Manager, Vault, etc.) in production.

```env
# .env (never commit this)
POSTGRES_USER=<strong-user>
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=mldb
SECRET_KEY=<cryptographically-random-string>
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
ML_SERVICE_URL=http://ml-service:8001
```

**b. Lock down CORS**

Both `backend/app.py` and `ml_service/app.py` have `allow_origins=["*"]`. In production, restrict to the actual frontend domains.

```python
# backend/app.py and ml_service/app.py
allow_origins=["https://yourdomain.com", "https://merchant.yourdomain.com"],
```

**c. Confirm `backend/config.py` is actually used**

`config.py` defines `ProductionConfig` with `SECRET_KEY` validation, but `app.py` does not read from it — CORS and app settings are set directly. Verify this config class is wired up or remove it to avoid confusion.

---

### 2. Frontend Build — Currently Running in Dev Mode

**Critical:** `frontend` (React CRA) is running `npm start` (development server) inside Docker. This is not suitable for production.

**Action:** Add a production build stage to `frontend/Dockerfile`, mirroring what `merchant-frontend` already does correctly:

```dockerfile
# frontend/Dockerfile — replace current content
FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:18-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/build ./build
EXPOSE 3000
CMD ["serve", "-s", "build", "-l", "3000", "--single"]
```

Also update `frontend/.env.example` — it still references a Flask URL (`localhost:5000`). Correct value is `http://localhost/api/v1`.

---

### 3. Environment Configuration — Missing `.env` for ml-service and merchant-frontend

Only `backend/` and `frontend/` have `.env.example` files. Create equivalent files for:
- `ml_service/.env.example`
- `merchant-frontend/.env.example` (if it calls the backend directly)

---

### 4. Database — No Migration System

Tables are created via `Base.metadata.create_all()` at startup. This works for initial setup but makes schema changes in production dangerous (no rollback, no audit trail).

**Action:** Introduce [Alembic](https://alembic.sqlalchemy.org/) for the backend and ml_service databases. Minimum viable setup:

```bash
cd backend && pip install alembic && alembic init migrations
```

This is the most significant structural gap for long-term maintainability.

---

### 5. Model Artifacts — Brittle Volume-Mount Path

`docker-compose.yml` mounts a KNN training CSV from a deeply nested path:

```yaml
- ./ml_pipeline/Matt_EDA/services/KNN Quote Service Production/processed_transactions_4mcc.csv:/data/...
```

This path contains spaces and is tied to the original developer's folder structure. If this file is absent, the ML service starts in degraded mode without a clear user-facing error.

**Actions:**
- Move `processed_transactions_4mcc.csv` to a stable, clean path (e.g., `ml_service/data/knn_seed.csv`)
- Update the volume mount and `seed_knn_data.py` to reference the new path
- Add a startup health check that explicitly fails if the seed data is missing and the KNN table is empty

---

### 6. `archive/` Directory — Remove Before Handoff

`archive/` contains old implementations, draft notebooks, and superseded service code. It creates confusion about which code is canonical and inflates the repo size.

**Action:** Delete `archive/` entirely before handing off the repo. Retain history in git if needed (`git log` will preserve it).

---

### 7. `backend/requirements.txt` — Spurious Dependency

`wandb` (Weights & Biases, an ML experiment-tracking library) is listed as a backend dependency. The backend has no ML training code. This adds ~100MB to the Docker image for no reason.

**Action:** Remove `wandb` from `backend/requirements.txt`.

Also pin `backend` to Python 3.11 (matching `ml_service`) for consistency and to get security patches.

---

### 8. Python Version Inconsistency

`backend/Dockerfile` uses `python:3.9-slim` while `ml_service/Dockerfile` uses `python:3.11-slim`. Standardise on 3.11 for both.

---

### 9. Testing Coverage

Only one integration test file exists (`backend/tests/integration/test_api_integration.py`). There are no tests for:
- ML service endpoints
- The cost calculation module
- Frontend components

**Action:** At minimum, add smoke tests for each ML endpoint and the cost calculation pipeline before handoff, so the receiving team has a baseline to validate changes against.

---

### 10. Nginx — HTTPS

The current nginx config only handles HTTP on port 80. For any real deployment:
- Add TLS termination (Let's Encrypt via Certbot, or offload to a load balancer/CDN)
- Redirect HTTP → HTTPS

---

## Deployment Checklist (Quick Reference)

```
[ ] Create .env file with all secrets (never commit)
[ ] Replace CORS allow_origins=["*"] with actual domain
[ ] Rebuild frontend with production Dockerfile
[ ] Remove archive/ directory
[ ] Remove wandb from backend/requirements.txt
[ ] Move KNN seed CSV to a clean path with no spaces
[ ] Initialise Alembic for DB migrations
[ ] Add TLS to nginx for any public-facing deployment
[ ] Run docker compose up --build and hit /api/v1/docs and /ml/docs to confirm both Swagger UIs load
[ ] Run backend test suite: docker compose exec backend pytest
```

---

## Assumptions Made

1. The receiving company will manage their own infrastructure (cloud provider, domain, TLS certificates). This guide focuses on the application layer only.
2. The PostgreSQL database is not pre-populated — the `seed_knn_data.py` script handles initial KNN data seeding from the CSV on first startup.
3. Model artifacts in `ml_service/artifacts/` are the trained, production-ready models. No retraining is required before first deployment.
4. The `ml_pipeline/` directory (training notebooks, EDA) is reference material for the data science work and is not part of the running system — it does not need to be deployed.
5. `Amex` and `Discover` card types have no fee structure JSONs; this is intentional — the system currently only supports Visa and Mastercard interchange calculation.
6. The `config.py` in the backend is a legacy Flask-style config that was partially migrated to FastAPI. It is not the source of truth for current runtime settings.
