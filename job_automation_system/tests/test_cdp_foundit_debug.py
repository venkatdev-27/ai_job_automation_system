"""
Debug FoundIt page - check selectors
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

CDP_URL = "http://localhost:3000"


async def debug_foundit():
    logger.info("=" * 60)
    logger.info("DEBUG FOUNDIT PAGE")
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
        
        logger.info("Opening FoundIt login page...")
        await page.goto("https://www.foundit.in/rio/login", timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        content = await page.content()
        logger.info(f"Content length: {len(content)}")
        
        await page.screenshot(path="foundit_debug.png")
        
        # Check all inputs
        inputs = await page.locator("input").all()
        logger.info(f"Found {len(inputs)} input fields")
        for i, inp in enumerate(inputs[:10]):
            try:
                id_val = await inp.get_attribute("id")
                name_val = await inp.get_attribute("name")
                type_val = await inp.get_attribute("type")
                placeholder = await inp.get_attribute("placeholder")
                class_val = await inp.get_attribute("class")
                logger.info(f"Input {i}: id={id_val}, name={name_val}, type={type_val}, placeholder={placeholder}")
            except:
                pass
        
        # Check forms
        forms = await page.locator("form").all()
        logger.info(f"Found {len(forms)} forms")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_foundit())