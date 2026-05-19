"""
Test Naukri full login via CDP with stealth
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

NAUKRI_EMAIL = "k.venky5678@gmail.com"
NAUKRI_PASSWORD = "Venkyyamuna@143322"

CDP_URL = "http://localhost:3000"


async def apply_stealth(page):
    await page.add_init_script("""() => {
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true,
            writable: true
        });
        Object.defineProperty(navigator, 'platform', {
            get: () => 'Win32',
            configurable: true
        });
        Object.defineProperty(navigator, 'vendor', {
            get: () => 'Google Inc.',
            configurable: true
        });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
            configurable: true
        });
    }""")


async def test_naukri_login():
    logger.info("=" * 60)
    logger.info("TESTING NAUKRI LOGIN VIA CDP")
    logger.info("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",
            locale="en-US",
            timezone_id="Asia/Kolkata",
            extra_http_headers={
                "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        
        page = await context.new_page()
        await apply_stealth(page)
        
        logger.info("Step 1: Opening Naukri login page...")
        await page.goto("https://www.naukri.com/nlogin/login", timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        # Check if login form loaded
        content = await page.content()
        if len(content) < 10000:
            logger.error("Login page blocked")
            await browser.close()
            return False
        
        logger.info("Step 2: Entering username...")
        await page.fill("#usernameField", NAUKRI_EMAIL)
        await asyncio.sleep(0.5)
        
        logger.info("Step 3: Entering password...")
        await page.fill("#passwordField", NAUKRI_PASSWORD)
        await asyncio.sleep(0.5)
        
        logger.info("Step 4: Clicking login button...")
        await page.click("button[type='submit']")
        await asyncio.sleep(5)
        
        logger.info(f"Current URL: {page.url}")
        
        if "login" not in page.url.lower():
            logger.info("SUCCESS - Logged in!")
            await page.screenshot(path="naukri_login_success.png")
            await browser.close()
            return True
        else:
            logger.error("Still on login page - FAILED")
            await page.screenshot(path="naukri_login_failed.png")
            await browser.close()
            return False


if __name__ == "__main__":
    result = asyncio.run(test_naukri_login())
    if result:
        logger.info("RESULT: PASSED")
    else:
        logger.error("RESULT: FAILED")