import asyncio
from src.scrapers.browser import launch_browser

async def main():
    async with launch_browser(headless=True) as (browser, ctx, page):
        response = await page.goto("http://www.unacofoodexport.com/", wait_until="domcontentloaded")
        print("Status:", response.status)
        print("Title:", await page.title())

asyncio.run(main())
