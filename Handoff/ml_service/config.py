import os


class MLConfig:
    # PostgreSQL — shared with the main backend (same Postgres instance, same DB)
    # Must be provided via DATABASE_URL environment variable.
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

    # Service port
    PORT: int = int(os.environ.get("ML_PORT", "8001"))
