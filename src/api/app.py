"""FastAPI application factory."""

from fastapi import FastAPI

from src.api.routes import advertisers, geography, health, jobs


def create_app() -> FastAPI:
    app = FastAPI(
        title="akirs",
        version="0.2.0",
        description="Akwa Ibom business intelligence — FB Ads scrape + recon",
    )
    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(advertisers.router)
    app.include_router(geography.router)
    return app


app = create_app()
