from fastapi import FastAPI
from contextlib import asynccontextmanager
from backend.database import engine, Base
from backend.routers import scraped

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Akirs Auto Backend", lifespan=lifespan)

app.include_router(scraped.router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
