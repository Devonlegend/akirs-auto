"""Geography routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import db_session
from src.api.schemas import GeographyOut
from src.db.models import Geography

router = APIRouter(prefix="/geography", tags=["geography"])


@router.get("/akwa-ibom", response_model=list[GeographyOut])
async def list_akwa_ibom(session: AsyncSession = Depends(db_session)) -> list[GeographyOut]:
    state_result = await session.execute(
        select(Geography).where(Geography.kind == "state").where(Geography.name == "Akwa Ibom")
    )
    akwa_ibom = state_result.scalar_one_or_none()
    if akwa_ibom is None:
        return []

    result = await session.execute(
        select(Geography)
        .where((Geography.id == akwa_ibom.id) | (Geography.parent_id == akwa_ibom.id))
        .order_by(Geography.kind, Geography.name)
    )
    return [
        GeographyOut(id=g.id, name=g.name, kind=g.kind, parent_id=g.parent_id)
        for g in result.scalars().all()
    ]


@router.get("/nigeria", response_model=list[GeographyOut])
async def list_nigeria(session: AsyncSession = Depends(db_session)) -> list[GeographyOut]:
    result = await session.execute(select(Geography).order_by(Geography.kind, Geography.name))
    return [
        GeographyOut(id=g.id, name=g.name, kind=g.kind, parent_id=g.parent_id)
        for g in result.scalars().all()
    ]
