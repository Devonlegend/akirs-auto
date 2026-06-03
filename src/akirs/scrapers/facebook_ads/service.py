"""FacebookAdsScraper service — drives the page object end-to-end."""

import logging
from typing import Any

from playwright.async_api import Page

from akirs.scrapers.base import AbstractScraper
from akirs.scrapers.facebook_ads.page import FacebookAdsLibraryPage

logger = logging.getLogger(__name__)


class FacebookAdsScraper(AbstractScraper):
    def __init__(self, page: Page):
        self.page = page
        self.facebook_page = FacebookAdsLibraryPage(page)

    async def setup(
        self,
        country: str | None = None,
        keyword: str | None = None,
        ad_category: str = "All ads",
        **_: Any,
    ) -> None:
        await self.facebook_page.navigate()
        if country:
            await self.facebook_page.select_country(country)
        await self.facebook_page.select_ad_category(ad_category)
        if keyword:
            await self.facebook_page.search_keyword(keyword)

    async def scrape(self, target_count: int) -> list[dict]:
        """Iterate ads, open each dialog, extract, close. Return list of raw ad dicts."""
        results: list[dict] = []
        async for card in self.facebook_page.iter_ad_cards(target_count):
            try:
                await card.open_dialog()
                data = await card.extract()
                if data.get("advertiser_url"):
                    results.append(data)
                else:
                    logger.debug("Skipping card with no advertiser_url")
            except Exception as e:
                logger.warning(f"Error extracting ad #{card.index}: {e}")
            finally:
                await card.close_dialog()

        logger.info(f"FacebookAdsScraper: extracted {len(results)} ads")
        return results
