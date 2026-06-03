"""Repository classes for data access (one per aggregate)."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from akirs.db.models import (
    Ad,
    Advertiser,
    Geography,
    KeywordRun,
    ReconFinding,
    RegistryRecord,
    ScrapeJob,
    SocialLink,
    SocialProfile,
)


class JobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, kind: str, params: dict[str, Any]) -> ScrapeJob:
        job = ScrapeJob(kind=kind, status="queued", params_json=params)
        self.session.add(job)
        await self.session.flush()
        return job

    async def get(self, job_id: int) -> ScrapeJob | None:
        return await self.session.get(ScrapeJob, job_id)

    async def mark_started(self, job_id: int, celery_task_id: str | None = None) -> None:
        job = await self.session.get(ScrapeJob, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = datetime.now(UTC)
        if celery_task_id:
            job.celery_task_id = celery_task_id

    async def mark_completed(self, job_id: int, error: str | None = None) -> None:
        job = await self.session.get(ScrapeJob, job_id)
        if job is None:
            return
        job.status = "failed" if error else "completed"
        job.completed_at = datetime.now(UTC)
        if error:
            job.error = error


class AdvertiserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, fb_url: str, name: str | None) -> tuple[Advertiser, bool]:
        """Insert if not exists by fb_url; return (advertiser, created)."""
        result = await self.session.execute(select(Advertiser).where(Advertiser.fb_url == fb_url))
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.last_seen = datetime.now(UTC)
            if name and existing.name != name:
                existing.name = name
            return existing, False
        adv = Advertiser(fb_url=fb_url, name=name)
        self.session.add(adv)
        await self.session.flush()
        return adv, True

    async def list_all(self, limit: int = 1000) -> list[Advertiser]:
        result = await self.session.execute(select(Advertiser).limit(limit))
        return list(result.scalars().all())

    async def get(self, advertiser_id: int) -> Advertiser | None:
        return await self.session.get(Advertiser, advertiser_id)


class AdRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(
        self,
        advertiser_id: int,
        keyword_run_id: int | None,
        fb_ad_id: str | None,
        raw_json: dict,
    ) -> Ad:
        ad = Ad(
            advertiser_id=advertiser_id,
            keyword_run_id=keyword_run_id,
            fb_ad_id=fb_ad_id,
            raw_json=raw_json,
        )
        self.session.add(ad)
        await self.session.flush()
        return ad


class SocialLinkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_many(self, advertiser_id: int, links: list[dict]) -> int:
        """Insert distinct (advertiser_id, url) pairs. Returns count of new rows."""
        if not links:
            return 0
        rows = [
            {"advertiser_id": advertiser_id, "platform": link["platform"], "url": link["url"]}
            for link in links
        ]
        stmt = sqlite_insert(SocialLink).values(rows).on_conflict_do_nothing(
            index_elements=["advertiser_id", "url"]
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    async def list_for_advertiser(self, advertiser_id: int) -> list[SocialLink]:
        result = await self.session.execute(
            select(SocialLink).where(SocialLink.advertiser_id == advertiser_id)
        )
        return list(result.scalars().all())


class KeywordRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        scrape_job_id: int,
        keyword: str,
        location_geography_id: int | None,
    ) -> KeywordRun:
        run = KeywordRun(
            scrape_job_id=scrape_job_id,
            keyword=keyword,
            location_geography_id=location_geography_id,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def mark_completed(self, run_id: int, ads_found: int) -> None:
        run = await self.session.get(KeywordRun, run_id)
        if run is None:
            return
        run.ads_found = ads_found
        run.completed_at = datetime.now(UTC)


class GeographyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_name(self, name: str) -> Geography | None:
        result = await self.session.execute(select(Geography).where(Geography.name == name))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Geography]:
        result = await self.session.execute(select(Geography))
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(Geography.id)))
        return int(result.scalar_one())


class ReconRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_findings(self, advertiser_id: int, findings: list[dict]) -> int:
        if not findings:
            return 0
        for f in findings:
            self.session.add(
                ReconFinding(
                    advertiser_id=advertiser_id,
                    source=f["source"],
                    kind=f["kind"],
                    value=f["value"],
                    confidence=f.get("confidence", 0.5),
                    raw_json=f.get("raw_json", {}),
                )
            )
        await self.session.flush()
        return len(findings)

    async def list_for_advertiser(self, advertiser_id: int) -> list[ReconFinding]:
        result = await self.session.execute(
            select(ReconFinding).where(ReconFinding.advertiser_id == advertiser_id)
        )
        return list(result.scalars().all())

    async def add_social_profile(self, advertiser_id: int, **kwargs) -> SocialProfile:
        profile = SocialProfile(advertiser_id=advertiser_id, **kwargs)
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def add_registry_record(self, advertiser_id: int, **kwargs) -> RegistryRecord:
        record = RegistryRecord(advertiser_id=advertiser_id, **kwargs)
        self.session.add(record)
        await self.session.flush()
        return record
