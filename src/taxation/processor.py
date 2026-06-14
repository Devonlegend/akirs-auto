"""Taxation processor — classify advertisers and persist taxable ones."""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config.settings import get_settings
from src.db.base import get_session_factory
from src.db.models import Advertiser
from src.db.repositories import TaxableEntityRepository
from .agent import assess
from .profile_text import build_profile_text

logger = logging.getLogger(__name__)


def _advertiser_query(limit: int | None):
    stmt = (
        select(Advertiser)
        .options(
            selectinload(Advertiser.ads),
            selectinload(Advertiser.social_links),
            selectinload(Advertiser.recon_findings),
            selectinload(Advertiser.social_profiles),
            selectinload(Advertiser.registry_records),
            selectinload(Advertiser.warehouse_votes),
        )
        .order_by(Advertiser.id)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return stmt


async def run_tax_classification(
    limit: int | None = None,
    advertiser_ids: list[int] | None = None,
) -> dict:
    """Classify advertisers via the LLM agent and upsert taxable assessments.

    Args:
        limit: Optional cap on advertisers processed (ignored if advertiser_ids given).
        advertiser_ids: Optional explicit subset of advertiser ids to process.

    Returns:
        Summary dict: ``processed``, ``taxable``, ``errors``, ``elapsed_ms``.
    """
    t0 = time.monotonic()
    settings = get_settings()
    errors: list[str] = []
    processed = 0
    taxable = 0

    session_factory = get_session_factory()
    async with session_factory() as session:  # type: AsyncSession
        stmt = _advertiser_query(limit)
        if advertiser_ids:
            stmt = _advertiser_query(None).where(Advertiser.id.in_(advertiser_ids))
        result = await session.execute(stmt)
        advertisers = list(result.scalars().unique())

        if not advertisers:
            return {
                "processed": 0,
                "taxable": 0,
                "errors": ["No advertisers to classify."],
                "elapsed_ms": (time.monotonic() - t0) * 1000,
            }

        repo = TaxableEntityRepository(session)
        semaphore = asyncio.Semaphore(settings.tax_concurrency)

        async def classify(adv: Advertiser):
            async with semaphore:
                blob = build_profile_text(adv)
                if not blob.strip():
                    return adv.id, None, None
                try:
                    assessment = await assess(blob)
                    return adv.id, assessment, None
                except Exception as exc:  # noqa: BLE001
                    return adv.id, None, str(exc)

        results = await asyncio.gather(*(classify(a) for a in advertisers))

        for adv_id, assessment, err in results:
            if err is not None:
                errors.append(f"advertiser {adv_id}: {err}")
                continue
            if assessment is None:
                continue
            processed += 1
            if assessment.is_taxable:
                await repo.upsert(adv_id, assessment, model=settings.tax_model)
                taxable += 1

        await session.commit()

    elapsed_ms = (time.monotonic() - t0) * 1000
    logger.info(
        "Tax classification complete: %d processed, %d taxable, %d errors (%.0f ms).",
        processed,
        taxable,
        len(errors),
        elapsed_ms,
    )
    return {
        "processed": processed,
        "taxable": taxable,
        "errors": errors,
        "elapsed_ms": elapsed_ms,
    }
