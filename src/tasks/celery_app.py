"""Celery app — uses Redis for broker + result backend.

Tasks run in the default prefork pool; async code is invoked via asyncio.run()
inside each task so we don't have to monkey-patch with gevent/eventlet.
"""

from celery import Celery

from src.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "akirs",
    broker=settings.broker_url,
    backend=settings.result_backend,
    include=[
        "tasks.phase1_scrape",
        "tasks.phase2_recon",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
