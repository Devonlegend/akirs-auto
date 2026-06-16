"""Jobs API routes."""

import asyncio
import json
import logging
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.security import verify_token
from src.api.deps import db_session
from src.api.schemas import JobCreatedResponse, JobStatusResponse, ScrapeJobRequest
from src.config.settings import get_settings
from src.db.models import Ad, Advertiser, KeywordRun, ScrapeJob
from src.db.repositories import JobRepository
from src.realtime.job_events import CHANNEL, publish_job_event, snapshot_active_jobs
from src.tasks.celery_app import celery_app
from src.tasks.phase1_scrape import scrape_facebook_ads_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

# Param keys holding Facebook login credentials. These are accepted for a single
# job, forwarded only to the running scrape task, and never written to the job
# row or returned in any API response. Scraping is anonymous unless supplied.
_SENSITIVE_PARAM_KEYS = ("facebook_email", "facebook_password")


@router.post("/scrape", response_model=JobCreatedResponse)
async def create_scrape_job(
    body: ScrapeJobRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(db_session),
) -> JobCreatedResponse:
    params = _scrape_params(body)
    return await _queue_scrape_job(params, session, background_tasks)


@router.post("/scrape/after-login", response_model=JobCreatedResponse)
async def create_scrape_job_after_manual_login(
    body: ScrapeJobRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(db_session),
) -> JobCreatedResponse:
    """Back-compat alias for the old manual-login flow.

    The scraper no longer opens a server-side login browser (that can't work in a
    deployed, headless environment). Scraping is anonymous by default; optional
    Facebook credentials on the request body are used ephemerally at scrape time.
    This endpoint now behaves identically to ``/scrape`` and never blocks.
    """
    params = _scrape_params(body)
    return await _queue_scrape_job(params, session, background_tasks)


def _scrape_params(body: ScrapeJobRequest) -> dict:
    settings = get_settings()
    params = body.model_dump(exclude_none=False)
    if not params.get("user_keywords"):
        params["user_keywords"] = _parse_csv(settings.scraper_keywords)
    return params


def _redact_params(params: dict) -> dict:
    """Return a copy of params safe to persist / return — credentials stripped."""
    return {k: v for k, v in params.items() if k not in _SENSITIVE_PARAM_KEYS}


def _parse_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


async def _queue_scrape_job(
    params: dict,
    session: AsyncSession,
    background_tasks: BackgroundTasks,
) -> JobCreatedResponse:
    # The job row stores only redacted params; the live task receives the full
    # params (including any ephemeral credentials) but never writes them back.
    stored_params = _redact_params(params)
    repo = JobRepository(session)
    job = await repo.create(kind="phase1_scrape", params=stored_params)
    await session.commit()

    try:
        async_result = scrape_facebook_ads_job.delay(job.id, params)
        return JobCreatedResponse(job_id=job.id, status="queued", celery_task_id=async_result.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Celery unavailable; running scrape job %s in FastAPI background: %s", job.id, exc)
        background_tasks.add_task(_run_scrape_without_celery, job.id, params)
        return JobCreatedResponse(job_id=job.id, status="queued", celery_task_id=None)


async def _run_scrape_without_celery(job_id: int, params: dict) -> None:
    from tasks.phase1_scrape import _run

    await _run(job_id, params, celery_task_id=None)


@router.get("", response_model=list[JobStatusResponse])
async def list_jobs(
    limit: int = 25,
    session: AsyncSession = Depends(db_session),
) -> list[JobStatusResponse]:
    result = await session.execute(
        select(ScrapeJob)
        .where(ScrapeJob.kind == "phase1_scrape")
        .order_by(desc(ScrapeJob.created_at))
        .limit(min(max(limit, 1), 100))
    )
    jobs = list(result.scalars().all())
    return [await _job_status_response(job, session) for job in jobs]


async def _publish_status_change(job: ScrapeJob, *, terminal: bool) -> None:
    """Push a job's status change to SSE subscribers. Counts are omitted; the
    client merges this onto the last-known state for that job."""
    params = job.params_json or {}
    await publish_job_event(
        {
            "job_id": job.id,
            "status": job.status,
            "operator_user_id": str(params.get("operator_user_id") or ""),
            "terminal": terminal,
        }
    )


_SSE_KEEPALIVE_SECONDS = 15.0


@router.get("/events")
async def job_events(request: Request, token: str = "") -> StreamingResponse:
    """Server-Sent Events stream of job state for the authenticated operator.

    EventSource cannot set headers, so the signed session token is passed as a
    query param. Each message is the same state object the worker publishes,
    filtered to jobs owned by this operator.
    """
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    uid = str(payload["uid"])

    async def event_stream():
        client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
        pubsub = client.pubsub()
        # Subscribe BEFORE reading the snapshot: subscribing after could drop an
        # event fired in the gap. Worst case is a duplicate, which the client
        # merges idempotently.
        await pubsub.subscribe(CHANNEL)
        try:
            for state in await snapshot_active_jobs():
                if str(state.get("operator_user_id") or "") == uid:
                    yield f"data: {json.dumps(state)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=_SSE_KEEPALIVE_SECONDS
                )
                if message is None:
                    yield ": keepalive\n\n"
                    continue
                try:
                    state = json.loads(message["data"])
                except (TypeError, ValueError):
                    continue
                if str(state.get("operator_user_id") or "") == uid:
                    yield f"data: {json.dumps(state)}\n\n"
        finally:
            # Always tear down on disconnect so closed tabs don't leak
            # subscriptions/connections.
            await pubsub.unsubscribe(CHANNEL)
            await pubsub.aclose()
            await client.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/{job_id}/pause", response_model=JobStatusResponse)
