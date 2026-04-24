FROM python:3.11-slim

# System deps (psycopg2, pillow, etc. if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source - explicitly copy backend
COPY backend /app/backend

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app:/app/backend

# Note: command is provided by docker-compose
EXPOSE 8000
