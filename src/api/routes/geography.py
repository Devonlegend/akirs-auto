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
    result = await session.execute(select(Geography).order_by(Geography.kind, Geography.name))
    return [
        GeographyOut(id=g.id, name=g.name, kind=g.kind, parent_id=g.parent_id)
        for g in result.scalars().all()
    ]