async def pause_job(
    job_id: int,
    session: AsyncSession = Depends(db_session),
) -> JobStatusResponse:
    job = await _get_job_or_404(job_id, session)
    if job.status in {"queued", "running"}:
        job.status = "paused"
        await session.commit()
        await session.refresh(job)
        await _publish_status_change(job, terminal=False)
    return await _job_status_response(job, session)


@router.post("/{job_id}/resume", response_model=JobStatusResponse)
async def resume_job(
    job_id: int,
    session: AsyncSession = Depends(db_session),
) -> JobStatusResponse:
    job = await _get_job_or_404(job_id, session)
    if job.status == "paused":
        job.status = "running" if job.started_at else "queued"
        await session.commit()
        await session.refresh(job)
        await _publish_status_change(job, terminal=False)
    return await _job_status_response(job, session)


@router.post("/{job_id}/stop", response_model=JobStatusResponse)
async def stop_job(
    job_id: int,
    session: AsyncSession = Depends(db_session),
) -> JobStatusResponse:
    job = await _get_job_or_404(job_id, session)
    if job.status not in {"completed", "failed", "stopped"}:
        job.status = "stopped"
        job.completed_at = datetime.now(UTC)
        job.error = "Stopped by operator"
        await session.commit()
        await session.refresh(job)
        await _publish_status_change(job, terminal=True)
        if job.celery_task_id:
            try:
                celery_app.control.revoke(job.celery_task_id, terminate=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not revoke Celery task %s: %s", job.celery_task_id, exc)
    return await _job_status_response(job, session)


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: int,
    session: AsyncSession = Depends(db_session),
) -> None:
    job = await _get_job_or_404(job_id, session)
    if job.status in {"queued", "running", "paused"}:
        raise HTTPException(status_code=409, detail="Only ended jobs can be deleted")

    keyword_run_ids = select(KeywordRun.id).where(KeywordRun.scrape_job_id == job_id)
    await session.execute(delete(Ad).where(Ad.keyword_run_id.in_(keyword_run_ids)))
    await session.execute(delete(KeywordRun).where(KeywordRun.scrape_job_id == job_id))
    await session.delete(job)
    await session.commit()


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: int,
    session: AsyncSession = Depends(db_session),
) -> JobStatusResponse:
    job = await _get_job_or_404(job_id, session)
    return await _job_status_response(job, session)


async def _get_job_or_404(job_id: int, session: AsyncSession) -> ScrapeJob:
    job = await session.get(ScrapeJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


async def _job_status_response(job: ScrapeJob, session: AsyncSession) -> JobStatusResponse:
    job_id = job.id
    kr_count = await session.scalar(
        select(func.count(KeywordRun.id)).where(KeywordRun.scrape_job_id == job_id)
    )
    ad_count = await session.scalar(
        select(func.count(Ad.id))
        .join(KeywordRun, KeywordRun.id == Ad.keyword_run_id)
        .where(KeywordRun.scrape_job_id == job_id)
    )
    adv_count = await session.scalar(
        select(func.count(func.distinct(Advertiser.id)))
        .join(Ad, Ad.advertiser_id == Advertiser.id)
        .join(KeywordRun, KeywordRun.id == Ad.keyword_run_id)
        .where(KeywordRun.scrape_job_id == job_id)
    )

    return JobStatusResponse(
        job_id=job.id,
        kind=job.kind,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error=job.error,
        celery_task_id=job.celery_task_id,
        params=job.params_json or {},
        keyword_run_count=int(kr_count or 0),
        ad_count=int(ad_count or 0),
        advertiser_count=int(adv_count or 0),
    )
