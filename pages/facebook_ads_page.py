"""Facebook Ads Library page object."""

from typing import List, Optional
import re
from playwright.sync_api import Page


class FacebookAdsLibraryPage:
    """Page object for interacting with Facebook Ads Library."""

    def __init__(self, page: Page):
        self.page = page
        self.base_url = "https://www.facebook.com/ads/library/?active_status=active&ad_type=political_and_issue_ads&country=TZ&is_targeted_country=false&media_type=all&sort_data[mode]=total_impressions&sort_data[direction]=desc"

    def navigate(self) -> None:
        """Navigate to Facebook Ads Library."""
        self.page.goto(self.base_url)
        self.page.wait_for_load_state("networkidle")

    def select_country(self, country_name: str) -> None:
        """Select a country from the filter dropdown."""
        # Click on country selector
        self.page.locator(
            ".x178xt8z.x1lun4ml.xso031l.xpilrb4.x13fuv20.x18b5jzi.x1q0q8m5.x1t7ytsu.x1x20ilw"
        ).click()

        # Fill in the search textbox
        self.page.get_by_role("textbox", name="Search for country").fill(country_name)

        # Click the matching result
        self.page.get_by_role("radio", name=country_name).check()

        # Confirm selection
        self.page.locator(
            "#js_r > .x1n2onr6 > .x6s0dn4.x78zum5.x13fuv20 > div:nth-child(2) > .x6s0dn4.x3nfvp2 > .x3nfvp2 > .xtwfq29"
        ).click()

    def select_ad_category(self, category: str = "All ads") -> None:
        """Select ad category filter."""
        self.page.get_by_text("Ad category", exact=True).click()
        self.page.get_by_text(category).click()

    def search_keyword(self, keyword: str) -> None:
        """Search for a keyword in the search box."""
        search_box = self.page.get_by_role("searchbox", name="Search by keyword or")
        search_box.click()
        search_box.fill(keyword)
        search_box.press("Enter")
        self.page.wait_for_load_state("networkidle")

    def get_ad_count(self) -> int:
        """Get the number of ads currently displayed."""
        # This would depend on the actual page structure
        # Adjust selector based on your needs
        ad_cards = self.page.locator("[role='button']:has-text('See ad details')")
        return ad_cards.count()

    def get_ads_by_selector(self, selector: str) -> List:
        """Get all ad elements matching a selector."""
        return self.page.locator(selector).all()

    def click_see_ad_details(self, index: int = 0) -> None:
        """Click on 'See ad details' button for a specific ad."""
        buttons = self.page.get_by_role("button", name="See ad details")
        if index < buttons.count():
            buttons.nth(index).click()

    def get_ad_details_dialog(self) -> Optional:
        """Get the ad details dialog if open."""
        try:
            dialog = self.page.get_by_role("dialog", name="Ad details")
            if dialog.is_visible():
                return dialog
        except:
            pass
        return None

    def close_ad_details_dialog(self) -> None:
        """Close the ad details dialog."""
        try:
            dialog = self.page.get_by_role("dialog", name="Ad details")
            dialog.press("Escape")
        except:
            pass

    def extract_social_links_from_dialog(self) -> List[dict]:
        """Extract all social media links from the current ad details dialog."""
        links = []

        try:
            # Look for all links in the dialog
            dialog = self.page.get_by_role("dialog", name="Ad details")
            if not dialog.is_visible():
                return links

            # Find all anchor tags within the dialog
            all_links = dialog.locator("a").all()

            for link_elem in all_links:
                try:
                    href = link_elem.get_attribute("href")
                    text = link_elem.inner_text().strip()

                    if not href or href.startswith("javascript:"):
                        continue

                    # Determine platform from URL or text
                    platform = self._detect_platform(href, text)

                    if platform:
                        links.append({"platform": platform, "url": href, "text": text})
                except:
                    continue
        except:
            pass

        return links

    @staticmethod
    def _detect_platform(url: str, text: str = "") -> Optional[str]:
        """Detect social media platform from URL."""
        url_lower = url.lower()
        text_lower = text.lower()

        platforms = {
            "facebook": ["facebook.com", "fb.me"],
            "instagram": ["instagram.com", "instagr.am"],
            "twitter": ["twitter.com", "x.com", "t.co"],
            "tiktok": ["tiktok.com", "vm.tiktok"],
            "youtube": ["youtube.com", "youtu.be"],
            "linkedin": ["linkedin.com"],
            "whatsapp": ["whatsapp.com", "wa.me"],
            "telegram": ["telegram.me", "t.me"],
            "website": ["http://", "https://"],
        }

        for platform, keywords in platforms.items():
            if any(kw in url_lower for kw in keywords) or any(
                kw in text_lower for kw in keywords
            ):
                return platform

        return None

    def get_advertiser_info(self) -> dict:
        """Extract advertiser information from the ad details dialog."""
        info = {"name": None, "url": None}

        try:
            dialog = self.page.get_by_role("dialog", name="Ad details")

            # Try to find advertiser name and link
            advertiser_link = dialog.locator("a[href*='facebook.com']").first
            if advertiser_link.count() > 0:
                info["name"] = advertiser_link.inner_text().strip()
                info["url"] = advertiser_link.get_attribute("href")
        except:
            pass

        return info
