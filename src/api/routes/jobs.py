"""Jobs API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import db_session
from api.schemas import JobCreatedResponse, JobStatusResponse, ScrapeJobRequest
from db.models import Ad, Advertiser, KeywordRun, ScrapeJob
from db.repositories import JobRepository
from tasks.phase1_scrape import scrape_facebook_ads_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/scrape", response_model=JobCreatedResponse)
async def create_scrape_job(
    body: ScrapeJobRequest,
    session: AsyncSession = Depends(db_session),
) -> JobCreatedResponse:
    params = body.model_dump(exclude_none=False)
    repo = JobRepository(session)
    job = await repo.create(kind="phase1_scrape", params=params)
    await session.commit()

    async_result = scrape_facebook_ads_job.delay(job.id, params)
    return JobCreatedResponse(job_id=job.id, status="queued", celery_task_id=async_result.id)


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: int,
    session: AsyncSession = Depends(db_session),
) -> JobStatusResponse:
    job = await session.get(ScrapeJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

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
