"""Shared async Playwright browser helpers."""

from contextlib import asynccontextmanager
from playwright.async_api import Browser, BrowserContext, Page, async_playwright


@asynccontextmanager
async def launch_browser(headless: bool = True):
    """Yield (browser, context, page) and clean them up on exit."""
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-size=1280,800",
                "--disable-infobars"
            ]
        )
        context: BrowserContext = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            java_script_enabled=True,
            bypass_csp=True,
            locale="en-US"
        )
        page: Page = await context.new_page()
        
        # Comprehensive Stealth Injection
        stealth_js = """
        // 1. Pass webdriver
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        
        // 2. Pass chrome
        window.chrome = { runtime: {} };
        
        // 3. Pass permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
        );
        
        // 4. Pass plugins
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        
        // 5. Pass languages
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """
        await page.add_init_script(stealth_js)
        
        try:
            yield browser, context, page
        finally:
            await context.close()
            await browser.close()
