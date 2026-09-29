import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# Read DATABASE_URL from the environment so the api, worker, and admin panel all
# share ONE database file. Previously this was hardcoded to a relative
# "./akirs.db" (-> /app/akirs.db in the container), while src/db/base.py read
# settings.database_url (-> /data/akirs.db). That split-brain meant the jobs
# tables (created at startup on /data/akirs.db) did not exist in the /app file
# the worker connected to -> "no such table: scrape_jobs". It also made
# auth/users ephemeral (the /app file is not on the /data volume).
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./akirs.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
