"""Data models for ad scraping."""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime


@dataclass
class SocialLink:
    """Represents a social media link found in an ad."""

    platform: str  # e.g., "facebook", "instagram", "twitter", "tiktok"
    url: str

    def to_dict(self):
        return asdict(self)


@dataclass
class AdDetails:
    """Represents details extracted from a Facebook ad."""

    ad_id: str
    advertiser_name: str
    advertiser_url: Optional[str] = None
    social_links: List[SocialLink] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=datetime.now)

    def to_dict(self):
        return {
            "ad_id": self.ad_id,
            "advertiser_name": self.advertiser_name,
            "advertiser_url": self.advertiser_url,
            "social_links": [link.to_dict() for link in self.social_links],
            "scraped_at": self.scraped_at.isoformat(),
        }

    def to_csv_row(self):
        """Convert to flat CSV row with one social link per row."""
        if not self.social_links:
            return [
                {
                    "ad_id": self.ad_id,
                    "advertiser_name": self.advertiser_name,
                    "advertiser_url": self.advertiser_url,
                    "social_platform": "",
                    "social_url": "",
                    "scraped_at": self.scraped_at.isoformat(),
                }
            ]

        rows = []
        for link in self.social_links:
            rows.append(
                {
                    "ad_id": self.ad_id,
                    "advertiser_name": self.advertiser_name,
                    "advertiser_url": self.advertiser_url,
                    "social_platform": link.platform,
                    "social_url": link.url,
                    "scraped_at": self.scraped_at.isoformat(),
                }
            )
        return rows
