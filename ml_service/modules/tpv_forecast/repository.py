"""
repository.py — Reference-data access layer for GetTPVForecast (v2).

Adapted for embedding inside ml_service. Uses the same Postgres DB
as the rest of ml_service (via DATABASE_URL).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class MerchantRepository(Protocol):
    def load_transactions(self, mcc: int, card_types: List[str]) -> pd.DataFrame: ...
    def load_cost_type_ids(self) -> List[str]: ...


@dataclass
class SQLiteMerchantRepository:
    db_path: Path

    def load_transactions(self, mcc: int, card_types: List[str]) -> pd.DataFrame:
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite DB not found: {self.db_path}")

        base_query = """
            SELECT transaction_id, date, amount, merchant_id, mcc,
                   card_brand, card_type, cost_type_ID, proc_cost
            FROM transactions
            WHERE CAST(mcc AS INTEGER) = ?
        """
        params: List[object] = [int(mcc)]

        normalized = [c.lower() for c in card_types if c.lower() != "both"]
        if normalized:
            placeholders = ", ".join(["?"] * len(normalized))
            base_query += f"""
                AND (
                    LOWER(COALESCE(card_brand, '')) IN ({placeholders})
                    OR LOWER(COALESCE(card_type, '')) IN ({placeholders})
                )
            """
            params.extend(normalized)
            params.extend(normalized)

        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql(base_query, conn, params=params)
        return df

    def load_cost_type_ids(self) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            ref = pd.read_sql("SELECT cost_type_ID FROM cost_type_ref", conn)
        return ref["cost_type_ID"].dropna().astype(int).astype(str).tolist()


@dataclass
class SQLAlchemyMerchantRepository:
    connection_string: str

    def _engine(self):
        from sqlalchemy import create_engine
        return create_engine(self.connection_string)

    def load_transactions(self, mcc: int, card_types: List[str]) -> pd.DataFrame:
        from sqlalchemy import text

        query = """
            SELECT transaction_id, date, amount, merchant_id, mcc,
                   card_brand, card_type, cost_type_ID, proc_cost
            FROM transactions
            WHERE CAST(mcc AS INTEGER) = :mcc
        """
        bind: dict = {"mcc": int(mcc)}

        normalized = [c.lower() for c in card_types if c.lower() != "both"]
        if normalized:
            placeholders = ", ".join([f":ct{i}" for i in range(len(normalized))])
            query += f"""
                AND (
                    LOWER(COALESCE(card_brand, '')) IN ({placeholders})
                    OR LOWER(COALESCE(card_type, '')) IN ({placeholders})
                )
            """
            for i, val in enumerate(normalized):
                bind[f"ct{i}"] = val

        engine = self._engine()
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=bind)
        return df

    def load_cost_type_ids(self) -> List[str]:
        from sqlalchemy import text
        engine = self._engine()
        with engine.connect() as conn:
            ref = pd.read_sql(text("SELECT cost_type_ID FROM cost_type_ref"), conn)
        return ref["cost_type_ID"].dropna().astype(int).astype(str).tolist()
