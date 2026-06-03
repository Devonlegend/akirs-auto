"""Advertiser routes — list, detail, findings, CSV export."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from akirs.api.deps import db_session
from akirs.api.schemas import AdvertiserOut, ReconFindingOut, SocialLinkOut
from akirs.db.models import Advertiser, ReconFinding
from akirs.exporters import CSVExportService

router = APIRouter(prefix="/advertisers", tags=["advertisers"])


def _to_out(adv: Advertiser) -> AdvertiserOut:
    return AdvertiserOut(
        id=adv.id,
        name=adv.name,
        fb_url=adv.fb_url,
        first_seen=adv.first_seen,
        last_seen=adv.last_seen,
        social_links=[SocialLinkOut(platform=l.platform, url=l.url) for l in adv.social_links],
    )


@router.get("", response_model=list[AdvertiserOut])
async def list_advertisers(
    limit: int = 100,
    session: AsyncSession = Depends(db_session),
) -> list[AdvertiserOut]:
    result = await session.execute(
        select(Advertiser).options(selectinload(Advertiser.social_links)).limit(limit)
    )
    return [_to_out(a) for a in result.scalars().all()]


@router.get("/export.csv")
async def export_csv(session: AsyncSession = Depends(db_session)) -> Response:
    body = await CSVExportService(session).to_string()
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ads_social_links.csv"},
    )


@router.get("/{advertiser_id}", response_model=AdvertiserOut)
async def get_advertiser(
    advertiser_id: int,
    session: AsyncSession = Depends(db_session),
) -> AdvertiserOut:
    result = await session.execute(
        select(Advertiser)
        .options(selectinload(Advertiser.social_links))
        .where(Advertiser.id == advertiser_id)
    )
    adv = result.scalar_one_or_none()
    if adv is None:
        raise HTTPException(status_code=404, detail="advertiser not found")
    return _to_out(adv)


@router.get("/{advertiser_id}/findings", response_model=list[ReconFindingOut])
async def get_findings(
    advertiser_id: int,
    session: AsyncSession = Depends(db_session),
) -> list[ReconFindingOut]:
    if await session.get(Advertiser, advertiser_id) is None:
        raise HTTPException(status_code=404, detail="advertiser not found")
    result = await session.execute(
        select(ReconFinding).where(ReconFinding.advertiser_id == advertiser_id)
    )
    return [
        ReconFindingOut(
            id=f.id,
            source=f.source,
            kind=f.kind,
            value=f.value,
            confidence=f.confidence,
            found_at=f.found_at,
        )
        for f in result.scalars().all()
    ]
