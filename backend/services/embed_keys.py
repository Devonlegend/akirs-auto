from __future__ import annotations

import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.embed import EmbedKey

_KEY_PREFIX = "akemb_"


def generate_key() -> str:
    return _KEY_PREFIX + secrets.token_urlsafe(32)


def _origin_allowed(stored: str, origin: str | None) -> bool:
    allow = [o.strip() for o in (stored or "").split(",") if o.strip()]
    if not allow:
        return True  # empty allow-list means any origin
    if origin is None:
        return False
    return origin in allow


async def create_embed_key(
    session: AsyncSession,
    label: str,
    allowed_origins: str = "",
    owner_id: int | None = None,
) -> EmbedKey:
    record = EmbedKey(
        key=generate_key(),
        label=label,
        allowed_origins=allowed_origins or "",
        owner_id=owner_id,
        active=True,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def validate_embed_key(
    session: AsyncSession,
    key: str | None,
    origin: str | None = None,
) -> EmbedKey | None:
    """Return the EmbedKey if it exists, is active, and the origin is allowed."""
    if not key:
        return None
    result = await session.execute(select(EmbedKey).where(EmbedKey.key == key))
    record = result.scalar_one_or_none()
    if record is None or not record.active:
        return None
    if not _origin_allowed(record.allowed_origins, origin):
        return None
    record.last_used_at = func.now()
    await session.commit()
    return record
