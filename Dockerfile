FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SEED_PATH=/app/config/seed/v0.1.yaml
# ATLASDOCS_ENV is intentionally unset here; the runtime must supply
# development or production explicitly.

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["sh", "-c", "alembic upgrade head && atlasdocs-seed && exec uvicorn atlasdocs.main:app --host 0.0.0.0 --port 8080"]
