"""
Seed knn_transactions from a reference CSV for the POC demo.

Runs once on startup when the table is empty.  The CSV is expected at
/data/processed_transactions_4mcc.csv inside the container (mounted via
docker-compose volume).

In production this seed script would be removed entirely — the KNN service
would query the live merchant transaction database directly.

Usage:
    Called automatically from app.py lifespan.
    Manual: docker compose exec ml-service python seed_knn_data.py
"""
from __future__ import annotations

import logging
import os
import time

import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

DEFAULT_CSV_PATH = "/data/processed_transactions_4mcc.csv"
CHUNK_SIZE = 50_000
DB_COLS = [
    "transaction_id", "merchant_id", "mcc", "card_brand",
    "card_type", "date", "amount", "proc_cost", "cost_type_id",
]


def seed_knn_transactions(database_url: str | None = None) -> bool:
    """
    Load reference transactions into knn_transactions if the table is empty.

    Returns True if data was seeded, False if skipped (already populated).
    """
    db_url = database_url or os.environ.get(
        "DATABASE_URL",
        "postgresql://pguser:pgpassword@postgres:5432/mldb",
    )
    csv_path = os.environ.get("KNN_SEED_CSV_PATH", DEFAULT_CSV_PATH)

    if not os.path.isfile(csv_path):
        logger.warning("[KNN Seed] CSV not found at %s — skipping seed", csv_path)
        return False

    engine = create_engine(db_url)

    with engine.connect() as conn:
        row_count = conn.execute(
            text("SELECT count(*) FROM knn_transactions")
        ).scalar()

    if row_count and row_count > 0:
        logger.info(
            "[KNN Seed] knn_transactions already has %s rows — skipping",
            f"{row_count:,}",
        )
        return False

    logger.info("[KNN Seed] Loading %s ...", csv_path)
    t0 = time.time()
    total = 0

    for chunk in pd.read_csv(csv_path, chunksize=CHUNK_SIZE):
        chunk.rename(columns={"cost_type_ID": "cost_type_id"}, inplace=True)
        chunk["cost_type_id"] = (
            pd.to_numeric(chunk["cost_type_id"], errors="coerce")
            .fillna(1)
            .astype(int)
        )
        cols = [c for c in DB_COLS if c in chunk.columns]
        chunk[cols].to_sql(
            "knn_transactions",
            engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=5000,
        )
        total += len(chunk)
        if total % 500_000 < CHUNK_SIZE:
            logger.info("[KNN Seed]   %s rows loaded ...", f"{total:,}")

    # Populate cost type reference table
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM knn_cost_type_ref"))
        conn.execute(text("""
            INSERT INTO knn_cost_type_ref (cost_type_id)
            SELECT DISTINCT cost_type_id FROM knn_transactions
            ORDER BY cost_type_id
        """))

    elapsed = time.time() - t0
    logger.info(
        "[KNN Seed] Done — %s rows loaded in %.1fs",
        f"{total:,}", elapsed,
    )

    # Log summary
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT mcc, count(*), count(DISTINCT merchant_id) "
            "FROM knn_transactions GROUP BY mcc ORDER BY mcc"
        )).fetchall()
        for mcc, cnt, merchants in rows:
            logger.info(
                "[KNN Seed]   MCC %s: %s rows, %s merchants",
                mcc, f"{cnt:,}", f"{merchants:,}",
            )

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_knn_transactions()
