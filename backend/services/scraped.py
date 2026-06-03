from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.scraped import Advertiser

async def get_advertisers(db: AsyncSession):
    result = await db.execute(select(Advertiser))
    return result.scalars().all()
