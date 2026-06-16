from __future__ import annotations

import hashlib
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.users import Admin, User

_SALT: Final = "akirs-auto-local-auth"
_SEED_USERS: Final = (
    ("user1", "user1", "User One"),
    ("user2", "user2", "User Two"),
)
# username, password, display_name for the bootstrap administrator.
_SEED_ADMIN: Final = ("admin", "admin", "Administrator")


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
                    password=hash_password(password),
                    display_name=display_name,
                )
            )
    await session.commit()


async def seed_default_admin(session: AsyncSession) -> None:
    username, password, display_name = _SEED_ADMIN
    result = await session.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none() is None:
        session.add(
            Admin(
                username=username,
                password=hash_password(password),
                display_name=display_name,
                can_manage_embed_keys=True,
                permissions="*",
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
    if user is None or user.password != hash_password(password):
        return None
    return user
