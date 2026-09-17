from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from chatbot.api.routes import prepare_pipeline, shutdown_pipeline
from chatbot.api.routes import router as chatbot_router
from backend.database import AsyncSessionLocal
from backend.models.embed import EmbedKey

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await prepare_pipeline()
    yield
    await shutdown_pipeline()


app = FastAPI(title="Akirs Chatbot App", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In a real app we'd scope this to allowed_origins of the embed key
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Embed-key auth on the hot path.
#
# Validating + bumping `last_used_at` used to do a SELECT + COMMIT on every
# chat message — 20-80ms of disk I/O before RAG even starts. We now:
#   1. Cache validated keys in memory (TTL below), so most requests never touch
#      the DB at all.
#   2. Background the `last_used_at` bump (debounced) instead of committing per
#      request.
# ---------------------------------------------------------------------------
_KEY_CACHE_TTL = 60.0  # seconds a validated key is trusted in memory
_key_cache: dict[str, tuple[float, str]] = {}  # key -> (time_validated, account_type)


def _cache_get(key: str) -> bool:
    hit = _key_cache.get(key)
    return bool(hit and time.monotonic() - hit[0] < _KEY_CACHE_TTL)


async def _touch_last_used(key: str) -> None:
    """Best-effort debounced `last_used_at` bump (never blocks the response)."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(EmbedKey)
                .where(EmbedKey.key == key)
                .where(EmbedKey.last_used_at < datetime.utcnow())
            )
            key_obj = result.scalar_one_or_none()
            if key_obj is not None:
                key_obj.last_used_at = datetime.utcnow()
                await db.commit()
    except Exception:
        logger.debug("last_used_at bump failed for key: %s", key, exc_info=True)


async def verify_embed_key(
    x_embed_key: str = Header(..., description="The embed key for the widget"),
) -> None:
    # Fast path: recently validated key in memory -> no DB hit / session at all.
    if _cache_get(x_embed_key):
        return

    # Cold path: validate against the DB (once per TTL window). We open a fresh
    # session here rather than via a request-scoped Depends(get_db), so the
    # common (cache-hit) path opens NO database session for the request.
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(EmbedKey.id, EmbedKey.active).where(EmbedKey.key == x_embed_key)
        )
        row = result.first()
    if row is None or not row[1]:
        raise HTTPException(status_code=401, detail="Invalid or inactive embed key")

    _key_cache[x_embed_key] = (time.monotonic(), "widget")
    if len(_key_cache) > 512:  # bounce the cache when it grows large
        _key_cache.clear()

    # Fire-and-forget the last_used_at update; never block the RAG pipeline.
    asyncio.create_task(_touch_last_used(x_embed_key))


app.include_router(chatbot_router, dependencies=[Depends(verify_embed_key)])
