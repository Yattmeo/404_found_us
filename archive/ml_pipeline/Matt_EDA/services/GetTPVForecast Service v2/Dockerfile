# GetTPVForecast Service
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py models.py service.py app.py train.py ./

RUN mkdir -p /app/artifacts

EXPOSE 8093

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8093"]
