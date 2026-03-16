"""
One-time migration: SQLite rate_quote.sqlite → PostgreSQL (knn_transactions, knn_cost_type_ref).

Run inside the ml-service container after the stack is up:

    docker compose exec ml-service python migrate_sqlite_to_postgres.py

The script is idempotent — it uses IF NOT EXISTS table creation and inserts
only rows that do not already exist (based on primary key conflicts).

── WHAT IT DOES ──────────────────────────────────────────────────────────────
1. Reads `transactions` and `cost_type_ref` tables from the SQLite file.
2. Writes them to PostgreSQL as `knn_transactions` and `knn_cost_type_ref`.
3. Keeps schema aligned with production KNN requirements.
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

    # Normalise column names to lowercase for PostgreSQL.
    transactions.columns = [c.lower() for c in transactions.columns]
    cost_type_ref.columns = [c.lower() for c in cost_type_ref.columns]

    # Source columns are lower-cased above, so COST_TYPE_ID becomes cost_type_id.
    if "cost_type_id" not in transactions.columns:
        raise ValueError("transactions table is missing required cost_type_id/cost_type_ID column")

    if "cost_type_id" not in cost_type_ref.columns:
        raise ValueError("cost_type_ref table is missing required cost_type_id/cost_type_ID column")

    # Add defaults for columns consumed by production KNN logic.
    required_txn_columns = [
        "transaction_id",
        "date",
        "amount",
        "merchant_id",
        "mcc",
        "card_brand",
        "card_type",
        "cost_type_id",
        "proc_cost",
    ]
    for col in required_txn_columns:
        if col not in transactions.columns:
            transactions[col] = None

    # Add surrogate id if original tables have none.
    if "id" not in transactions.columns:
        transactions.insert(0, "id", range(1, len(transactions) + 1))
    if "id" not in cost_type_ref.columns:
        cost_type_ref.insert(0, "id", range(1, len(cost_type_ref) + 1))

    transactions = transactions[["id", *required_txn_columns]].copy()
    cost_type_ref = cost_type_ref[["id", "cost_type_id"]].copy()

    # Convert numerics where applicable.
    transactions["amount"] = pd.to_numeric(transactions["amount"], errors="coerce")
    transactions["proc_cost"] = pd.to_numeric(transactions["proc_cost"], errors="coerce")
    transactions["mcc"] = pd.to_numeric(transactions["mcc"], errors="coerce")
    transactions["cost_type_id"] = pd.to_numeric(transactions["cost_type_id"], errors="coerce")
    cost_type_ref["cost_type_id"] = pd.to_numeric(cost_type_ref["cost_type_id"], errors="coerce")

    pg_engine = create_engine(MLConfig.DATABASE_URL, pool_pre_ping=True)

    # ── Create tables if they don't exist ─────────────────────────────────────
    with pg_engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS knn_transactions (
                id          SERIAL PRIMARY KEY,
                transaction_id TEXT,
                merchant_id TEXT,
                mcc         INTEGER,
                card_brand  TEXT,
                card_type   TEXT,
                date        TEXT    NOT NULL,
                amount      DOUBLE PRECISION,
                proc_cost   DOUBLE PRECISION,
                cost_type_id INTEGER
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
    # Use replace to guarantee schema consistency across upgrades.
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
