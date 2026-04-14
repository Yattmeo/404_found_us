# ML Service

FastAPI microservice (`ml-service:8001`) — KNN rate quoting, cost/volume/profit forecasting, and Monte Carlo simulation.

> Part of the **404 Found Us** platform. See the [root README](../README.md) for the full architecture.

---

## Endpoints

All endpoints are prefixed with `/ml` by the nginx proxy.

| Method | Path | Tag | Description |
|--------|------|-----|-------------|
| POST | `/process` | ML Orchestration | Run Rate Opt → TPV → KNN in sequence |
| POST | `/knn-rate-quote` | KNN Rate Quote | KNN-based processing cost forecast |
| POST | `/getQuote` | KNN Quote Service | Match 5 similar merchants, return cost history |
| POST | `/getCompositeMerchant` | KNN Quote Service | Match 5 merchants, return composite weekly features |
| POST | `/GetCostForecast` | Cost Forecast (M9 v2) | 3-month cost forecast (M9 monthly → weekly interpolation) |
| POST | `/GetTPVForecast` | TPV Forecast | Conformal monthly TPV prediction |
| POST | `/GetVolumeForecast` | Volume Forecast | 12-week TPV forecast (SARIMA/SARIMAX) |
| POST | `/GetProfitForecast` | Profit Forecast | Monte Carlo profit simulation (cost + TPV + fee rate + fixed fee) |
| POST | `/rate-optimisation` | Rate Optimisation | Rate optimisation engine (stub) |
| POST | `/tpv-prediction` | TPV Prediction | TPV prediction engine (stub) |
| GET | `/cost-forecast/health` | Cost Forecast (M9 v2) | M9 health check |

Swagger docs: http://localhost/ml/docs

---

## Modules

```
ml_service/modules/
├── knn_rate_quote/       ✅ Implemented — KNN, PostgreSQL-backed
├── cost_forecast/        ✅ Implemented — M9 v2 artifact-based cost prediction
├── tpv_forecast/         ✅ Implemented — Conformal TPV prediction
├── volume_forecast/      ✅ Implemented — SARIMAX weekly forecast
├── profit_forecast/      ✅ Implemented — Monte Carlo profit simulation
├── rate_optimisation/    ⬜ Stub — implement your model
└── tpv_prediction/       ⬜ Stub — implement your model
```

### Cost Forecast Pipeline

```
/ml/GetCostForecast (legacy format)
    │
    ├── Convert weekly features → monthly context (6 months)
    ├── Forward to M9 Forecast Service (:8092)
    │       └── HuberRegressor + GBR conformal intervals → 3 monthly points
    ├── Interpolate 3 months → 12 weekly points (linear, 4 wks/month)
    │
    └── Fallback (if M9 degraded): base_cost_rate with drift factors
            └── Also interpolated to 12 weekly points
```

### Volume Forecast Pipeline

```
/ml/GetVolumeForecast
    │
    ├── KNN: /getCompositeMerchant → 5 nearest merchants' weekly features
    ├── SARIMA/SARIMAX fit on composite weekly totals
    ├── Onboarding-scale adjustment (onboarding_mean / forecast_avg)
    │
    └── Returns 12 weekly TPV points with CI bands
```

---

## Database

Shares PostgreSQL (`mldb`) with the backend.

| Table | Populated by | Description |
|-------|-------------|-------------|
| `knn_transactions` | `migrate_sqlite_to_postgres.py` | Historical transaction data for KNN |
| `knn_cost_type_ref` | `migrate_sqlite_to_postgres.py` | Cost type lookup table |

### First-time setup

```bash
docker compose exec ml-service python migrate_sqlite_to_postgres.py
```

Safe to re-run — uses `if_exists="replace"`.

---

## Development

```bash
# Restart after code changes (volumes are mounted)
docker restart ml-service

# Rebuild after requirements.txt or Dockerfile changes
docker compose build ml-service --no-cache
docker compose up -d --force-recreate ml-service
```

---

## Adding a New Model (Stub Engines)

Edit only `service.py` in the target module:

```
ml_service/modules/<your_module>/
    service.py     ← your model logic here
    schemas.py     ← output fields
    controller.py  ← don't touch
```

If using a pre-trained model file, place it in `ml_service/models/` and load with `joblib.load()`.  
Add any new dependencies to `ml_service/requirements.txt` and rebuild.
