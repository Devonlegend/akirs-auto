"""Redis-backed live job state for SSE.

The scrape worker publishes a small progress signal after each keyword and on
every status change. Two things happen per publish:
  - the latest state is stored under a per-job key (the snapshot a freshly
    connected SSE client reads), with a TTL so finished jobs self-expire;
  - the same state is published on a channel that SSE endpoints relay as deltas.

This carries only the ephemeral progress signal — the scraped data and final
job status still live in the database. Publishing is best-effort: a Redis
outage must never break a scrape, so failures are swallowed and logged.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

CHANNEL = "akirs:job-events"
_KEY_PREFIX = "akirs:job:"
_SNAPSHOT_TTL_SECONDS = 60 * 60  # 1h; active jobs refresh it on every event


def _key(job_id: int) -> str:
    return f"{_KEY_PREFIX}{job_id}"


def _client() -> aioredis.Redis:
    # No module-level singleton: Celery may run each task in a fresh event loop,
    # and a redis.asyncio client is bound to the loop it was created in.
    return aioredis.from_url(get_settings().redis_url, decode_responses=True)


async def publish_job_event(state: dict[str, Any]) -> None:
    """Store the latest job state and publish it. Best-effort."""
    job_id = state.get("job_id")
    if job_id is None:
        return
    client = _client()
    try:
        payload = json.dumps(state)
        async with client.pipeline(transaction=False) as pipe:
            pipe.set(_key(int(job_id)), payload, ex=_SNAPSHOT_TTL_SECONDS)
            pipe.publish(CHANNEL, payload)
            await pipe.execute()
    except Exception as exc:  # noqa: BLE001 - never let telemetry break a scrape
        logger.warning("job-event publish failed for job %s: %s", job_id, exc)
    finally:
        await client.aclose()


async def snapshot_active_jobs() -> list[dict[str, Any]]:
    """Current state of every job still present in Redis (active / recently ended)."""
    client = _client()
    try:
        keys = [k async for k in client.scan_iter(match=f"{_KEY_PREFIX}*")]
        if not keys:
            return []
        values = await client.mget(keys)
        return [json.loads(v) for v in values if v]
    except Exception as exc:  # noqa: BLE001
        logger.warning("job-event snapshot failed: %s", exc)
        return []
    finally:
        await client.aclose()
