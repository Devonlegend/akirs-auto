"""Phase 2 recon framework: ReconSource ABC + ReconCoordinator.

Each ReconSource implements `enrich(advertiser, session) -> list[ReconFindingData]`
and carries its own asyncio.Semaphore to throttle outbound traffic.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Advertiser

logger = logging.getLogger(__name__)


@dataclass
class ReconFindingData:
    source: str
    kind: str
    value: str
    confidence: float = 0.5
    raw_json: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReconSource(ABC):
    """Adapter contract for a single recon data source."""

    name: str = "base"

    def __init__(self, *, enabled: bool = True, concurrency: int = 1) -> None:
        self.enabled = enabled
        self.semaphore = asyncio.Semaphore(concurrency)

    @abstractmethod
    async def _enrich_impl(
        self, advertiser: Advertiser, session: AsyncSession
    ) -> list[ReconFindingData]: ...

    async def enrich(
        self, advertiser: Advertiser, session: AsyncSession
    ) -> list[ReconFindingData]:
        if not self.enabled:
            logger.info(f"Recon source '{self.name}' disabled — skipping for advertiser {advertiser.id}")
            return []
        async with self.semaphore:
            try:
                return await self._enrich_impl(advertiser, session)
            except Exception as e:
                logger.exception(f"Recon source '{self.name}' failed for advertiser {advertiser.id}: {e}")
                return []


class ReconCoordinator:
    """Runs all registered sources in parallel for a single advertiser."""

    def __init__(self, sources: list[ReconSource]):
        self.sources = sources

    async def enrich(
        self, advertiser: Advertiser, session: AsyncSession
    ) -> list[ReconFindingData]:
        tasks = [src.enrich(advertiser, session) for src in self.sources]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        flat: list[ReconFindingData] = []
        for batch in results:
            flat.extend(batch)
        return flat


class FallbackReconCoordinator:
    """Runs recon sources in tiered fallback stages.
    
    Tiers are evaluated sequentially. Sources within a tier run in parallel.
    If a tier produces specific high-value findings (like email or phone),
    we stop and return, skipping subsequent, more expensive tiers.
    """

    def __init__(self, tiers: list[list[ReconSource]], stop_conditions: set[str] = None):
        self.tiers = tiers
        # If any of these kinds are found in a tier, we stop processing further tiers
        self.stop_conditions = stop_conditions or {"email", "phone"}

    async def enrich(
        self, advertiser: Advertiser, session: AsyncSession
    ) -> list[ReconFindingData]:
        all_findings = []
        for i, tier in enumerate(self.tiers):
            if not tier:
                continue
                
            logger.info(f"Running fallback tier {i + 1} for advertiser {advertiser.id}")
            tasks = [src.enrich(advertiser, session) for src in tier]
            results = await asyncio.gather(*tasks, return_exceptions=False)
            
            tier_findings: list[ReconFindingData] = []
            for batch in results:
                tier_findings.extend(batch)
                
            all_findings.extend(tier_findings)
            
            # Check if stop conditions are met
            found_kinds = {f.kind for f in tier_findings}
            if self.stop_conditions.intersection(found_kinds):
                logger.info(f"Stop conditions met in tier {i + 1} for advertiser {advertiser.id}. Skipping remaining tiers.")
                break
                
        return all_findings
