"""Search-engine recon adapter — DuckDuckGo HTML, no API key required.

Queries DuckDuckGo with several templates (including contact-specific
ones), parses result URLs and snippets, and produces ``mention``,
``email``, and ``phone`` findings by running the shared extractors
against each snippet.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.db.models import Advertiser
from recon.base import ReconFindingData, ReconSource
from recon.extractors import extract_emails, extract_phones

logger = logging.getLogger(__name__)

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class SearchEngineRecon(ReconSource):
    """Tier-2 recon: DuckDuckGo HTML search for advertiser mentions."""

    name = "search"

    QUERY_TEMPLATES: tuple[str, ...] = (
        '"{name}" akwa ibom contact',
        '"{name}" akwa ibom email phone',
        '"{name}" business profile nigeria',
        # Contact-specific queries
        '"{name}" email address contact',
        '"{name}" phone number whatsapp',
    )

    async def _enrich_impl(
        self, advertiser: Advertiser, session: AsyncSession
    ) -> list[ReconFindingData]:
        if not advertiser.name:
            return []

        findings: list[ReconFindingData] = []
        settings = get_settings()

        async with httpx.AsyncClient(
            timeout=15.0, headers=DEFAULT_HEADERS, follow_redirects=True
        ) as client:
            for template in self.QUERY_TEMPLATES:
                query = template.format(name=advertiser.name)
                try:
                    results = await self._search(client, query)
                except Exception as exc:
                    logger.warning("[search] Query failed '%s': %s", query, exc)
                    results = []

                for r in results[:5]:
                    # Standard mention finding
                    findings.append(
                        ReconFindingData(
                            source=self.name,
                            kind="mention",
                            value=r["url"],
                            confidence=0.4,
                            raw_json={
                                "query": query,
                                "title": r.get("title"),
                                "snippet": r.get("snippet"),
                            },
                        )
                    )

                    # Extract emails and phones from the snippet text
                    snippet = r.get("snippet") or ""
                    title = r.get("title") or ""
                    combined = f"{title} {snippet}"

                    snippet_meta = {
                        "query": query,
                        "source_url": r["url"],
                        "snippet": snippet,
                    }

                    for email in extract_emails(combined):
                        findings.append(
                            ReconFindingData(
                                source=self.name,
                                kind="email",
                                value=email,
                                confidence=0.5,
                                raw_json=snippet_meta,
                            )
                        )

                    for phone in extract_phones(combined, max_results=2):
                        findings.append(
                            ReconFindingData(
                                source=self.name,
                                kind="phone",
                                value=phone,
                                confidence=0.4,
                                raw_json=snippet_meta,
                            )
                        )

                await asyncio.sleep(settings.recon_search_delay_seconds)

        if findings:
            logger.info(
                "[search] %d findings for advertiser=%s",
                len(findings), advertiser.id,
            )
        return findings

    # ------------------------------------------------------------------
    # DuckDuckGo HTML scraper
    # ------------------------------------------------------------------

    async def _search(
        self, client: httpx.AsyncClient, query: str
    ) -> list[dict[str, Any]]:
        """POST to DuckDuckGo HTML and parse the results page."""
        resp = await client.post(DDG_HTML_URL, data={"q": query})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results: list[dict[str, Any]] = []
        for result_div in soup.select("div.result"):
            link_el = result_div.select_one("a.result__a")
            snippet_el = result_div.select_one("a.result__snippet")
            if not link_el:
                continue
            href = link_el.get("href")
            title = link_el.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True) if snippet_el else None
            if not href:
                continue
            results.append({"url": href, "title": title, "snippet": snippet})
        return results
