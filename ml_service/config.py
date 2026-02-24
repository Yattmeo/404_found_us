import os


class MLConfig:
    # PostgreSQL — shared with the main backend (same Postgres instance, same DB)
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        "postgresql://pguser:pgpassword@postgres:5432/mldb",
    )

    # Vector dimension for merchant embeddings stored in pgvector.
    # Change this when you finalise the feature vector size in the
    # Cluster Generation Engine.
    # ── WHERE TO EDIT ──────────────────────────────────────────────
    # ml_service/modules/cluster_generation/service.py  →  _build_feature_vector()
    # ml_service/models.py                             →  MerchantClusterVector.embedding
    VECTOR_DIM: int = int(os.environ.get("VECTOR_DIM", "8"))

    # Service port
    PORT: int = int(os.environ.get("ML_PORT", "8001"))
