"""
Test LinkedIn full login via CDP - check selectors first
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
        
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",
            locale="en-US",
            timezone_id="Asia/Kolkata"
        )
        
        page = await context.new_page()
        
        logger.info("Opening LinkedIn login page...")
        await page.goto("https://www.linkedin.com/login", timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        # Debug - show page content
        content = await page.content()
        logger.info(f"Content length: {len(content)}")
        await page.screenshot(path="linkedin_debug.png")
        
        # Try to find any input field
        inputs = await page.locator("input").all()
        logger.info(f"Found {len(inputs)} input fields")
        for i, inp in enumerate(inputs[:5]):
            try:
                id_val = await inp.get_attribute("id")
                name_val = await inp.get_attribute("name")
                type_val = await inp.get_attribute("type")
                placeholder = await inp.get_attribute("placeholder")
                logger.info(f"Input {i}: id={id_val}, name={name_val}, type={type_val}, placeholder={placeholder}")
            except:
                pass
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_linkedin_login())