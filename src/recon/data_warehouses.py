"""Adapter for generic data warehouses / scraped 3rd-party datasets (PDL, Brave Search)."""

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from src.config.settings import get_settings
from src.db.models import Advertiser, WarehouseVote
from recon.base import ReconFindingData, ReconSource

logger = logging.getLogger(__name__)


class DataWarehouseRecon(ReconSource):
    name = "warehouse"

    async def _enrich_impl(
        self, advertiser: Advertiser, session: AsyncSession
    ) -> list[ReconFindingData]:
        settings = get_settings()
        pdl_key = settings.pdl_api_key
        brave_key = settings.brave_search_api_key

        tasks = []
        if pdl_key:
            tasks.append(self._fetch_pdl(advertiser, pdl_key))
        if brave_key:
            tasks.append(self._fetch_brave(advertiser, brave_key))

        if not tasks:
            logger.info(f"[warehouse] no API keys configured for PDL/Brave — skipping advertiser {advertiser.id}")
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        findings_by_kind: dict[str, dict[str, list]] = {} # kind -> {value -> [providers]}
        votes: list[WarehouseVote] = []

        providers_run = []
        if pdl_key: providers_run.append("pdl")
        if brave_key: providers_run.append("brave")

        for provider, res in zip(providers_run, results):
            if isinstance(res, Exception):
                logger.error(f"[warehouse] {provider} failed for {advertiser.id}: {res}")
                continue
            
            for finding in res:
                kind = finding["kind"]
                val = finding["value"]
                conf = finding.get("confidence", 0.5)
                
                votes.append(
                    WarehouseVote(
                        advertiser_id=advertiser.id,
                        provider=provider,
                        kind=kind,
                        value=val,
                        confidence=conf,
                        raw_json=finding.get("raw_json", {})
                    )
                )

                if kind not in findings_by_kind:
                    findings_by_kind[kind] = {}
                if val not in findings_by_kind[kind]:
                    findings_by_kind[kind][val] = []
                findings_by_kind[kind][val].append(provider)

        session.add_all(votes)

        merged_findings = []
        for kind, values_dict in findings_by_kind.items():
            for val, providers in values_dict.items():
                # Prioritize PDL for confidence
                conf = 0.9 if "pdl" in providers else 0.7
                merged_findings.append(
                    ReconFindingData(
                        source=self.name,
                        kind=kind,
                        value=val,
                        confidence=conf,
                        raw_json={"providers": providers}
                    )
                )

        return merged_findings

    async def _fetch_pdl(self, advertiser: Advertiser, api_key: str) -> list[dict[str, Any]]:
        name = advertiser.name or ""
        if not name:
            return []
            
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                # PDL Company Enrichment API
                resp = await client.get(
                    "https://api.peopledatalabs.com/v5/company/enrich",
                    params={"name": name, "api_key": api_key}
                )
                findings = []
                if resp.status_code == 200:
                    data = resp.json()
                    
                    if website := data.get("website"):
                        findings.append({"kind": "website", "value": website, "confidence": 0.9, "raw_json": data})
                    if industry := data.get("industry"):
                        findings.append({"kind": "industry", "value": industry, "confidence": 0.9, "raw_json": data})
                    if location := data.get("location", {}).get("name"):
                        findings.append({"kind": "address", "value": location, "confidence": 0.8, "raw_json": data})
                        
                return findings
            except Exception as e:
                logger.warning(f"PDL fetch failed for {name}: {e}")
                return []

    async def _fetch_brave(self, advertiser: Advertiser, api_key: str) -> list[dict[str, Any]]:
        name = advertiser.name or ""
        if not name:
            return []
            
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                # Brave Search API
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={"Accept": "application/json", "X-Subscription-Token": api_key},
                    params={"q": f'"{name}" company contact info'}
                )
                findings = []
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("web", {}).get("results", [])
                    if results:
                        # Extract the top result's URL as a potential website
                        top_result = results[0]
                        if url := top_result.get("url"):
                            findings.append({"kind": "website", "value": url, "confidence": 0.7, "raw_json": top_result})
                return findings
            except Exception as e:
                logger.warning(f"Brave Search fetch failed for {name}: {e}")
                return []
