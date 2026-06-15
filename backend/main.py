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
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.database import AsyncSessionLocal, Base, engine
from backend.models import users  # noqa: F401 - register auth tables with SQLAlchemy metadata
from backend.routers import auth, scraped, taxation
from backend.services.auth_queries import seed_default_users

from api.routes import advertisers as api_advertisers
from api.routes import geography as api_geography
from api.routes import jobs as api_jobs
from src.db.base import Base as JobsBase
from src.db.base import get_engine as get_jobs_engine
from src.db import models as _jobs_models  # noqa: F401 - register scraper tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with get_jobs_engine().begin() as conn:
        await conn.run_sync(JobsBase.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed_default_users(session)
    yield


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
app.include_router(api_jobs.router)
app.include_router(api_advertisers.router)
app.include_router(api_geography.router)

ui_dir = Path(__file__).resolve().parent.parent / "UserInterface"
if ui_dir.exists():
    app.mount("/ui", StaticFiles(directory=ui_dir, html=True), name="ui")


@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/ui/")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
