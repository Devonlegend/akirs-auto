"""Recon source: OpenStreetMap Nominatim — free geocoder for hq_address.

Free, no API key required. Subject to Nominatim's usage policy:
    https://operations.osmfoundation.org/policies/nominatim/

Policy compliance built in:
    * Sends a descriptive User-Agent (required).
    * Hard 1 req/sec cap via asyncio.sleep — never exceed it.
    * Single query per advertiser (cheap on their servers).
    * Restricted to Nigeria via ``countrycodes=ng`` and biased to Akwa Ibom
      via a viewbox around Uyo.

Produces:
    * ``address`` — formatted display name from OSM

Runs in Tier 2 so it costs nothing AND finishes before the paid TomTom call
in Tier 3. TomTom still runs after to add phone + verified POI name —
``address`` is not in the FallbackReconCoordinator stop conditions, so Tier 3
is not skipped.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Advertiser
from recon.base import ReconFindingData, ReconSource

logger = logging.getLogger(__name__)

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HTTP_TIMEOUT = 15.0

# Akwa Ibom viewbox: roughly (west, north, east, south) around Uyo + state edges.
# Nominatim accepts ``viewbox=lon1,lat1,lon2,lat2`` with bounded=1 to bias hard.
_AKS_VIEWBOX = "7.50,5.55,8.40,4.45"

# Required by Nominatim policy.
_USER_AGENT = "akirs-recon/0.2 (Akwa Ibom business intelligence)"

# Self-imposed minimum delay between requests (1 req/sec is the policy ceiling).
_MIN_INTERVAL_S = 1.1


class NominatimRecon(ReconSource):
    """Tier-2 recon: free OSM Nominatim address lookup, no key required."""

    name = "nominatim"

    # Module-level lock so concurrent advertisers can't accidentally race past
    # the 1 req/sec policy even if multiple instances run in parallel.
    _global_lock: asyncio.Lock = asyncio.Lock()
    _last_call_at: float = 0.0

    async def _enrich_impl(
        self, advertiser: Advertiser, session: AsyncSession
    ) -> list[ReconFindingData]:
        if not advertiser.name:
            return []

        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": _USER_AGENT, "Accept-Language": "en"},
        ) as client:
            results = await self._query(client, advertiser.name)

        findings: list[ReconFindingData] = []
        for r in results:
            display = r.get("display_name")
            if not display:
                continue
            importance = float(r.get("importance", 0.0))
            findings.append(ReconFindingData(
                source=self.name,
                kind="address",
                value=display,
                confidence=min(1.0, importance + 0.2),  # Nominatim importance is conservative
                raw_json={
                    "api": "nominatim",
                    "query": advertiser.name,
                    "osm_type": r.get("osm_type"),
                    "osm_id": r.get("osm_id"),
                    "lat": r.get("lat"),
                    "lon": r.get("lon"),
                },
            ))

        if findings:
            logger.info(
                "[nominatim] %d findings for advertiser=%s",
                len(findings), advertiser.id,
            )
        return findings

    # ------------------------------------------------------------------
    # Policy-compliant request helper
    # ------------------------------------------------------------------

    async def _query(self, client: httpx.AsyncClient, name: str) -> list[dict]:
        params = {
            "q": name,
            "format": "json",
            "addressdetails": 1,
            "limit": 3,
            "countrycodes": "ng",
            "viewbox": _AKS_VIEWBOX,
            "bounded": 1,
        }

        async with self._global_lock:
            wait = _MIN_INTERVAL_S - (asyncio.get_event_loop().time() - self._last_call_at)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                resp = await client.get(_NOMINATIM_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "[nominatim] HTTP %s for %r: %s",
                    exc.response.status_code, name, exc,
                )
                data = []
            except Exception:
                logger.exception("[nominatim] error for %r", name)
                data = []
            finally:
                type(self)._last_call_at = asyncio.get_event_loop().time()

        return data if isinstance(data, list) else []
