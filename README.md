# 404_found_us
FYP2026

---

## Project Structure

```
404_found_us/
├── backend/              FastAPI backend — cost calculation, merchant quotes
├── frontend/             React frontend
├── ml_service/           ML microservice — Rate Optimisation, TPV Prediction, KNN Rate Quote
├── nginx/                Reverse proxy config
├── cost_structure/       Visa/Mastercard card & network fee JSON files
├── input_files/          Sample transaction CSV files
├── ml_pipeline/          EDA notebooks and modelling analysis
├── KNN Demo Service/     ⚠️  See note below — do not delete
└── docker-compose.yml
```

---

## Getting Started

```bash
docker compose up --build -d
```

On first run (or whenever the KNN reference data needs refreshing), seed the database:

```bash
docker compose exec ml-service python migrate_sqlite_to_postgres.py
```

---

## Important: KNN Demo Service folder

The `KNN Demo Service/KNN Demo Service/` directory **must be kept** for two reasons:

1. **`rate_quote.sqlite`** — This is the source dataset for the KNN Rate Quote Engine. The migration script reads from it to populate the `knn_transactions` and `knn_cost_type_ref` tables in PostgreSQL.
2. **Docker volume mount** — `docker-compose.yml` mounts this folder read-only into the `ml-service` container at `/data/knn_source`. Removing the folder without removing that line will cause `docker compose up` to fail.

The other files in the folder (original service code, tests) are superseded by `ml_service/modules/knn_rate_quote/` and can be ignored.

---

## Important: migrate_sqlite_to_postgres.py

`ml_service/migrate_sqlite_to_postgres.py` is **not part of the application startup** — it is a one-off data tool. Run it when:

- Setting up the project on a new machine or fresh database
- The `KNN Demo Service/KNN Demo Service/rate_quote.sqlite` file has been updated with new transaction data
- The `knn_transactions` or `knn_cost_type_ref` tables are missing or need to be rebuilt

```bash
docker compose exec ml-service python migrate_sqlite_to_postgres.py
```

The script is safe to re-run — it uses `if_exists="replace"` so it will overwrite existing data with the latest SQLite contents.

---

## API Endpoints

| Service | Base URL | Docs |
|---|---|---|
| Backend | `http://localhost/api/v1` | `http://localhost/api/docs` |
| ML Service | `http://localhost/ml` | `http://localhost/ml/docs` |

### Key ML endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/ml/knn-rate-quote` | KNN Rate Quote Engine — forecast processing cost |
| `POST` | `/ml/rate-optimisation` | Rate Optimisation Engine |
| `POST` | `/ml/tpv-prediction` | TPV Prediction Engine |
| `POST` | `/ml/process` | Runs all three engines in sequence |
