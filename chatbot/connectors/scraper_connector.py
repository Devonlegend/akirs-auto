"""Scraper connector — reads akirs.db and feeds advertiser data into the ingestion pipeline.

This is an *optional* bridge.  The core chatbot works perfectly without it —
just use ``POST /chatbot/ingest`` to feed arbitrary text.  This connector
simply knows how to turn the scraper's relational data into structured text
blobs and push them through the same generic ingestion pipeline.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from chatbot.ingestion.ingestor import Ingestor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Advertiser → text-blob builder
# ---------------------------------------------------------------------------


def build_advertiser_text(adv: object) -> str:
    """Convert an advertiser ORM object + its relationships into a human-readable text blob.

    The Advertiser object is expected to have eager-loaded relationships:
    ``social_links``, ``recon_findings``, ``social_profiles``,
    ``registry_records``, ``warehouse_votes``.

    Args:
        adv: An ORM ``Advertiser`` instance.

    Returns:
        A structured text representation suitable for embedding.
    """
    lines: list[str] = []

    # -- Name & URL ----------------------------------------------------------
    name = getattr(adv, "name", None)
    fb_url = getattr(adv, "fb_url", "")
    if name:
        lines.append(f"Business: {name}")
    if fb_url:
        lines.append(f"Facebook URL: {fb_url}")

    # -- First / last seen ---------------------------------------------------
    first = getattr(adv, "first_seen", None)
    last = getattr(adv, "last_seen", None)
    if first:
        lines.append(f"First Seen: {first.isoformat()}")
    if last:
        lines.append(f"Last Seen: {last.isoformat()}")

    # -- Social links --------------------------------------------------------
    social_links: list = getattr(adv, "social_links", []) or []
    if social_links:
        platforms: dict[str, list[str]] = {}
        for sl in social_links:
            plat = getattr(sl, "platform", "other")
            url = getattr(sl, "url", "")
            platforms.setdefault(plat, []).append(url)
        lines.append("Social Links:")
        for plat, urls in sorted(platforms.items()):
            for url in urls:
                lines.append(f"  {plat}: {url}")

    # -- Social profiles -----------------------------------------------------
    social_profiles: list = getattr(adv, "social_profiles", []) or []
    if social_profiles:
        lines.append("Social Profiles:")
        for sp in social_profiles:
            plat = getattr(sp, "platform", "?")
            handle = getattr(sp, "handle", "")
            bio = getattr(sp, "bio", "")
            followers = getattr(sp, "follower_count", None)
            parts = [f"  {plat}"]
            if handle:
                parts.append(f"@{handle}")
            if followers is not None:
                parts.append(f"({followers:,} followers)")
            lines.append(" ".join(parts))
            if bio:
                lines.append(f"    Bio: {bio}")

    # -- Recon findings (emails, phones, addresses, etc.) --------------------
    recon_findings: list = getattr(adv, "recon_findings", []) or []
    if recon_findings:
        by_kind: dict[str, list[tuple[str, float, str]]] = {}
        for rf in recon_findings:
            kind = getattr(rf, "kind", "other")
            value = getattr(rf, "value", "")
            conf = getattr(rf, "confidence", 0.5)
            source = getattr(rf, "source", "?")
            by_kind.setdefault(kind, []).append((value, conf, source))

        for kind, items in sorted(by_kind.items()):
            unique_vals: dict[str, tuple[float, str]] = {}
            for v, c, s in items:
                if v not in unique_vals or c > unique_vals[v][0]:
                    unique_vals[v] = (c, s)
            label = kind.replace("_", " ").title()
            vals = ", ".join(
                f"{v} (conf: {c:.2f}, src: {s})" for v, (c, s) in sorted(unique_vals.items())
            )
            lines.append(f"{label}: {vals}")

    # -- Registry records ----------------------------------------------------
    registry_records: list = getattr(adv, "registry_records", []) or []
    if registry_records:
        lines.append("Registry:")
        for rr in registry_records:
            reg = getattr(rr, "registry", "?")
            rn = getattr(rr, "registration_number", "")
            status = getattr(rr, "status", "")
            parts = [f"  {reg}"]
            if rn:
                parts.append(f"RC: {rn}")
            if status:
                parts.append(f"({status})")
            lines.append(" ".join(parts))

    # -- Warehouse votes (PDL, Brave Search, etc.) ---------------------------
    warehouse_votes: list = getattr(adv, "warehouse_votes", []) or []
    if warehouse_votes:
        by_provider: dict[str, list[tuple[str, str, float]]] = {}
        for wv in warehouse_votes:
            provider = getattr(wv, "provider", "?")
            kind = getattr(wv, "kind", "?")
            value = getattr(wv, "value", "")
            conf = getattr(wv, "confidence", 0.5)
            by_provider.setdefault(provider, []).append((kind, value, conf))

        lines.append("Warehouse Data:")
        for provider, items in sorted(by_provider.items()):
            item_strs = [f"{k}: {v} ({c:.2f})" for k, v, c in items]
            lines.append(f"  {provider}: {' | '.join(item_strs)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_scraper_ingest(
    collection: str = "akirs_businesses",
    limit: int | None = None,
) -> dict:
    """Pull all advertisers from the scraper DB and ingest them into *collection*.

    Args:
        collection: Target ChromaDB collection name.
        limit: Optional max number of advertisers (useful for testing).

    Returns:
        Dict with keys ``collection``, ``advertisers_processed``,
        ``chunks_created``, ``errors``, ``elapsed_ms``.
    """
    t0 = time.monotonic()
    errors: list[str] = []

    # -- Lazy-import the scraper's database machinery ------------------------
    try:
        # Add src/ to the path so we can import from the scraper package.
        src_path = Path(__file__).resolve().parents[2] / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from db.base import get_engine, get_session_factory
        from db.models import (
            Advertiser,
            ReconFinding,
            RegistryRecord,
            SocialLink,
            SocialProfile,
            WarehouseVote,
        )
    except ImportError as exc:
        msg = f"Cannot import scraper models — is akirs.db available? ({exc})"
        logger.error(msg)
        return {
            "collection": collection,
            "advertisers_processed": 0,
            "chunks_created": 0,
            "errors": [msg],
            "elapsed_ms": (time.monotonic() - t0) * 1000,
        }

    # -- Query advertisers ---------------------------------------------------
    try:
        session_factory = get_session_factory()
    except Exception as exc:
        return {
            "collection": collection,
            "advertisers_processed": 0,
            "chunks_created": 0,
            "errors": [f"Database connection failed: {exc}"],
            "elapsed_ms": (time.monotonic() - t0) * 1000,
        }

    advertisers: list = []
    async with session_factory() as session:  # type: AsyncSession
        stmt = (
            select(Advertiser)
            .options(
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

        result = await session.execute(stmt)
        advertisers = list(result.scalars().unique())

    if not advertisers:
        logger.warning("No advertisers found in the scraper DB.")
        return {
            "collection": collection,
            "advertisers_processed": 0,
            "chunks_created": 0,
            "errors": ["No advertisers in database."],
            "elapsed_ms": (time.monotonic() - t0) * 1000,
        }

    logger.info("Loaded %d advertisers from scraper DB.", len(advertisers))

    # -- Build text blobs and ingest -----------------------------------------
    ingestor = Ingestor()
    total_chunks = 0
    processed = 0

    for adv in advertisers:
        adv_id = getattr(adv, "id", "?")
        adv_name = getattr(adv, "name", None) or f"advertiser_{adv_id}"

        try:
            text = build_advertiser_text(adv)
            if not text.strip():
                continue

            result = await ingestor.ingest(
                collection=collection,
                text=text,
                metadata={
                    "advertiser_id": adv_id,
                    "advertiser_name": str(adv_name)[:200],
                    "source": "facebook_ads_library",
                },
                doc_id=f"adv_{adv_id}",
            )
            total_chunks += result["chunks_created"]
            processed += 1
        except Exception as exc:
            err_msg = f"advertiser {adv_id} ({adv_name}): {exc}"
            logger.exception(err_msg)
            errors.append(err_msg)

    elapsed_ms = (time.monotonic() - t0) * 1000
    logger.info(
        "Scraper ingest complete: %d advertisers → %d chunks (%.0f ms).",
        processed,
        total_chunks,
        elapsed_ms,
    )

    return {
        "collection": collection,
        "advertisers_processed": processed,
        "chunks_created": total_chunks,
        "errors": errors,
        "elapsed_ms": elapsed_ms,
    }
