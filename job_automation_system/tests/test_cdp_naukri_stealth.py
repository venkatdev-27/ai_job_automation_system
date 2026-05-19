"""
Test Naukri login via CDP with stealth - anti-detection
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

CDP_URL = "http://localhost:3000"


async def apply_stealth(page):
    """Apply anti-detection scripts"""
    await page.add_init_script("""() => {
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true,
            writable: true
        });
        Object.defineProperty(navigator, 'platform', {
            get: () => 'Win32',
            configurable: true
        });
        Object.defineProperty(navigator, 'vendor', {
            get: () => 'Google Inc.',
            configurable: true
        });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
            configurable: true
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
            configurable: true
        });
        if (window.chrome) {
            Object.defineProperty(window.chrome, 'runtime', {
                get: () => ({ installMode: 'normal' }),
                configurable: true
            });
        }
        window.navigator.chrome = window.navigator.chrome || (() => {
            var script = document.createElement('script');
            script.textContent = 'window.chrome = { runtime: { installMode: "normal" } };';
            (document.documentElement || document.head).appendChild(script);
            script.remove();
        })();
        window.cdc_adoQpoasnfa = window.top.document.querySelector;
        window.$cdc_asdflg = window.top.document.querySelector;
    }""")


async def test_naukri_stealth():
    logger.info("=" * 60)
    logger.info("TESTING NAUKRI WITH STEALTH VIA CDP")
    logger.info("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        
        # Create context with custom headers
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",
            locale="en-US",
            timezone_id="Asia/Kolkata",
            permissions=["geolocation"]
        )
        
        page = await context.new_page()
        
        # Apply stealth
        await apply_stealth(page)
        
        # Add route interception to fake headers
        await page.route("**/*", lambda route: route.continue_(
            headers={
                **route.request.headers,
                "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "Accept-Language": "en-US,en;q=0.9"
            }
        ))
        
        logger.info("Opening Naukri login page...")
        try:
            # Navigate directly with proper headers
            await page.goto("https://www.naukri.com/nlogin/login", 
                          timeout=30000, 
                          wait_until="networkidle")
            await asyncio.sleep(3)
            
            content = await page.content()
            content_len = len(content)
            logger.info(f"Content length: {content_len} bytes")
            logger.info(f"URL: {page.url}")
            
            if content_len < 10000:
                logger.error("BLOCKED")
                await page.screenshot(path="naukri_blocked.png")
                return False
            
            logger.info("SUCCESS - Page loaded!")
            await page.screenshot(path="naukri_stealth_ok.png")
            await browser.close()
            return True
            
        except Exception as e:
            logger.error(f"Failed: {e}")
            await browser.close()
            return False


if __name__ == "__main__":
    result = asyncio.run(test_naukri_stealth())
    if result:
        logger.info("RESULT: PASSED")
    else:
        logger.error("RESULT: FAILED")