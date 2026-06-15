"""Jobs API routes."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import db_session
from api.schemas import JobCreatedResponse, JobStatusResponse, ScrapeJobRequest
from src.config.settings import get_settings
from src.db.models import Ad, Advertiser, KeywordRun, ScrapeJob
from src.db.repositories import JobRepository
from src.scrapers.browser import launch_browser
from tasks.celery_app import celery_app
from tasks.phase1_scrape import scrape_facebook_ads_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


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
    params = _scrape_params(body)
    await _wait_for_manual_login(params)
    return await _queue_scrape_job(params, session, background_tasks)


def _scrape_params(body: ScrapeJobRequest) -> dict:
    settings = get_settings()
    params = body.model_dump(exclude_none=False)
    params["facebook_user_data_dir"] = params.get("facebook_user_data_dir") or str(
        settings.fb_ads_user_data_dir
    )
    if not params.get("user_keywords"):
        params["user_keywords"] = _parse_csv(settings.scraper_keywords)
    return params


def _parse_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


async def _queue_scrape_job(
    params: dict,
    session: AsyncSession,
    background_tasks: BackgroundTasks,
) -> JobCreatedResponse:
    repo = JobRepository(session)
    job = await repo.create(kind="phase1_scrape", params=params)
    await session.commit()

    try:
        async_result = scrape_facebook_ads_job.delay(job.id, params)
        return JobCreatedResponse(job_id=job.id, status="queued", celery_task_id=async_result.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Celery unavailable; running scrape job %s in FastAPI background: %s", job.id, exc)
        background_tasks.add_task(_run_scrape_without_celery, job.id, params)
        return JobCreatedResponse(job_id=job.id, status="queued", celery_task_id=None)


async def _wait_for_manual_login(params: dict) -> None:
    settings = get_settings()
    user_data_dir = params.get("facebook_user_data_dir") or str(settings.fb_ads_user_data_dir)

    async with launch_browser(headless=False, user_data_dir=user_data_dir) as (_browser, _context, page):
        await page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")
        logger.info("Manual Facebook login browser opened. Close it to start scraping.")

        while True:
            try:
                if page.is_closed():
                    return
                await page.wait_for_timeout(1000)
            except Exception:
                return


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


@router.post("/{job_id}/stop", response_model=JobStatusResponse)
async def stop_job(
    job_id: int,
    session: AsyncSession = Depends(db_session),
) -> JobStatusResponse:
    from tasks.celery_app import celery_app

    job = await session.get(ScrapeJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    if job.status not in ["completed", "failed"]:
        # Revoke the task in Celery, terminate=True sends SIGTERM to the worker child process.
        if job.celery_task_id:
            celery_app.control.revoke(job.celery_task_id, terminate=True)
            
        job.status = "failed"
        job.error = "Manually stopped by user."
        await session.commit()

    return await get_job(job_id, session)

