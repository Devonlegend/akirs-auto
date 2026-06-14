from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models.scraped import Advertiser


def _ordered_unique(values):
    """Dedupe while preserving first-seen order, dropping falsy entries."""
    seen = set()
    out = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _enrich(advertiser: Advertiser) -> dict:
    findings = advertiser.recon_findings or []
    emails = _ordered_unique(f.value for f in findings if f.kind == "email")
    phones = _ordered_unique(f.value for f in findings if f.kind == "phone")
    addresses = _ordered_unique(f.value for f in findings if f.kind == "address")
    sources = _ordered_unique(f.source for f in findings)

    platforms = _ordered_unique(
        [link.platform for link in (advertiser.social_links or [])]
        + [profile.platform for profile in (advertiser.social_profiles or [])]
    )

    follower_counts = [
        profile.follower_count
        for profile in (advertiser.social_profiles or [])
        if profile.follower_count is not None
    ]
    followers = max(follower_counts) if follower_counts else None

    return {
        "id": advertiser.id,
        "name": advertiser.name,
        "fb_url": advertiser.fb_url,
        "first_seen": advertiser.first_seen,
        "last_seen": advertiser.last_seen,
        "platforms": platforms,
        "social_links": list(advertiser.social_links or []),
        "emails": emails,
        "phones": phones,
        "addresses": addresses,
        "followers": followers,
        "sources": sources,
    }


def _query():
    return select(Advertiser).options(
        selectinload(Advertiser.social_links),
        selectinload(Advertiser.recon_findings),
        selectinload(Advertiser.social_profiles),
    )


async def get_advertisers(db: AsyncSession):
    result = await db.execute(_query())
    return [_enrich(a) for a in result.scalars().all()]


async def get_advertiser(db: AsyncSession, advertiser_id: int):
    result = await db.execute(_query().where(Advertiser.id == advertiser_id))
    advertiser = result.scalars().first()
    return _enrich(advertiser) if advertiser else None
