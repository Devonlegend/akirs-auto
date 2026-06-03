"""Thin CLI shim: single-shot scrape via the new akirs framework.

For the full server experience (FastAPI + Celery + recon), use:
    uvicorn akirs.api.app:app --reload
    celery -A akirs.tasks.celery_app worker --loglevel=info

This shim runs phase 1 directly in-process without Celery, useful for quick
local verification of pagination + DB persistence.  When ``--recon`` is
supplied, phase 2 enrichment also runs inline immediately after the scrape.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, UTC

from src.akirs.config.settings import get_settings
from src.akirs.db.base import get_session_factory
from src.akirs.db.repositories import (
    AdRepository,
    AdvertiserRepository,
    GeographyRepository,
    JobRepository,
    KeywordRunRepository,
    ReconRepository,
    SocialLinkRepository,
)
from src.akirs.keywords import expand
from src.akirs.scrapers.browser import launch_browser
from src.akirs.scrapers.facebook_ads import FacebookAdsScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("akirs.cli")


async def _run_recon(
    new_advertiser_ids: list[int],
    factory,
) -> None:
    """Run Phase 2 recon inline for all newly discovered advertisers.

    Imports the coordinator lazily so this module doesn't hard-depend on recon
    infrastructure at import time.

    Args:
        new_advertiser_ids: Primary keys of advertisers to enrich.
        factory: Async session factory.
    """
    if not new_advertiser_ids:
        logger.info("No new advertisers — skipping recon")
        return

    from src.akirs.recon.registry import build_default_coordinator  # noqa: PLC0415

    coordinator = build_default_coordinator()
    logger.info("Starting Phase 2 recon for %d advertisers", len(new_advertiser_ids))

    for adv_id in new_advertiser_ids:
        async with factory() as session:
            adv_repo = AdvertiserRepository(session)
            recon_repo = ReconRepository(session)

            adv = await adv_repo.get(adv_id)
            if adv is None:
                logger.warning("Advertiser %d not found — skipping recon", adv_id)
                continue

            try:
                findings = await coordinator.enrich(adv, session)
                finding_dicts = [f.to_dict() for f in findings]
                saved = await recon_repo.add_findings(adv.id, finding_dicts)
                await session.commit()
                logger.info(
                    "Recon for advertiser %d (%s): %d findings persisted",
                    adv.id,
                    adv.name or adv.fb_url,
                    saved,
                )
            except Exception:
                logger.exception("Recon failed for advertiser %d", adv_id)
                await session.rollback()

    logger.info("Phase 2 recon complete")


async def _export_csv(factory) -> None:
    """Export enriched CSV after recon to the configured output directory.

    Args:
        factory: Async session factory.
    """
    from akirs.exporters.csv_export import CSVExportService  # noqa: PLC0415

    settings = get_settings()
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    csv_path = settings.output_dir / f"akirs_enriched_{timestamp}.csv"

    async with factory() as session:
        exporter = CSVExportService(session)
        await exporter.to_file(csv_path)

    logger.info("Enriched CSV exported to %s", csv_path)


async def run_once(args: argparse.Namespace) -> None:
    """Execute a single-shot Phase 1 scrape, optionally followed by Phase 2 recon."""
    settings = get_settings()
    factory = get_session_factory()

    specs = expand(
        locations=args.locations,
        categories=args.categories,
        cap=args.cap,
    )
    logger.info(f"Generated {len(specs)} keyword runs")

    async with factory() as session:
        job = await JobRepository(session).create(kind="phase1_scrape_cli", params=vars(args))
        await session.commit()
        job_id = job.id

    new_advertiser_ids: list[int] = []

    async with launch_browser(headless=args.headless) as (_b, _c, page):
        scraper = FacebookAdsScraper(page)
        await scraper.setup(country=settings.fb_ads_country)

        for spec in specs:
            logger.info(f"keyword={spec.keyword!r} location={spec.location!r}")
            await scraper.facebook_page.search_keyword(spec.keyword)
            ads = await scraper.scrape(target_count=args.target)

            async with factory() as session:
                adv_repo = AdvertiserRepository(session)
                ad_repo = AdRepository(session)
                link_repo = SocialLinkRepository(session)
                geo_repo = GeographyRepository(session)
                kr_repo = KeywordRunRepository(session)

                geo = await geo_repo.get_by_name(spec.location) if spec.location else None
                kr = await kr_repo.create(
                    scrape_job_id=job_id,
                    keyword=spec.keyword,
                    location_geography_id=geo.id if geo else None,
                )
                await session.commit()

                saved = 0
                for ad in ads:
                    if not ad.get("advertiser_url"):
                        continue
                    adv, created = await adv_repo.upsert(ad["advertiser_url"], ad.get("advertiser_name"))
                    await ad_repo.add(adv.id, kr.id, ad.get("fb_ad_id"), ad)
                    await link_repo.add_many(adv.id, ad.get("social_links", []))
                    if created:
                        new_advertiser_ids.append(adv.id)
                    saved += 1

                await kr_repo.mark_completed(kr.id, ads_found=saved)
                await session.commit()
                logger.info(f"persisted {saved} ads for keyword {spec.keyword!r}")

    async with factory() as session:
        await JobRepository(session).mark_completed(job_id)
        await session.commit()
    logger.info(f"job {job_id} complete — {len(new_advertiser_ids)} new advertisers discovered")

    # Phase 2: inline recon (if requested)
    if args.recon:
        await _run_recon(new_advertiser_ids, factory)
        await _export_csv(factory)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    p = argparse.ArgumentParser(description="akirs single-shot scrape CLI")
    p.add_argument("--locations", nargs="*", help="Akwa Ibom locations (defaults to all 31 LGAs)")
    p.add_argument("--categories", nargs="*", help="Business categories (defaults to curated)")
    p.add_argument("--target", type=int, default=5, help="Target ads per keyword (default 5)")
    p.add_argument("--cap", type=int, default=4, help="Max keyword runs (default 4)")
    p.add_argument("--headless", action="store_true", help="Run browser headless")
    p.add_argument(
        "--recon",
        action="store_true",
        help="Run Phase 2 recon inline after scraping (no Celery required)",
    )
    return p.parse_args()


def main() -> None:
    """Entry point for the akirs CLI."""
    asyncio.run(run_once(parse_args()))


if __name__ == "__main__":
    main()

