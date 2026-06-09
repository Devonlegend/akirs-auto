"""Facebook Ads Library page object with pagination."""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import parse_qs, urlparse

from playwright.async_api import Locator, Page

from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class AdCard:
    """A single ad result row. Provides open_dialog/close_dialog/extract."""

    page: Page
    index: int
    button: Locator
    fingerprint: str = ""

    async def open_dialog(self) -> None:
        await self.button.scroll_into_view_if_needed()
        await self.button.click()
        try:
            await self.page.wait_for_selector("div[role='dialog']", timeout=5000)
            await self.page.wait_for_timeout(500)
        except Exception as e:
            logger.warning(f"Dialog wait failed for ad {self.index}: {e}")

    async def close_dialog(self) -> None:
        try:
            dialog = self.page.locator("div[role='dialog']").first
            if await dialog.is_visible():
                await dialog.press("Escape")
                await self.page.wait_for_timeout(300)
                if await dialog.is_visible():
                    # Fallback click outside or close button
                    close_btn = dialog.get_by_role("button").first
                    if await close_btn.count() > 0:
                        await close_btn.click()
        except Exception:
            pass

    async def extract(self) -> dict:
        """Return advertiser info + social links from the open dialog."""
        info = await _get_advertiser_info(self.page)
        links = await _extract_social_links_from_dialog(self.page)
        return {
            "advertiser_name": info.get("name"),
            "advertiser_url": info.get("url"),
            "fb_ad_id": info.get("fb_ad_id"),
            "social_links": links,
            "fingerprint": self.fingerprint,
        }


class FacebookAdsLibraryPage:
    """Page object for Facebook Ads Library with pagination support."""

    AD_DETAILS_BUTTON_SELECTOR = "div[role='button']:has-text('See ad details')"

    def __init__(self, page: Page):
        self.page = page
        self.settings = get_settings()

    async def navigate(self) -> None:
        for attempt in range(4):
            await self.page.goto(self.settings.fb_ads_base_url)
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(2000)
            
            error_msg = self.page.locator("text=/something went wrong/i").first
            if await error_msg.count() > 0:
                logger.warning(f"Encountered 'Something went wrong' on load. Hard navigating (attempt {attempt + 1}/4)...")
                await self.page.wait_for_timeout(3000)
                await self.page.goto(self.settings.fb_ads_base_url)
                await self.page.wait_for_load_state("networkidle")
            else:
                break

    async def select_country(self, country_name: str) -> None:
        try:
            await self.page.wait_for_timeout(900)
            country_combo = self.page.locator("div[role='button'], div[role='combobox']").filter(has_text=re.compile(f"country|{country_name}", re.I)).first
            
            if await country_combo.count() > 0:
                current_text = await country_combo.inner_text()
                if country_name.lower() in current_text.lower():
                    logger.info(f"Country is already set to {current_text.strip()}")
                    return
                await country_combo.click(timeout=5000)
                await self.page.wait_for_timeout(400)

                search_box = self.page.get_by_role("textbox", name=re.compile("country", re.I)).first
                if await search_box.count() == 0:
                    search_box = self.page.locator("input[placeholder*='earch']").first
                await search_box.click()
                await search_box.press("Control+A")
                await search_box.press("Backspace")
                await search_box.press_sequentially(country_name, delay=100)
                await self.page.wait_for_timeout(400)

                await self.page.get_by_role("radio", name=country_name).check()
                await self.page.wait_for_timeout(300)

                done_btn = self.page.get_by_role("button", name=re.compile("done", re.I)).first
                if await done_btn.count() > 0:
                    await done_btn.click()
        except Exception as e:
            logger.warning(f"select_country({country_name}) failed (continuing): {e}")

    async def select_ad_category(self, category: str = "All ads") -> None:
        try:
            dropdown = self.page.locator('div[role="combobox"], div[role="button"]').filter(has_text=re.compile("Ad category", re.I)).first
            if await dropdown.count() > 0:
                await dropdown.click()
            else:
                await self.page.get_by_text("Ad category").first.click()
            await self.page.wait_for_timeout(400)
            
            option = self.page.get_by_role("option", name=category).first
            if await option.count() == 0:
                option = self.page.locator(f'div[role="button"], span').filter(has_text=re.compile(category, re.I)).first
            await option.click()
            await self.page.wait_for_timeout(400)
        except Exception as e:
            logger.warning(f"select_ad_category({category}) failed (continuing): {e}")

    async def search_keyword(self, keyword: str) -> None:
        for attempt in range(3):
            try:
                search_box = self.page.get_by_placeholder(re.compile("search|keyword", re.I)).first
                if await search_box.count() == 0:
                     search_box = self.page.locator("input[type='text']").last
                
                await search_box.click()
                await self.page.wait_for_timeout(300)
                await search_box.press("Control+A")
                await search_box.press("Backspace")
                await self.page.wait_for_timeout(200)
                
                # Human typing simulation
                await search_box.press_sequentially(keyword, delay=120)
                await self.page.wait_for_timeout(500)
                await search_box.press("Enter")
                
                await self.page.wait_for_load_state("networkidle", timeout=15000)
                await self.page.wait_for_timeout(3000)
                
                # Check if it errored out after searching
                error_msg = self.page.locator("text=/something went wrong/i").first
                if await error_msg.count() > 0:
                    logger.warning(f"Search errored for '{keyword}'. Hard resetting page (attempt {attempt+1}/3)...")
                    await self.navigate()
                    await self.select_country(self.settings.fb_ads_country)
                    await self.select_ad_category("All ads")
                    continue
                else:
                    break
            except Exception as e:
                logger.warning(f"search_keyword({keyword}) failed: {e}")
                break

    def _get_ad_buttons(self) -> Locator:
        return self.page.locator("div[role='button'], a, button").filter(has_text=re.compile(r"ad details", re.I))

    async def visible_ad_count(self) -> int:
        return await self._get_ad_buttons().count()

    async def _scroll_to_load_more(self) -> bool:
        """Scroll once. Return True if document height changed (i.e. content loaded)."""
        prev_height = await self.page.evaluate("document.body.scrollHeight")
        await self.page.evaluate("window.scrollBy(0, window.innerHeight * 0.9)")
        await self.page.wait_for_timeout(self.settings.fb_ads_scroll_delay_ms)
        new_height = await self.page.evaluate("document.body.scrollHeight")
        return new_height > prev_height

    async def iter_ad_cards(self, target_count: int) -> AsyncIterator[AdCard]:
        """Yield AdCard objects up to target_count, scrolling as needed.

        Stops on: target reached, N consecutive scrolls without new ads, or max scrolls.
        """
        empty_threshold = self.settings.fb_ads_empty_scroll_threshold
        max_scrolls = self.settings.fb_ads_max_scrolls

        yielded = 0
        empty_scrolls = 0
        scroll_count = 0
        seen_fingerprints: set[str] = set()
        
        # Debug dump if no ads found on initial load
        if await self.visible_ad_count() == 0:
            logger.warning("0 ad details buttons found on initial load, dumping debug info...")
            try:
                await self.page.screenshot(path="output/debug_fb.png", full_page=True)
                with open("output/debug_fb.html", "w") as f:
                    f.write(await self.page.content())
            except Exception as e:
                logger.error(f"Failed to dump debug files: {e}")

        while yielded < target_count and scroll_count <= max_scrolls:
            buttons = self._get_ad_buttons()
            count = await buttons.count()
            new_in_pass = 0
            for i in range(count):
                if yielded >= target_count:
                    break
                btn = buttons.nth(i)
                fp = await _fingerprint_card(btn, i)
                if fp in seen_fingerprints:
                    continue
                seen_fingerprints.add(fp)
                new_in_pass += 1
                yielded += 1
                yield AdCard(page=self.page, index=i, button=btn, fingerprint=fp)

            if yielded >= target_count:
                break

            grew = await self._scroll_to_load_more()
            scroll_count += 1
            if not grew and new_in_pass == 0:
                empty_scrolls += 1
                if empty_scrolls >= empty_threshold:
                    logger.info(f"iter_ad_cards: stopping after {empty_scrolls} empty scrolls")
                    break
            else:
                empty_scrolls = 0


