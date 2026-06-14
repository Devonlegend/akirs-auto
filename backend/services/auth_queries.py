from __future__ import annotations

import hashlib
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.users import User

_SALT: Final = "akirs-auto-local-auth"
_SEED_USERS: Final = (
    ("user1", "user1", "User One"),
    ("user2", "user2", "User Two"),
)


def hash_password(password: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        _SALT.encode("utf-8"),
        120_000,
    ).hex()


async def seed_default_users(session: AsyncSession) -> None:
    for username, password, display_name in _SEED_USERS:
        result = await session.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none() is None:
            session.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    display_name=display_name,
                )
            )
    await session.commit()


async def authenticate_user(session: AsyncSession, username: str, password: str) -> User | None:
    # Ensure default users exist (helps if startup seeding was skipped)
    any_user = await session.execute(select(User).limit(1))
    if any_user.scalar_one_or_none() is None:
        await seed_default_users(session)

    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or user.password_hash != hash_password(password):
        return None
    return user
