FROM python:3.11-slim

ARG BUILD_DATE
ENV BUILD_DATE=$BUILD_DATE

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy all project files including backend
COPY . /app

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app:/app/backend

# Note: command is provided by docker-compose
EXPOSE 8000
