"""
Test LinkedIn full login via CDP - wait for form
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
        await page.goto("https://www.linkedin.com/login", timeout=30000)
        await asyncio.sleep(3)
        
        # Wait for the username field to appear
        try:
            await page.wait_for_selector("input#username", timeout=10000)
        except:
            logger.warning("Username field not found with #username, trying other selectors")
        
        # Try multiple selectors
        selectors = ["input#username", "input[name='session_key']", "input[type='email']", "input[autocomplete='username']"]
        username_field = None
        for sel in selectors:
            if await page.locator(sel).count() > 0:
                username_field = page.locator(sel).first
                logger.info(f"Found username field with: {sel}")
                break
        
        if not username_field:
            logger.error("Username field not found")
            await page.screenshot(path="linkedin_no_field.png")
            await browser.close()
            return False
        
        await username_field.fill(LINKEDIN_EMAIL)
        await asyncio.sleep(0.5)
        
        # Find password field
        pwd_selectors = ["input#password", "input[name='session_password']", "input[type='password']"]
        password_field = None
        for sel in pwd_selectors:
            if await page.locator(sel).count() > 0:
                password_field = page.locator(sel).first
                logger.info(f"Found password field with: {sel}")
                break
        
        if password_field:
            await password_field.fill(LINKEDIN_PASSWORD)
            await asyncio.sleep(0.5)
            
            # Click submit
            await page.click("button[type='submit']")
            await asyncio.sleep(5)
            
            logger.info(f"Current URL: {page.url}")
            
            if "login" not in page.url.lower():
                logger.info("SUCCESS - Logged in!")
                await page.screenshot(path="linkedin_login_success.png")
                await browser.close()
                return True
        
        logger.error("FAILED")
        await page.screenshot(path="linkedin_login_failed.png")
        await browser.close()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_linkedin_login())
    if result:
        logger.info("RESULT: PASSED")
    else:
        logger.error("RESULT: FAILED")