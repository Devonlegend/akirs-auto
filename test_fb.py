import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating...")
        await page.goto("https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=NG&q=food%20Abak&search_type=keyword_unordered&media_type=all", timeout=60000)
        
        await page.wait_for_timeout(5000)
        
        print("Finding country combobox...")
        try:
            combo = page.get_by_role("combobox")
            count = await combo.count()
            print(f"Combobox count: {count}")
            for i in range(count):
                text = await combo.nth(i).inner_text()
                print(f"Combobox {i}: {text}")
        except Exception as e:
            print(f"Combobox error: {e}")
            
        print("Finding Ad Details buttons...")
        try:
            btns = page.locator("div[role='button']:has-text('See ad details')")
            count = await btns.count()
            print(f"Found {count} See ad details buttons")
            
            if count > 0:
                btn = btns.first
                await btn.click()
                await page.wait_for_timeout(3000)
                
                print("Checking dialogs...")
                dialogs = page.get_by_role("dialog")
                for i in range(await dialogs.count()):
                    name = await dialogs.nth(i).get_attribute("aria-label")
                    print(f"Dialog {i} aria-label: {name}")
                    
                html = await page.content()
                with open("fb_ads_debug.html", "w") as f:
                    f.write(html)
        except Exception as e:
            print(f"Ad details error: {e}")
            
        await browser.close()

asyncio.run(main())
