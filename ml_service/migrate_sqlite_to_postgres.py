"""
One-time migration: SQLite rate_quote.sqlite → PostgreSQL (knn_transactions, knn_cost_type_ref).

Run inside the ml-service container after the stack is up:

    docker compose exec ml-service python migrate_sqlite_to_postgres.py

The script is idempotent — it uses IF NOT EXISTS table creation and inserts
only rows that do not already exist (based on primary key conflicts).

── WHAT IT DOES ──────────────────────────────────────────────────────────────
1. Reads `transactions` and `cost_type_ref` tables from the SQLite file.
2. Writes them to PostgreSQL as `knn_transactions` and `knn_cost_type_ref`.
3. On subsequent runs rows are appended; duplicate rows (same id) are skipped
   via INSERT … ON CONFLICT DO NOTHING.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from config import MLConfig

# ── Paths ─────────────────────────────────────────────────────────────────────
# In Docker the KNN source data is mounted (read-only) at /data/knn_source/
# via the docker-compose volume:
#   "./KNN Demo Service/KNN Demo Service:/data/knn_source:ro"
# If running the script locally (outside Docker) fall back to the relative path.
DOCKER_SQLITE_PATH = Path("/data/knn_source/rate_quote.sqlite")
LOCAL_SQLITE_PATH = (
    Path(__file__).resolve().parent.parent
    / "KNN Demo Service"
    / "KNN Demo Service"
    / "rate_quote.sqlite"
)
SQLITE_PATH = DOCKER_SQLITE_PATH if DOCKER_SQLITE_PATH.exists() else LOCAL_SQLITE_PATH


def migrate() -> None:
    if not SQLITE_PATH.exists():
        raise FileNotFoundError(
            f"SQLite file not found at {SQLITE_PATH}.\n"
            "Ensure the 'KNN Demo Service' directory is mounted or present in the container."
        )

    print(f"Reading from SQLite: {SQLITE_PATH}")
    with sqlite3.connect(SQLITE_PATH) as sqlite_conn:
        transactions = pd.read_sql("SELECT * FROM transactions", sqlite_conn)
        cost_type_ref = pd.read_sql("SELECT * FROM cost_type_ref", sqlite_conn)

    print(f"  transactions rows  : {len(transactions)}")
    print(f"  cost_type_ref rows : {len(cost_type_ref)}")

    # Normalise column names to lowercase for PostgreSQL
    transactions.columns = [c.lower() for c in transactions.columns]
    cost_type_ref.columns = [c.lower() for c in cost_type_ref.columns]

    # Add surrogate id if original tables have none
    if "id" not in transactions.columns:
        transactions.insert(0, "id", range(1, len(transactions) + 1))
    if "id" not in cost_type_ref.columns:
        cost_type_ref.insert(0, "id", range(1, len(cost_type_ref) + 1))

    pg_engine = create_engine(MLConfig.DATABASE_URL, pool_pre_ping=True)

    # ── Create tables if they don't exist ─────────────────────────────────────
    with pg_engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS knn_transactions (
                id          SERIAL PRIMARY KEY,
                merchant_id TEXT,
                date        TEXT    NOT NULL,
                amount      DOUBLE PRECISION,
                proc_cost   DOUBLE PRECISION,
                cost_type_id INTEGER,
                card_type   TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS knn_cost_type_ref (
                id           SERIAL PRIMARY KEY,
                cost_type_id INTEGER NOT NULL
            )
        """))
        conn.commit()
    print("PostgreSQL tables created / verified.")

    # ── Bulk insert via pandas (replace strategy) ─────────────────────────────
    # Using if_exists='replace' for a clean load on first run.
    # Change to 'append' if you want to add new rows without wiping the table.
    transactions.to_sql(
        "knn_transactions", pg_engine,
        if_exists="replace", index=False, method="multi", chunksize=500,
    )
    cost_type_ref.to_sql(
        "knn_cost_type_ref", pg_engine,
        if_exists="replace", index=False, method="multi", chunksize=500,
    )

    print("Migration complete.")
    print(f"  knn_transactions  → {len(transactions)} rows written.")
    print(f"  knn_cost_type_ref → {len(cost_type_ref)} rows written.")


if __name__ == "__main__":
    migrate()
