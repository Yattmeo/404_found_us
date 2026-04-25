FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the uvicorn port
EXPOSE ${BACKEND_PORT:-8000}

# Default command (overridden by docker-compose with --reload for dev)
CMD uvicorn app:app --host 0.0.0.0 --port ${BACKEND_PORT:-8000}
