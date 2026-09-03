FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Gunicorn manages a pool of uvicorn workers — one process per core is the
# recommended default for production, but we start with 1 worker to keep
# memory usage low and allow horizontal scaling. Increase when needed.
#
# Shell-form CMD (no brackets) so $PORT actually gets expanded at runtime —
# cloud (and most PaaS hosts) assign a dynamic port via $PORT and route
# traffic to it; hardcoding 8000 in exec-form CMD silently breaks this,
# since exec-form never expands env vars.
CMD gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 1 \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout 30 \
    --keep-alive 5