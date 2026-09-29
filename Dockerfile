# akirs-auto — API + Celery worker image
# Python 3.13 + Playwright (Chromium) + all runtime deps.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# System libs Chromium needs at runtime + curl for healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Python deps (project itself is NOT pip-installed; `src/`, `backend/`,
# `chatbot/` are copied in below and imported via PYTHONPATH=/app/src).
# Includes the `chatbot` extra since CHATBOT_ENABLED=true in production.
COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache \
        fastapi "uvicorn[standard]" pydantic pydantic-settings \
        "sqlalchemy[asyncio]" aiosqlite alembic \
        "celery[redis]" redis httpx beautifulsoup4 \
        "pydantic-ai-slim[openai]" "starlette-admin>=1.0.1" itsdangerous \
        playwright watchdog \
        chromadb sentence-transformers tiktoken rapidfuzz

# Browser runtime (worker + any in-process scraping).
RUN playwright install chromium

# App source. `src/` is a pythonpath root; `backend/` and `chatbot/` are
# top-level packages imported by `backend.main:app`. `UserInterface/` is the
# static UI mounted at /ui.
COPY src/ ./src/
COPY backend/ ./backend/
COPY chatbot/ ./chatbot/
COPY UserInterface/ ./UserInterface/
COPY main.py ./

# Persistent state (SQLite DB, CSV exports, browser profile, ChromaDB data).
# Mounted as a named volume by docker-compose / Coolify.
RUN mkdir -p /data /data/output /data/chatbot_data /app/.akirs-browser
VOLUME ["/data"]

EXPOSE 8000

# Default: run the API. Compose overrides this for the worker.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
