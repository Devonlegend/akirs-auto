import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.database import Base, engine
from backend.routers import scraped, taxation
from chatbot.api.routes import prepare_pipeline, shutdown_pipeline
from chatbot.api.routes import router as chatbot_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure Ollama is running with the configured model loaded.
    try:
        await prepare_pipeline()
    except Exception:
        logging.getLogger("backend").exception(
            "Ollama bootstrap failed at startup — chat queries may fail until it's available."
        )

    try:
        yield
    finally:
        await shutdown_pipeline()


app = FastAPI(title="Akirs Auto Backend", lifespan=lifespan)

app.include_router(scraped.router)
app.include_router(taxation.router)
app.include_router(chatbot_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
