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
from src.keywords import expand
from src.realtime.job_events import publish_job_event
from src.scrapers.browser import launch_browser
from src.scrapers.facebook_ads import FacebookAdsScraper

logger = logging.getLogger(__name__)


def _progress(
    job_id: int,
    params: dict[str, Any],
    status: str,
    *,
    keywords_total: int,
    keywords_done: int,
    ads: int,
    advertisers: int,
    error: str | None = None,
    terminal: bool = False,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "status": status,
        "operator_user_id": str(params.get("operator_user_id") or ""),
        "keywords_total": keywords_total,
        "keywords_done": keywords_done,
        "ads": ads,
        "advertisers": advertisers,
        "error": error,
        "terminal": terminal,
    }


@shared_task(name="tasks.phase1_scrape.scrape_facebook_ads_job", bind=True)
def scrape_facebook_ads_job(self, job_id: int, params: dict[str, Any]) -> dict[str, Any]:
    """Celery entry point. Runs the async impl via asyncio.run()."""
    return asyncio.run(_run(job_id, params, celery_task_id=self.request.id))


async def _run(job_id: int, params: dict[str, Any], celery_task_id: str | None) -> dict[str, Any]:
    settings = get_settings()

    target = int(params.get("target_ads_per_keyword", settings.target_ads_per_keyword_default))
    cap = int(params.get("keyword_cap", settings.keyword_cap_default))
    run_recon = bool(params.get("run_recon", True))
    country = params.get("country", settings.fb_ads_country)
    # Optional, ephemeral Facebook credentials. Scraping runs anonymously against
    # the public Ads Library unless both are supplied; they are never persisted.
    facebook_email = params.get("facebook_email") or None
    facebook_password = params.get("facebook_password") or None
    user_keywords = params.get("user_keywords") or [
        item.strip() for item in settings.scraper_keywords.split(",") if item.strip()
    ]

    specs = expand(
        locations=params.get("locations"),
        categories=params.get("categories"),
        user_keywords=user_keywords,
        use_llm=bool(params.get("use_llm_expansion", False)),
        cap=cap,
    )

    async with AsyncSessionLocal() as session:
        await JobRepository(session).mark_started(job_id, celery_task_id)
        await session.commit()

    keywords_total = len(specs)
    await publish_job_event(
        _progress(job_id, params, "running", keywords_total=keywords_total, keywords_done=0, ads=0, advertisers=0)
    )

    new_advertiser_ids: list[int] = []
    all_advertiser_ids: set[int] = set()
    total_ads = 0
    keywords_done = 0
    error_msg: str | None = None
    final_status: str | None = None

    try:
        async with launch_browser(
            headless=settings.fb_ads_headless,
        ) as (_browser, _context, page):
            if facebook_email and facebook_password:
                await _attempt_facebook_login(page, facebook_email, facebook_password)

            scraper = FacebookAdsScraper(page)
            await scraper.setup(country=country)

            for spec in specs:
                if not await _wait_until_job_can_continue(job_id):
                    logger.info("Phase 1: job %s stopped before keyword '%s'", job_id, spec.keyword)
                    break

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
                        all_advertiser_ids.add(adv.id)
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

                keywords_done += 1
                await publish_job_event(
                    _progress(
                        job_id,
                        params,
                        "running",
                        keywords_total=keywords_total,
                        keywords_done=keywords_done,
                        ads=total_ads,
                        advertisers=len(all_advertiser_ids),
                    )
                )
    except Exception as e:
        logger.exception(f"Phase 1 failed: {e}")
        error_msg = str(e)

    async with AsyncSessionLocal() as session:
        job = await JobRepository(session).get(job_id)
        final_status = job.status if job else None
        if job and job.status != "stopped":
            await JobRepository(session).mark_completed(job_id, error=error_msg)
            await session.commit()

    terminal_status = "stopped" if final_status == "stopped" else ("failed" if error_msg else "completed")
    await publish_job_event(
        _progress(
            job_id,
            params,
            terminal_status,
            keywords_total=keywords_total,
            keywords_done=keywords_done,
            ads=total_ads,
            advertisers=len(all_advertiser_ids),
            error=error_msg,
            terminal=True,
        )
    )

    if run_recon and all_advertiser_ids and not error_msg and final_status != "stopped":
        _dispatch_recon(job_id, list(all_advertiser_ids))

    return {
        "job_id": job_id,
        "keyword_runs": len(specs),
        "total_ads": total_ads,
        "new_advertisers": len(new_advertiser_ids),
        "error": error_msg,
    }


async def _attempt_facebook_login(page, email: str, password: str) -> None:
    """Best-effort scripted Facebook login using ephemeral, per-job credentials.

    Scraping targets the public Ads Library and works without authentication, so
    a failed login here is non-fatal — we log and continue anonymously. The
    credentials are used only for this browser session and are never persisted.
    Facebook 2FA / checkpoints can still block scripted logins; that is expected.
    """
    try:
        await page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")
        await page.fill("input[name='email']", email, timeout=8000)
        await page.fill("input[name='pass']", password, timeout=8000)
        await page.click("button[name='login']", timeout=8000)
        await page.wait_for_load_state("networkidle", timeout=15000)

        current_url = page.url or ""
        if "login" in current_url or "checkpoint" in current_url:
            logger.warning(
                "Phase 1: Facebook login did not complete (checkpoint/2FA or bad "
                "credentials) — continuing anonymously."
            )
        else:
            logger.info("Phase 1: Facebook login succeeded for this job session.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Phase 1: Facebook login attempt failed (%s) — continuing anonymously.", exc)


async def _wait_until_job_can_continue(job_id: int) -> bool:
    while True:
        async with AsyncSessionLocal() as session:
            job = await JobRepository(session).get(job_id)
            status = job.status if job else "stopped"

        if status == "stopped":
            return False
        if status != "paused":
            return True

        await asyncio.sleep(2)


def _dispatch_recon(job_id: int, advertiser_ids: list[int]) -> None:
    """Fan out a Phase 2 recon task per advertiser, chord to a finalize callback."""
    from tasks.phase2_recon import finalize_recon, recon_advertiser_job

    header = [recon_advertiser_job.s(adv_id) for adv_id in advertiser_ids]
    chord(header)(finalize_recon.s(job_id))
