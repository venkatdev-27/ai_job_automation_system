"""
Test FoundIt with enhanced CDP stealth
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

from scraper_adapter.playwright_manager import PlaywrightManager

FOUNDIT_EMAIL = "k.venky5678@gmail.com"
FOUNDIT_PASSWORD = "Venkyyamuna@143322"


async def test_foundit_enhanced():
    logger.info("=" * 60)
    logger.info("TESTING FOUNDIT WITH ENHANCED CDP STEALTH")
    logger.info("=" * 60)
    
    # Use the playwright_manager directly
    pm = PlaywrightManager()
    
    try:
        page = await pm.get_page_via_cdp(
            cdp_url="http://localhost:3000"
        )
        logger.info("Got CDP page")
        
        # Navigate to FoundIt
        await page.goto("https://www.foundit.in/rio/login", timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        content = await page.content()
        logger.info(f"Content length: {len(content)}")
        
        if len(content) < 5000:
            logger.error("BLOCKED")
            return False
        
        logger.info("Page loaded - trying login...")
        
        # Fill username
        await page.fill("#userName", FOUNDIT_EMAIL)
        await asyncio.sleep(0.5)
        
        # Toggle password if exists
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
        
        # Click login
        await page.locator("#password").press("Enter")
        await asyncio.sleep(5)
        
        logger.info(f"URL: {page.url}")
        
        if "login" not in page.url.lower():
            logger.info("SUCCESS!")
            return True
        
        logger.info("FAILED")
        return False
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_foundit_enhanced())
    if result:
        logger.info("RESULT: PASSED")
    else:
        logger.error("RESULT: FAILED")