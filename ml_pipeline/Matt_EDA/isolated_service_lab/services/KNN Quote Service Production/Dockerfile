# ---------------------------------------------------------------------------
# KNN Quote Service – Production Image
# ---------------------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies first (layer-cached unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (tests excluded via .dockerignore)
COPY app.py feature_engineering.py models.py processing_costs.py repository.py service.py ./

# Mount point for the SQLite database.
# Set TRANSACTIONS_AND_COST_TYPE_DB_PATH at runtime to the full path of your DB file inside the container.
VOLUME ["/data"]

# Supply exactly ONE of the following at runtime:
#   DB_CONNECTION_STRING  – SQLAlchemy URL for any external database
#                           e.g. postgresql://user:pass@host:5432/dbname
#   TRANSACTIONS_AND_COST_TYPE_DB_PATH – full path to a local SQLite file inside the container
ENV DB_CONNECTION_STRING="" \
    TRANSACTIONS_AND_COST_TYPE_DB_PATH=""

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