async def _fingerprint_card(button: Locator, index: int) -> str:
    """Best-effort stable fingerprint based on nearest advertiser link href."""
    try:
        card = button.locator("xpath=ancestor::div[contains(@role,'article') or contains(@class,'_7jvw')][1]")
        href = await card.locator("a[href*='facebook.com']").first.get_attribute("href", timeout=500)
        if href:
            return href
    except Exception:
        pass
    return f"pos-{index}"


async def _get_advertiser_info(page: Page) -> dict:
    info: dict = {"name": None, "url": None, "fb_ad_id": None}
    try:
        dialog = page.locator("div[role='dialog']").first
        if await dialog.count() == 0:
            return info

        advertiser_link = dialog.locator("a[href*='facebook.com'], a[href*='instagram.com']").first
        if await advertiser_link.count() > 0:
            info["name"] = (await advertiser_link.inner_text()).strip() or None
            info["url"] = await advertiser_link.get_attribute("href")

        dialog_text = await dialog.inner_text()
        m = re.search(r"Library ID[:\s]+(\d+)", dialog_text)
        if m:
            info["fb_ad_id"] = m.group(1)
    except Exception as e:
        logger.warning(f"_get_advertiser_info error: {e}")
    return info


async def _extract_social_links_from_dialog(page: Page) -> list[dict]:
    links: list[dict] = []
    try:
        dialog = page.locator("div[role='dialog']").first
        if await dialog.count() == 0:
            return links

        anchors = await dialog.locator("a").all()
        for a in anchors:
            try:
                href = await a.get_attribute("href")
                if not href or href.startswith("javascript:") or href.startswith("/"):
                    continue
                
                # Unwrap facebook redirect links
                if "l.facebook.com/l.php" in href:
                    qs = parse_qs(urlparse(href).query)
                    if "u" in qs:
                        href = qs["u"][0]

                text = (await a.inner_text()).strip()
                platform = _detect_platform(href, text)
                if platform:
                    links.append({"platform": platform, "url": href, "text": text})
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"_extract_social_links error: {e}")
    return _dedupe_links(links)


def _detect_platform(url: str, text: str = "") -> Optional[str]:
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
    }
    for platform, kws in platforms.items():
        if any(kw in url_lower for kw in kws) or any(kw in text_lower for kw in kws):
            return platform
    if url_lower.startswith("http://") or url_lower.startswith("https://"):
        return "website"
    return None


def _dedupe_links(links: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for link in links:
        key = link["url"]
        if key in seen:
            continue
        seen.add(key)
        out.append(link)
    return out
