"""
Test FoundIt full login via CDP - with password toggle
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


async def apply_stealth(page):
    await page.add_init_script("""() => {
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true,
            writable: true
        });
    }""")


async def test_foundit_login():
    logger.info("=" * 60)
    logger.info("TESTING FOUNDIT LOGIN VIA CDP")
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
        
        logger.info("Step 1: Opening FoundIt login page...")
        await page.goto("https://www.foundit.in/rio/login", timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        content = await page.content()
        if len(content) < 5000:
            logger.error("Login page blocked")
            return False
        
        # Fill username
        logger.info("Step 2: Filling username...")
        user_field = page.locator("#userName")
        await user_field.fill(FOUNDIT_EMAIL)
        await asyncio.sleep(1)
        
        # Try to toggle to password login if needed
        logger.info("Step 3: Looking for password login toggle...")
        try:
            lp_toggle = page.locator("span:has-text('Login via Password')").first
            if await lp_toggle.is_visible(timeout=3000):
                await lp_toggle.click()
                logger.info("Clicked 'Login via Password' toggle")
                await asyncio.sleep(1.5)
        except:
            logger.info("No toggle, password field should be visible")
        
        # Fill password
        logger.info("Step 4: Filling password...")
        pwd_field = page.locator("#password")
        try:
            await pwd_field.wait_for(state="visible", timeout=5000)
        except:
            logger.error("Password field not visible")
            return False
        
        await pwd_field.fill(FOUNDIT_PASSWORD)
        await asyncio.sleep(0.5)
        
        # Click login
        logger.info("Step 5: Clicking login button...")
        await page.click("button:has-text('Login')")
        await asyncio.sleep(5)
        
        logger.info(f"Current URL: {page.url}")
        
        if "login" not in page.url.lower() and "otp" not in page.url.lower():
            logger.info("SUCCESS - Logged in!")
            return True
        else:
            logger.error("Still on login/OTP page")
            return False


if __name__ == "__main__":
    result = asyncio.run(test_foundit_login())
    if result:
        logger.info("RESULT: PASSED")
    else:
        logger.error("RESULT: FAILED")