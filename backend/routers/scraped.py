from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.schemas import scraped as schemas
from backend.services import scraped as services

router = APIRouter(prefix="/scraped", tags=["Scraped Data"])
DbDep = Annotated[AsyncSession, Depends(get_db)]

@router.get("/advertisers/", response_model=List[schemas.AdvertiserEnriched])
async def get_advertisers(db: DbDep):
    return await services.get_advertisers(db)

@router.get("/advertisers/{advertiser_id}", response_model=schemas.AdvertiserEnriched)
async def get_advertiser(advertiser_id: int, db: DbDep):
    advertiser = await services.get_advertiser(db, advertiser_id)
    if advertiser is None:
        raise HTTPException(status_code=404, detail="Advertiser not found")
    return advertiser
