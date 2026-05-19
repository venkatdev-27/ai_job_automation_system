"""
Debug FoundIt - check page flow
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
    logger.info("DEBUG FOUNDIT")
    logger.info("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",
        )
        
        page = await context.new_page()
        
        await page.goto("https://www.foundit.in/rio/login", timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        # Get the full HTML
        content = await page.content()
        logger.info(f"Content: {len(content)} chars")
        
        # Check buttons
        btns = await page.locator("button").all()
        logger.info(f"Buttons: {len(btns)}")
        for i, btn in enumerate(btns):
            try:
                txt = await btn.text_content()
                cls = await btn.get_attribute("class")
                logger.info(f"Button {i}: text={txt}, class={cls}")
            except:
                pass
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_foundit())