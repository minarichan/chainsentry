FROM node:20-alpine AS frontend
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "from solcx import install_solc; install_solc('0.8.20')"

COPY src ./src
COPY contracts ./contracts
COPY --from=frontend /ui/dist ./frontend/dist

ENV PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SCAN_DB_PATH=/app/data/scans.sqlite \
    FRONTEND_DIST=/app/frontend/dist \
    SCAN_TIMEOUT_SEC=120

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
