"""Recon source: TomTom Places API for physical address + phone enrichment.

Looks up the advertiser by name against the TomTom Search 2 / POI index,
restricted to Nigeria (``countrySet=NG``), and biased toward Akwa Ibom via
a geo-bias on Uyo's centroid. Auto-disables when no API key is configured.

Produces:
    * ``address``      — POI ``freeformAddress`` (1 finding per top hit)
    * ``phone``        — POI phone number (when present)
    * ``company_name`` — POI display name (often the verified legal name)

Stays inside the existing ReconSource contract so the FallbackReconCoordinator
can stop after this tier when high-value findings appear.
"""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from db.models import Advertiser
from recon.base import ReconFindingData, ReconSource

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 15.0
_SEARCH_URL_TPL = "https://api.tomtom.com/search/2/search/{q}.json"

# Uyo centroid — biases the search toward Akwa Ibom without filtering hard.
_UYO_LAT = 5.0382
_UYO_LON = 7.9128
_RADIUS_METERS = 150_000          # ~Akwa Ibom + neighbouring LGAs


class PlacesEnrichmentRecon(ReconSource):
    """Tier-3 recon: TomTom Places lookup for verified address + phone."""

    name = "places"

    def __init__(self, **kw) -> None:
        settings = get_settings()
        self._api_key: str | None = settings.tomtom_api_key
        # Disable entirely if no key is available — keeps the tier silent
        # for users who haven't provisioned TomTom credentials.
        kw.setdefault("enabled", bool(self._api_key))
        super().__init__(**kw)

    # ------------------------------------------------------------------
    # ReconSource implementation
    # ------------------------------------------------------------------

    async def _enrich_impl(
        self, advertiser: Advertiser, session: AsyncSession
    ) -> list[ReconFindingData]:
        if not advertiser.name:
            logger.debug("[places] advertiser=%s has no name — skipping", advertiser.id)
            return []

        findings: list[ReconFindingData] = []
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            findings.extend(await self._query_tomtom(client, advertiser.name))

        if findings:
            logger.info(
                "[places] %d findings for advertiser=%s",
                len(findings), advertiser.id,
            )
        return findings

    # ------------------------------------------------------------------
    # TomTom call
    # ------------------------------------------------------------------

    async def _query_tomtom(
        self, client: httpx.AsyncClient, name: str
    ) -> list[ReconFindingData]:
        """Single Search-2 lookup, geo-biased to Uyo, restricted to Nigeria."""
        findings: list[ReconFindingData] = []
        url = _SEARCH_URL_TPL.format(q=quote_plus(name.strip()))
        params = {
            "key": self._api_key,
            "countrySet": "NG",
            "lat": _UYO_LAT,
            "lon": _UYO_LON,
            "radius": _RADIUS_METERS,
            "idxSet": "POI",
            "limit": 3,
        }

        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "[places] TomTom HTTP %s for %r: %s",
                exc.response.status_code, name, exc,
            )
            return findings
        except Exception:
            logger.exception("[places] TomTom error for %r", name)
            return findings

        for result in data.get("results", []):
            findings.extend(self._extract_findings(name, result))

        return findings

    def _extract_findings(
        self, query_name: str, result: dict
    ) -> list[ReconFindingData]:
        """Convert one TomTom POI result into recon findings."""
        out: list[ReconFindingData] = []

        # TomTom returns score 0..10 — normalise to 0..1.
        confidence = min(1.0, float(result.get("score", 0)) / 10.0)
        poi = result.get("poi") or {}
        address = result.get("address") or {}
        raw_meta = {
            "api": "tomtom",
            "query": query_name,
            "tomtom_id": result.get("id"),
            "type": result.get("type"),
        }

        if formatted := address.get("freeformAddress"):
            out.append(ReconFindingData(
                source=self.name,
                kind="address",
                value=formatted,
                confidence=confidence,
                raw_json={**raw_meta, "address": address},
            ))

        if phone := poi.get("phone"):
            out.append(ReconFindingData(
                source=self.name,
                kind="phone",
                value=phone,
                confidence=confidence,
                raw_json=raw_meta,
            ))

        # POI "name" is often the verified legal / trading name — high value.
        if poi_name := poi.get("name"):
            out.append(ReconFindingData(
                source=self.name,
                kind="company_name",
                value=poi_name,
                # Slight discount: TomTom name ≠ legal name in every case.
                confidence=max(confidence - 0.1, 0.0),
                raw_json=raw_meta,
            ))

        return out
