"""
Test LinkedIn login via CDP - simple check
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

LINKEDIN_EMAIL = "k.venky5678@gmail.com"
LINKEDIN_PASSWORD = "Venkyyamuna@1433"

CDP_URL = "http://localhost:3000"


async def test_linkedin_login():
    logger.info("=" * 60)
    logger.info("TESTING LINKEDIN LOGIN VIA CDP")
    logger.info("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        page = await browser.new_page()
        
        logger.info("Opening LinkedIn login page...")
        try:
            response = await page.goto("https://www.linkedin.com/login", timeout=30000, wait_until="domcontentloaded")
            logger.info(f"Response status: {response.status if response else 'None'}")
            await asyncio.sleep(2)
            
            content = await page.content()
            content_len = len(content)
            logger.info(f"Page loaded. Content length: {content_len} bytes")
            
            if content_len < 5000 or "Access Denied" in content or "restricted" in content.lower():
                logger.error(f"BLOCKED - Content length: {content_len}")
                await page.screenshot(path="linkedin_blocked.png")
                await browser.close()
                return False
            
            logger.info("SUCCESS - Page loaded!")
            await page.screenshot(path="linkedin_loaded.png")
            await browser.close()
            return True
            
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            await browser.close()
            return False


if __name__ == "__main__":
    result = asyncio.run(test_linkedin_login())
    if result:
        logger.info("RESULT: PASSED")
    else:
        logger.error("RESULT: FAILED")