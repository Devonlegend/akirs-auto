from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.database import Base, engine
from backend.routers import scraped
from chatbot.api.routes import router as chatbot_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Akirs Auto Backend", lifespan=lifespan)

app.include_router(scraped.router)
app.include_router(chatbot_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
