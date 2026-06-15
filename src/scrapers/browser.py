"""Shared async Playwright browser helpers."""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)


@asynccontextmanager
async def launch_browser(headless: bool = True, user_data_dir: str | Path | None = None):
    """Yield (browser, context, page) and clean them up on exit."""
    async with async_playwright() as p:
        browser: Browser | None = None
        args = [
            "--disable-blink-features=AutomationControlled",
            "--window-size=960,720",
            "--disable-infobars",
        ]
        context_options = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 960, "height": 720},
            "java_script_enabled": True,
            "bypass_csp": True,
            "locale": "en-US",
            "ignore_https_errors": True,
        }

        if user_data_dir:
            Path(user_data_dir).mkdir(parents=True, exist_ok=True)
            context: BrowserContext = await p.chromium.launch_persistent_context(
                str(user_data_dir),
                headless=headless,
                args=args,
                **context_options,
            )
        else:
            browser = await p.chromium.launch(headless=headless, args=args)
            context = await browser.new_context(**context_options)

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
        await context.add_init_script(stealth_js)
        page: Page = context.pages[0] if context.pages else await context.new_page()
        
        try:
            yield browser, context, page
        finally:
            try:
                await context.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Browser context was already closed: %s", exc)
            if browser is not None:
                try:
                    await browser.close()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Browser was already closed: %s", exc)
