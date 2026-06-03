"""Shared async Playwright browser helpers."""

from contextlib import asynccontextmanager
from playwright.async_api import Browser, BrowserContext, Page, async_playwright


@asynccontextmanager
async def launch_browser(headless: bool = True):
    """Yield (browser, context, page) and clean them up on exit."""
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=headless)
        context: BrowserContext = await browser.new_context()
        page: Page = await context.new_page()
        try:
            yield browser, context, page
        finally:
            await context.close()
            await browser.close()
