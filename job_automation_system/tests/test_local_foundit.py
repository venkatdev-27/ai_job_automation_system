"""
Test FoundIt with LOCAL browser (non-CDP) - should bypass detection
"""
import asyncio
import logging
from pathlib import Path
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FOUNDIT_EMAIL = "k.venky5678@gmail.com"
FOUNDIT_PASSWORD = "Venkyyamuna@143322"


async def test_foundit_local():
    logger.info("=" * 60)
    logger.info("TESTING FOUNDIT WITH LOCAL BROWSER")
    logger.info("=" * 60)
    
    async with async_playwright() as p:
        # Launch local Chrome (not CDP)
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
            ]
        )
        
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",
            locale="en-US",
            timezone_id="Asia/Kolkata"
        )
        
        page = await context.new_page()
        
        # Add stealth
        await page.add_init_script("""() => {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true,
                writable: true
            });
        }""")
        
        await page.goto("https://www.foundit.in/rio/login", timeout=30000, wait_until="networkidle")
        await asyncio.sleep(2)
        
        # Fill username
        await page.fill("#userName", FOUNDIT_EMAIL)
        await asyncio.sleep(0.5)
        
        # Click toggle if exists
        try:
            lp_toggle = page.locator("span:has-text('Login via Password')").first
            if await lp_toggle.is_visible(timeout=2000):
                await lp_toggle.click()
                await asyncio.sleep(1)
        except:
            pass
        
        # Fill password
        await page.fill("#password", FOUNDIT_PASSWORD)
        await asyncio.sleep(0.5)
        
        # Press Enter
        await page.locator("#password").press("Enter")
        await asyncio.sleep(5)
        
        logger.info(f"URL after login: {page.url}")
        
        if "login" not in page.url.lower() and "otp" not in page.url.lower():
            logger.info("SUCCESS!")
            await browser.close()
            return True
        
        logger.info("FAILED")
        await browser.close()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_foundit_local())
    if result:
        logger.info("RESULT: PASSED")
    else:
        logger.error("RESULT: FAILED")