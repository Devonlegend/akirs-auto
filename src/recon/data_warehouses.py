"""Stub adapter for generic data warehouses / scraped 3rd-party datasets."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from akirs.db.models import Advertiser
from akirs.recon.base import ReconFindingData, ReconSource

logger = logging.getLogger(__name__)


class DataWarehouseRecon(ReconSource):
    name = "warehouse"

    async def _enrich_impl(
        self, advertiser: Advertiser, session: AsyncSession
    ) -> list[ReconFindingData]:
        logger.info(f"[warehouse] not yet implemented — advertiser={advertiser.id} ({advertiser.name})")
        return []
