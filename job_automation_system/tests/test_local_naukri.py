"""
Test Naukri with LOCAL browser - should bypass detection
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


async def test_naukri_local():
    logger.info("=" * 60)
    logger.info("TESTING NAUKRI WITH LOCAL BROWSER")
    logger.info("=" * 60)
    
    async with async_playwright() as p:
        # Launch local Chrome with stealth args
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--ignore-certificate-errors',
                '--ignore-ssl-errors',
            ]
        )
        
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",
            locale="en-US",
        )
        
        page = await context.new_page()
        
        # Add stealth
        await page.add_init_script("""() => {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true,
                writable: true
            });
            window.navigator.chrome = true;
        }""")
        
        logger.info("Opening Naukri login...")
        await page.goto("https://www.naukri.com/nlogin/login", timeout=30000, wait_until="networkidle")
        await asyncio.sleep(2)
        
        content = await page.content()
        logger.info(f"Content: {len(content)}")
        
        if len(content) < 10000:
            logger.error("BLOCKED by Naukri")
            await browser.close()
            return False
        
        logger.info("Filling username...")
        await page.fill("#usernameField", NAUKRI_EMAIL)
        await asyncio.sleep(0.5)
        
        logger.info("Filling password...")
        await page.fill("#passwordField", NAUKRI_PASSWORD)
        await asyncio.sleep(0.5)
        
        logger.info("Clicking login...")
        await page.click("button[type='submit']")
        await asyncio.sleep(5)
        
        logger.info(f"URL: {page.url}")
        
        if "login" not in page.url.lower():
            logger.info("SUCCESS!")
            await browser.close()
            return True
        
        logger.info("FAILED")
        await browser.close()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_naukri_local())
    if result:
        logger.info("RESULT: PASSED")
    else:
        logger.error("RESULT: FAILED")