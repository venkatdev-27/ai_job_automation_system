"""
Test FoundIt - check OTP requirement
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

CDP_URL = "http://localhost:3000"


async def test_foundit():
    logger.info("=" * 60)
    logger.info("TESTING FOUNDIT")
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
        
        # Fill username
        await page.fill("#userName", FOUNDIT_EMAIL)
        await asyncio.sleep(1)
        
        # Look for password toggle
        try:
            lp_toggle = page.locator("span:has-text('Login via Password')").first
            if await lp_toggle.is_visible(timeout=3000):
                await lp_toggle.click()
                logger.info("Clicked toggle")
                await asyncio.sleep(1.5)
        except:
            pass
        
        # Fill password
        pwd_field = page.locator("#password")
        await pwd_field.wait_for(state="visible", timeout=5000)
        await pwd_field.fill(FOUNDIT_PASSWORD)
        
        # Click login
        await page.click("button:has-text('Login')")
        await asyncio.sleep(3)
        
        # Check page content for OTP
        content = await page.content()
        logger.info(f"URL: {page.url}")
        
        # Look for OTP field
        otp_fields = await page.locator("input[type='text']").all()
        logger.info(f"Text inputs: {len(otp_fields)}")
        
        # Look for any inputs
        all_inputs = await page.locator("input").all()
        logger.info(f"Total inputs: {len(all_inputs)}")
        for i, inp in enumerate(all_inputs[:5]):
            try:
                id_val = await inp.get_attribute("id")
                type_val = await inp.get_attribute("type")
                placeholder = await inp.get_attribute("placeholder")
                logger.info(f"Input {i}: id={id_val}, type={type_val}, placeholder={placeholder}")
            except:
                pass
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_foundit())