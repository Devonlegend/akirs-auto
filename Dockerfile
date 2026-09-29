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

# Python deps — installed EXACTLY as pinned in uv.lock (reproducible builds).
# `uv export` emits a requirements.txt from the lockfile (default = the
# project's base/runtime dependencies; the `dev` group is excluded). The
# chatbot RAG stack (chromadb, sentence-transformers, tiktoken, rapidfuzz) is
# part of the base deps, so it's included — matching CHATBOT_ENABLED=true in
# production. Installing from the lockfile (instead of re-resolving unpinned
# names with `uv pip install`) prevents "works locally, breaks in the
# container" dependency drift and Docker layer-cache surprises.
# The project itself is NOT installed; `src/`, `backend/`, `chatbot/` are
# copied in below and imported via PYTHONPATH=/app/src.
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && \
    uv export --frozen --no-dev --no-emit-project --no-hashes \
        -o /tmp/requirements.txt && \
    uv pip install --system --no-cache -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

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
