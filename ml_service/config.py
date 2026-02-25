import os


class MLConfig:
    # PostgreSQL — shared with the main backend (same Postgres instance, same DB)
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        "postgresql://pguser:pgpassword@postgres:5432/mldb",
    )

    # Service port
    PORT: int = int(os.environ.get("ML_PORT", "8001"))
