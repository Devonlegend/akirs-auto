"""Ad scraper service."""

import logging
from typing import List, Callable, Optional
from playwright.sync_api import Page, Browser, BrowserContext
from pages import FacebookAdsLibraryPage
from models import AdDetails, SocialLink

logger = logging.getLogger(__name__)


class AdScraperService:
    """Service to scrape ad details and extract social links."""

    def __init__(self, page: Page):
        self.page = page
        self.facebook_ads_page = FacebookAdsLibraryPage(page)
        self.scraped_ads: List[AdDetails] = []

    def setup(self, countries: List[str] = None, keywords: List[str] = None) -> None:
        """Setup the scraper with initial filters."""
        self.facebook_ads_page.navigate()

        if countries:
            for country in countries:
                logger.info(f"Selecting country: {country}")
                try:
                    self.facebook_ads_page.select_country(country)
                except Exception as e:
                    logger.error(f"Error selecting country {country}: {e}")

        if keywords:
            for keyword in keywords:
                logger.info(f"Searching for keyword: {keyword}")
                try:
                    self.facebook_ads_page.search_keyword(keyword)
                except Exception as e:
                    logger.error(f"Error searching keyword {keyword}: {e}")

    def scrape_ad_details(self, ad_index: int = 0) -> Optional[AdDetails]:
        """Scrape details for a specific ad."""
        try:
            logger.info(f"Scraping ad at index {ad_index}")

            # Click "See ad details"
            self.facebook_ads_page.click_see_ad_details(ad_index)

            # Wait for dialog to open
            self.page.wait_for_timeout(500)

            # Extract advertiser info
            advertiser_info = self.facebook_ads_page.get_advertiser_info()

            # Extract social links
            social_links_data = (
                self.facebook_ads_page.extract_social_links_from_dialog()
            )

            # Convert to SocialLink objects
            social_links = [
                SocialLink(platform=link["platform"], url=link["url"])
                for link in social_links_data
            ]

            # Create AdDetails object
            ad_details = AdDetails(
                ad_id=f"ad_{ad_index}",  # You can enhance this with actual ad IDs from page
                advertiser_name=advertiser_info.get("name", "Unknown"),
                advertiser_url=advertiser_info.get("url"),
                social_links=social_links,
            )

            self.scraped_ads.append(ad_details)
            logger.info(
                f"✓ Scraped ad: {ad_details.advertiser_name} with {len(social_links)} social links"
            )

            return ad_details

        except Exception as e:
            logger.error(f"Error scraping ad at index {ad_index}: {e}")
            return None
        finally:
            # Close dialog for next iteration
            self.facebook_ads_page.close_ad_details_dialog()

    def scrape_multiple_ads(self, count: int = 5) -> List[AdDetails]:
        """Scrape multiple ads."""
        for i in range(count):
            logger.info(f"Processing ad {i + 1}/{count}")
            self.scrape_ad_details(i)

        return self.scraped_ads

    def get_scraped_ads(self) -> List[AdDetails]:
        """Get all scraped ads."""
        return self.scraped_ads
