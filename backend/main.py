import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# The `src/` package is laid out so its modules import each other as top-level
# packages (e.g. `from taxation.agent import ...`, matching pyproject's
# `pythonpath = ["src"]`). Running uvicorn only puts the repo root on sys.path,
# so add `src/` here before importing any router that pulls in `src` code.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.database import AsyncSessionLocal, Base, engine
from backend.models import users  # noqa: F401 - register auth tables with SQLAlchemy metadata
from backend.routers import auth, scraped, taxation
from backend.services.auth_queries import seed_default_users

from api.routes import advertisers as api_advertisers
from api.routes import geography as api_geography
from api.routes import jobs as api_jobs

try:
    from chatbot.api.routes import prepare_pipeline, shutdown_pipeline
    from chatbot.api.routes import router as chatbot_router
except ModuleNotFoundError as exc:
    logging.getLogger("backend").warning(
        "Chatbot routes disabled because optional dependency %s is not installed.",
        exc.name,
    )
    chatbot_router = None

    async def prepare_pipeline():
        return None

    async def shutdown_pipeline():
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed_default_users(session)

    # Ensure Ollama is running with the configured model loaded.
    # try:
    #     await prepare_pipeline()
    # except Exception:
    #     logging.getLogger("backend").exception(
    #         "Ollama bootstrap failed at startup — chat queries may fail until it's available."
    #     )

    try:
        yield
    finally:
        pass
        # await shutdown_pipeline()


app = FastAPI(title="Akirs Auto Backend", lifespan=lifespan)

# Frontend is served from a separate static host during development, so allow
# cross-origin requests. Tighten allow_origins to the real static host later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scraped.router)
app.include_router(taxation.router)
app.include_router(auth.router)
if chatbot_router is not None:
    app.include_router(chatbot_router)
app.include_router(api_jobs.router)
app.include_router(api_advertisers.router)
app.include_router(api_geography.router)

ui_dir = Path(__file__).resolve().parent.parent / "UserInterface"
if ui_dir.exists():
    app.mount("/ui", StaticFiles(directory=ui_dir, html=True), name="ui")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
