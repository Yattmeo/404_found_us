"""
PostgreSQL connection for the ML microservice.

pgvector is enabled on the same Postgres instance used by the main backend.
The `vector` extension is available because the image is pgvector/pgvector:pg16.

── WHERE CLUSTER DATA IS STORED ─────────────────────────────────────────────
Table: merchant_cluster_vectors   (see models.py → MerchantClusterVector)
Table: cluster_centroids          (see models.py → ClusterCentroid)

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
    """Create all tables (including pgvector ones) on first startup."""
    from sqlalchemy import text
    # Enable pgvector extension before any table creation
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    # Register pgvector types with SQLAlchemy
    from pgvector.sqlalchemy import Vector  # noqa: F401 — side-effect import
    import models  # noqa: F401 — registers all ORM classes with Base
    Base.metadata.create_all(bind=engine)
