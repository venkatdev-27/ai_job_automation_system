import asyncio
import os
from playwright.async_api import async_playwright

async def test_launch():
    print("Starting Playwright...")
    async with async_playwright() as p:
        print("Launching browser (headless=True, --no-sandbox)...")
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            print("Successfully launched browser!")
            
            page = await browser.new_page()
            print("Navigating to Google...")
            await page.goto("https://www.google.com", timeout=30000)
            print(f"Page title: {await page.title()}")
            
            await browser.close()
            print("Browser closed.")
        except Exception as e:
            print(f"Launch failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_launch())
