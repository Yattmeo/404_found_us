"""
SQLAlchemy ORM models for the ML microservice.

── KNN RATE QUOTE TABLES ─────────────────────────────────────────────────────
knn_transactions   — historical transaction rows migrated from SQLite
knn_cost_type_ref  — lookup table of known cost_type_id values

These tables are populated once by running:
    docker compose exec ml-service python migrate_sqlite_to_postgres.py

── WHERE TO EDIT ─────────────────────────────────────────────────────────────
• Add extra columns here if your engines require additional metadata.
"""
from __future__ import annotations

from sqlalchemy import Column, Float, Integer, String

from database import Base


class KNNTransaction(Base):
    """One row per historical transaction used by the KNN Rate Quote Engine."""
    __tablename__ = "knn_transactions"

    id          = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(String, nullable=True, index=True)
    date        = Column(String, nullable=False)
    amount      = Column(Float, nullable=True)
    proc_cost   = Column(Float, nullable=True)
    cost_type_id = Column(Integer, nullable=True)
    card_type   = Column(String, nullable=True)


class KNNCostTypeRef(Base):
    """Lookup table of valid cost_type_id values for the KNN engine."""
    __tablename__ = "knn_cost_type_ref"

    id           = Column(Integer, primary_key=True, index=True)
    cost_type_id = Column(Integer, nullable=False)
