"""Configuration and settings."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FacebookAdsConfig:
    """Configuration for Facebook Ads Library scraper."""

    # Base URL for Facebook Ads Library
    base_url: str = (
        "https://www.facebook.com/ads/library/?active_status=active&ad_type=political_and_issue_ads&country=TZ&is_targeted_country=false&media_type=all&sort_data[mode]=total_impressions&sort_data[direction]=desc"
    )

    # Browser settings
    headless: bool = False
    timeout: int = 30000  # milliseconds

    # Search settings
    countries: list = None
    keywords: list = None

    def __post_init__(self):
        if self.countries is None:
            self.countries = ["Nigeria"]
        if self.keywords is None:
            self.keywords = ["Learn"]


@dataclass
class AppConfig:
    """Main application configuration."""

    facebook_ads: FacebookAdsConfig = None
    output_csv_path: str = "output/ads_social_links.csv"

    def __post_init__(self):
        if self.facebook_ads is None:
            self.facebook_ads = FacebookAdsConfig()
