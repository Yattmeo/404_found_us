# GetM9MonthlyCostForecast Service
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code (train.py included for convenience; not needed at runtime)
COPY config.py models.py service.py app.py train.py ./

# Artifacts are mounted as a host volume so the cron-driven train.py writes
# are immediately visible inside the container without a rebuild.
# The directory is pre-created so Docker does not create it as root-owned.
RUN mkdir -p /app/artifacts

EXPOSE 8092

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8092"]
