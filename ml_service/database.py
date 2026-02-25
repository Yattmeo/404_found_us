"""
PostgreSQL connection for the ML microservice.

── WHERE KNN DATA IS STORED ──────────────────────────────────────────────────
Table: knn_transactions   (see models.py → KNNTransaction)
Table: knn_cost_type_ref  (see models.py → KNNCostTypeRef)

Populate with:  docker compose exec ml-service python migrate_sqlite_to_postgres.py

Use `db: Session = Depends(get_db)` in any route that needs DB access.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import MLConfig

engine = create_engine(MLConfig.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables on first startup."""
    import models  # noqa: F401 — registers all ORM classes with Base
    Base.metadata.create_all(bind=engine)
