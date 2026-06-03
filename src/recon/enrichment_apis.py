"""Recon source: paid enrichment APIs (Hunter.io, Apollo.io).

Extracts the domain from advertiser website URLs, then queries whichever
third-party enrichment APIs have keys configured in the environment.
Auto-disables itself when **no** API keys are present.
"""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from db.models import Advertiser, SocialLink
from recon.base import ReconFindingData, ReconSource
from recon.extractors import extract_domain

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 15.0


class EnrichmentAPIRecon(ReconSource):
    """Tier-3 recon: Hunter.io and Apollo.io enrichment."""

    name = "enrichment"

    def __init__(self, **kw) -> None:
        settings = get_settings()
        self._hunter_key: str | None = settings.hunter_api_key
        self._apollo_key: str | None = settings.apollo_api_key
        # Disable entirely if no keys are available.
        kw.setdefault("enabled", bool(self._hunter_key or self._apollo_key))
        super().__init__(**kw)

    # ------------------------------------------------------------------
    # ReconSource implementation
    # ------------------------------------------------------------------

    async def _enrich_impl(
        self, advertiser: Advertiser, session: AsyncSession
    ) -> list[ReconFindingData]:
        domains = await self._get_domains(advertiser, session)
        if not domains:
            logger.debug(
                "[enrichment] No website domains for advertiser=%s", advertiser.id
            )
            return []

        findings: list[ReconFindingData] = []

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            for domain in domains:
                if self._hunter_key:
                    findings.extend(await self._query_hunter(client, domain))
                if self._apollo_key:
                    findings.extend(
                        await self._query_apollo(client, domain, advertiser.name)
                    )

        if findings:
            logger.info(
                "[enrichment] %d findings via APIs for advertiser=%s",
                len(findings), advertiser.id,
            )
        return findings

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_domains(
        advertiser: Advertiser, session: AsyncSession
    ) -> list[str]:
        """Return unique domains from the advertiser's website social links."""
        stmt = select(SocialLink.url).where(
            SocialLink.advertiser_id == advertiser.id,
            SocialLink.platform == "website",
        )
        result = await session.execute(stmt)
        urls: list[str] = [row[0] for row in result.all()]
        seen: set[str] = set()
        domains: list[str] = []
        for url in urls:
            dom = extract_domain(url)
            if dom and dom not in seen:
                seen.add(dom)
                domains.append(dom)
        return domains

    # ------------------------------------------------------------------
    # Hunter.io
    # ------------------------------------------------------------------

    async def _query_hunter(
        self, client: httpx.AsyncClient, domain: str
    ) -> list[ReconFindingData]:
        """Call the Hunter.io domain-search endpoint."""
        findings: list[ReconFindingData] = []
        url = "https://api.hunter.io/v2/domain-search"
        params = {"domain": domain, "api_key": self._hunter_key, "limit": 10}

        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json().get("data", {})
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "[enrichment] Hunter API HTTP %s for %s: %s",
                exc.response.status_code, domain, exc,
            )
            return findings
        except Exception:
            logger.exception("[enrichment] Hunter API error for %s", domain)
            return findings

        raw_meta = {"api": "hunter", "domain": domain}

        for email_obj in data.get("emails", []):
            email_val = email_obj.get("value")
            if not email_val:
                continue
            confidence = (email_obj.get("confidence", 50)) / 100.0
            findings.append(ReconFindingData(
                source=self.name, kind="email", value=email_val,
                confidence=confidence, raw_json={**raw_meta, "hunter": email_obj},
            ))

            # Capture associated job title / name if present.
            first = email_obj.get("first_name", "")
            last = email_obj.get("last_name", "")
            position = email_obj.get("position")
            if position:
                findings.append(ReconFindingData(
                    source=self.name, kind="job_title",
                    value=f"{first} {last} — {position}".strip(),
                    confidence=confidence,
                    raw_json=raw_meta,
                ))

        org = data.get("organization")
        if org:
            findings.append(ReconFindingData(
                source=self.name, kind="company_name", value=org,
                confidence=0.8, raw_json=raw_meta,
            ))

        return findings

    # ------------------------------------------------------------------
    # Apollo.io
    # ------------------------------------------------------------------

    async def _query_apollo(
        self,
        client: httpx.AsyncClient,
        domain: str,
        advertiser_name: str | None,
    ) -> list[ReconFindingData]:
        """Call the Apollo.io mixed people/org search endpoint."""
        findings: list[ReconFindingData] = []
        url = "https://api.apollo.io/v1/mixed_people/search"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
        }
        payload: dict = {
            "api_key": self._apollo_key,
            "q_organization_domains": domain,
            "page": 1,
            "per_page": 10,
        }

        try:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "[enrichment] Apollo API HTTP %s for %s: %s",
                exc.response.status_code, domain, exc,
            )
            return findings
        except Exception:
            logger.exception("[enrichment] Apollo API error for %s", domain)
            return findings

        raw_meta = {"api": "apollo", "domain": domain}

        for person in data.get("people", []):
            email_val = person.get("email")
            if email_val:
                findings.append(ReconFindingData(
                    source=self.name, kind="email", value=email_val,
                    confidence=0.75, raw_json=raw_meta,
                ))

            phone_val = (
                person.get("phone_number")
                or (person.get("phone_numbers") or [{}])[0].get("sanitized_number")
            )
            if phone_val:
                findings.append(ReconFindingData(
                    source=self.name, kind="phone", value=phone_val,
                    confidence=0.7, raw_json=raw_meta,
                ))

            title = person.get("title")
            name = person.get("name", "")
            if title:
                findings.append(ReconFindingData(
                    source=self.name, kind="job_title",
                    value=f"{name} — {title}".strip(" —"),
                    confidence=0.7, raw_json=raw_meta,
                ))

        # Organisation-level info
        for org in data.get("organizations", []):
            org_name = org.get("name")
            if org_name:
                findings.append(ReconFindingData(
                    source=self.name, kind="company_name", value=org_name,
                    confidence=0.8, raw_json=raw_meta,
                ))

        return findings
