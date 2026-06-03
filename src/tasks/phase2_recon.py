"""Phase 2 recon task — fanned out per advertiser via Celery chord from Phase 1.

Filled in by tasks #6 and #7 (recon framework and search adapter). For now
this file declares the task signatures so Phase 1 can chord-dispatch them.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="tasks.phase2_recon.recon_advertiser_job", bind=True)
def recon_advertiser_job(self, advertiser_id: int) -> dict[str, Any]:
    """Run all enabled recon sources for one advertiser."""
    return asyncio.run(_run_recon(advertiser_id))


async def _run_recon(advertiser_id: int) -> dict[str, Any]:
    # Imported lazily so the celery app can boot without the recon framework
    # being wired up (it's filled in by task #6).
    from backend.database import AsyncSessionLocal
    from db.repositories import AdvertiserRepository, ReconRepository
    from recon.registry import build_default_coordinator

    async with AsyncSessionLocal() as session:
        advertiser = await AdvertiserRepository(session).get(advertiser_id)
        if advertiser is None:
            return {"advertiser_id": advertiser_id, "error": "not found"}

        coordinator = build_default_coordinator()
        findings = await coordinator.enrich(advertiser, session)

        recon_repo = ReconRepository(session)
        persisted = await recon_repo.add_findings(advertiser_id, [f.to_dict() for f in findings])
        await session.commit()

    return {"advertiser_id": advertiser_id, "findings": persisted}


@shared_task(name="tasks.phase2_recon.finalize_recon")
def finalize_recon(results: list[dict[str, Any]], job_id: int) -> dict[str, Any]:
    """Chord callback after all per-advertiser recon tasks finish."""
    total_findings = sum(int(r.get("findings", 0) or 0) for r in results if isinstance(r, dict))
    logger.info(
        f"Recon complete for job {job_id}: {len(results)} advertisers processed, "
        f"{total_findings} findings persisted"
    )
    return {"job_id": job_id, "advertisers": len(results), "findings": total_findings}
