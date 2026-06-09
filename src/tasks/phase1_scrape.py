"""Phase 1: Facebook Ads scrape task.

Runs the FB Ads scraper for each expanded keyword and persists discovered
advertisers, ads, and social links. On completion, optionally fans out
Phase 2 recon tasks via a Celery chord.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import chord, shared_task

from src.config.settings import get_settings
from backend.database import AsyncSessionLocal
from src.db.repositories import (
    AdRepository,
    AdvertiserRepository,
    GeographyRepository,
    JobRepository,
    KeywordRunRepository,
    SocialLinkRepository,
)
from keywords import expand
from src.scrapers.browser import launch_browser
from src.scrapers.facebook_ads import FacebookAdsScraper

logger = logging.getLogger(__name__)


@shared_task(name="tasks.phase1_scrape.scrape_facebook_ads_job", bind=True)
def scrape_facebook_ads_job(self, job_id: int, params: dict[str, Any]) -> dict[str, Any]:
    """Celery entry point. Runs the async impl via asyncio.run()."""
    return asyncio.run(_run(job_id, params, celery_task_id=self.request.id))


async def _run(job_id: int, params: dict[str, Any], celery_task_id: str | None) -> dict[str, Any]:
    settings = get_settings()
    settings = get_settings()

    target = int(params.get("target_ads_per_keyword", settings.target_ads_per_keyword_default))
    cap = int(params.get("keyword_cap", settings.keyword_cap_default))
    run_recon = bool(params.get("run_recon", True))
    country = params.get("country", settings.fb_ads_country)

    specs = expand(
        locations=params.get("locations"),
        categories=params.get("categories"),
        user_keywords=params.get("user_keywords"),
        use_llm=bool(params.get("use_llm_expansion", False)),
        cap=cap,
    )

    async with AsyncSessionLocal() as session:
        await JobRepository(session).mark_started(job_id, celery_task_id)
        await session.commit()

    new_advertiser_ids: list[int] = []
    total_ads = 0
    error_msg: str | None = None

    try:
        async with launch_browser(headless=settings.fb_ads_headless) as (_browser, _context, page):
            scraper = FacebookAdsScraper(page)
            await scraper.setup(country=country)

            for spec in specs:
                logger.info(f"Phase 1: scraping keyword='{spec.keyword}' location='{spec.location}'")
                async with AsyncSessionLocal() as session:
                    geo_repo = GeographyRepository(session)
                    kr_repo = KeywordRunRepository(session)
                    geo = await geo_repo.get_by_name(spec.location) if spec.location else None
                    keyword_run = await kr_repo.create(
                        scrape_job_id=job_id,
                        keyword=spec.keyword,
                        location_geography_id=geo.id if geo else None,
                    )
                    await session.commit()
                    keyword_run_id = keyword_run.id

                await scraper.facebook_page.search_keyword(spec.keyword)

                try:
                    ads = await scraper.scrape(target_count=target)
                except Exception as e:
                    logger.exception(f"Scrape failed for keyword '{spec.keyword}': {e}")
                    ads = []

                async with AsyncSessionLocal() as session:
                    adv_repo = AdvertiserRepository(session)
                    ad_repo = AdRepository(session)
                    link_repo = SocialLinkRepository(session)
                    kr_repo = KeywordRunRepository(session)

                    saved = 0
                    for ad in ads:
                        fb_url = ad.get("advertiser_url")
                        if not fb_url:
                            continue
                        adv, created = await adv_repo.upsert(fb_url=fb_url, name=ad.get("advertiser_name"))
                        if created:
                            new_advertiser_ids.append(adv.id)
                        await ad_repo.add(
                            advertiser_id=adv.id,
                            keyword_run_id=keyword_run_id,
                            fb_ad_id=ad.get("fb_ad_id"),
                            raw_json=ad,
                        )
                        await link_repo.add_many(advertiser_id=adv.id, links=ad.get("social_links", []))
                        saved += 1

                    await kr_repo.mark_completed(keyword_run_id, ads_found=saved)
                    total_ads += saved
                    await session.commit()
    except Exception as e:
        logger.exception(f"Phase 1 failed: {e}")
        error_msg = str(e)

    async with AsyncSessionLocal() as session:
        await JobRepository(session).mark_completed(job_id, error=error_msg)
        await session.commit()

    if run_recon and new_advertiser_ids and not error_msg:
        _dispatch_recon(job_id, new_advertiser_ids)

    return {
        "job_id": job_id,
        "keyword_runs": len(specs),
        "total_ads": total_ads,
        "new_advertisers": len(new_advertiser_ids),
        "error": error_msg,
    }


def _dispatch_recon(job_id: int, advertiser_ids: list[int]) -> None:
    """Fan out a Phase 2 recon task per advertiser, chord to a finalize callback."""
    from tasks.phase2_recon import finalize_recon, recon_advertiser_job

    header = [recon_advertiser_job.s(adv_id) for adv_id in advertiser_ids]
    chord(header)(finalize_recon.s(job_id))
