from typing import Annotated, List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.schemas import scraped as schemas
from backend.services import scraped as services

router = APIRouter(prefix="/scraped", tags=["Scraped Data"])
DbDep = Annotated[AsyncSession, Depends(get_db)]

@router.get("/advertisers/", response_model=List[schemas.Advertiser])
async def get_advertisers(db: DbDep):
    return await services.get_advertisers(db)
