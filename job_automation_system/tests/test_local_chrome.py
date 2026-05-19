"""
Direct Playwright Test - Without CDP, using local Chrome
"""
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path("/app/job_automation_system")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
os.environ["USE_CDP"] = "false"
os.environ["PLAYWRIGHT_BROWSER"] = "chromium"
os.environ["IN_DOCKER"] = "true"

import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
for noisy in ['pymongo', 'httpx']:
    logging.getLogger(noisy).setLevel(logging.WARNING)


async def test_local_chrome():
    """Test with local Chrome (not CDP)."""
    print("\n" + "=" * 60)
    print("TEST: LOCAL CHROME (Not CDP)")
    print("=" * 60)
    
    from playwright.async_api import async_playwright
    from database.credentials import get_student_credentials
    
    student_id = "student_4443c80f"
    creds = get_student_credentials(student_id)
    
    if not creds:
        print("No credentials!")
        return False
    
    naukri_creds = creds.get("naukri", {})
    username = naukri_creds.get("username") or naukri_creds.get("email")
    password = naukri_creds.get("password")
    
    print(f"Username: {username}")
    
    p = await async_playwright().start()
    
    try:
        # Launch local Chrome
        browser = await p.chromium.launch(
            headless=False,  # Not headless to test
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        print("Launched local Chrome")
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-IN",
        )
        
        page = await context.new_page()
        
        # Add stealth
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.cdc_adoQpoasnfaofpintcsj = undefined;
        """)
        
        print("Navigating to Naukri...")
        await page.goto("https://www.naukri.com/nlogin/login", timeout=60000)
        await asyncio.sleep(5)
        
        print(f"URL: {page.url}")
        print(f"Title: {(await page.title())[:60]}")
        
        content = await page.content()
        print(f"Content length: {len(content)}")
        
        if len(content) > 1000:
            print("LOGIN PAGE LOADED!")
            await page.screenshot(path="/app/local_login.png")
            return True
        else:
            print("PAGE BLOCKED")
            await page.screenshot(path="/app/local_blocked.png")
            return False
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            await p.stop()
        except:
            pass


async def main():
    success = await test_local_chrome()
    print(f"\nRESULT: {'PASS' if success else 'FAIL'}")
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)