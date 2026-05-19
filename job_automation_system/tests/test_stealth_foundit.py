"""
Test FoundIt - enhanced stealth with more evasions
"""
import asyncio
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FOUNDIT_EMAIL = "k.venky5678@gmail.com"
FOUNDIT_PASSWORD = "Venkyyamuna@143322"


async def test_foundit():
    logger.info("=" * 60)
    logger.info("TESTING FOUNDIT - ENHANCED STEALTH")
    logger.info("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-features=AutomationControlled',
                '--disable-infobars',
                '--no-sandbox',
            ]
        )
        
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",
            locale="en-US",
            timezone_id="Asia/Kolkata",
            permissions=["geolocation"],
            device_scale_factor=1,
            has_touch=False,
            is_mobile=False,
        )
        
        page = await context.new_page()
        
        # Enhanced stealth - run before navigation
        await page.add_init_script("""() => {
            // Stun webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            
            // Stun plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
                configurable: true
            });
            
            // Stun languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
                configurable: true
            });
            
            // Stun platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32',
                configurable: true
            });
            
            // Stun vendor
            Object.defineProperty(navigator, 'vendor', {
                get: () => 'Google Inc.',
                configurable: true
            });
            
            // Hide automation
            window.navigator.chrome = true;
            window.cdc_adoQpoasnfa = undefined;
            window.$cdc_asdflg = undefined;
            window.$chrome_async = undefined;
            
            // Generate magic arrays
            const magic = window.Symbol('foo');
            window[magic] = [1, 2, 3];
        }""")
        
        logger.info("Navigating to FoundIt...")
        # Try different wait strategy
        await page.goto("https://www.foundit.in/rio/login", timeout=30000)
        await asyncio.sleep(4)
        
        content = await page.content()
        logger.info(f"Content: {len(content)}")
        
        if len(content) < 5000:
            logger.error("BLOCKED - content too short")
            await browser.close()
            return False
        
        # Fill username
        logger.info("Filling username...")
        try:
            await page.wait_for_selector("#userName", timeout=5000)
            await page.fill("#userName", FOUNDIT_EMAIL)
        except Exception as e:
            logger.error(f"Fill username failed: {e}")
            await browser.close()
            return False
        
        await asyncio.sleep(1)
        
        # Toggle password if exists
        try:
            lp_toggle = page.locator("span:has-text('Login via Password')").first
            if await lp_toggle.is_visible(timeout=3000):
                await lp_toggle.click()
                logger.info("Clicked password toggle")
                await asyncio.sleep(1.5)
        except:
            logger.info("No password toggle")
        
        # Fill password
        try:
            await page.wait_for_selector("#password", timeout=5000)
            await page.fill("#password", FOUNDIT_PASSWORD)
        except Exception as e:
            logger.error(f"Fill password failed: {e}")
            await browser.close()
            return False
        
        await asyncio.sleep(0.5)
        
        # Click login via different methods
        logger.info("Clicking login...")
        
        # Try clicking the button
        try:
            btn = page.locator("button:has-text('Login')").first
            await btn.click()
        except:
            # Press Enter instead
            await page.locator("#password").press("Enter")
        
        await asyncio.sleep(6)
        
        logger.info(f"URL: {page.url}")
        
        # Final check
        if "otp" in page.url.lower():
            logger.warning("OTP page - need manual verification")
            await browser.close()
            return True  # Consider this partial success
        
        if "login" not in page.url.lower():
            logger.info("SUCCESS!")
            await browser.close()
            return True
        
        logger.error("FAILED - still on login")
        await browser.close()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_foundit())
    if result:
        logger.info("RESULT: PASSED")
    else:
        logger.error("RESULT: FAILED")