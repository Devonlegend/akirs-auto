"""CSV exporter — reads from the DB and emits the enriched column layout.

Includes Phase 1 scrape data (advertiser + social links) alongside Phase 2
recon enrichment data (emails, phones, sources) in a single flat CSV.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, UTC
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from akirs.db.models import Advertiser, ReconFinding, SocialLink

logger = logging.getLogger(__name__)

CSV_FIELDS = (
    "ad_id",
    "advertiser_name",
    "advertiser_url",
    "social_platform",
    "social_url",
    "recon_emails",
    "recon_phones",
    "recon_sources",
    "scraped_at",
)


class CSVExportService:
    """Renders advertisers + social links + recon findings into an enriched CSV."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _aggregate_recon(findings: list[ReconFinding]) -> dict[str, str]:
        """Aggregate recon findings into semicolon-separated email, phone, and source strings.

        Args:
            findings: List of ReconFinding ORM objects for a single advertiser.

        Returns:
            Dict with keys ``recon_emails``, ``recon_phones``, ``recon_sources``.
        """
        emails: list[str] = []
        phones: list[str] = []
        sources: set[str] = set()

        for finding in findings:
            if finding.kind == "email":
                emails.append(finding.value)
            elif finding.kind == "phone":
                phones.append(finding.value)
            sources.add(finding.source)

        return {
            "recon_emails": "; ".join(dict.fromkeys(emails)),  # dedupe preserving order
            "recon_phones": "; ".join(dict.fromkeys(phones)),
            "recon_sources": "; ".join(sorted(sources)),
        }

    async def _rows(self) -> list[dict]:
        """Fetch all advertisers with eager-loaded social links and recon findings.

        Each advertiser × social-link pair becomes one CSV row. If an advertiser
        has no social links, a single row is still emitted with empty social
        columns. Recon data is duplicated across all rows for the same advertiser
        so that every row carries the full enrichment context.
        """
        result = await self.session.execute(
            select(Advertiser).options(
                selectinload(Advertiser.social_links),
                selectinload(Advertiser.recon_findings),
            )
        )
        advertisers = result.scalars().all()
        rows: list[dict] = []

        for adv in advertisers:
            scraped_at = (adv.last_seen or datetime.now(UTC)).isoformat()
            recon_agg = self._aggregate_recon(adv.recon_findings)
            base = {
                "ad_id": f"ad_{adv.id}",
                "advertiser_name": adv.name or "",
                "advertiser_url": adv.fb_url,
                **recon_agg,
                "scraped_at": scraped_at,
            }
            if not adv.social_links:
                rows.append({**base, "social_platform": "", "social_url": ""})
                continue
            for link in adv.social_links:
                rows.append({**base, "social_platform": link.platform, "social_url": link.url})

        logger.debug("Prepared %d CSV rows from %d advertisers", len(rows), len(advertisers))
        return rows

    async def to_string(self) -> str:
        """Render the full CSV as a string."""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(await self._rows())
        return buf.getvalue()

    async def to_file(self, path: Path | str) -> Path:
        """Write the CSV to *path*, creating parent directories as needed.

        Returns:
            The resolved ``Path`` that was written to.
        """
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(await self.to_string(), encoding="utf-8")
        logger.info("CSV exported to %s", out)
        return out

