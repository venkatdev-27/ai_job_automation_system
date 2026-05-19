"""
Enhanced Platform Login Test - Full stealth testing
"""
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path("/app/job_automation_system")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
os.environ["USE_CDP"] = "true"
os.environ["PLAYWRIGHT_BROWSER"] = "chromium"
os.environ["IN_DOCKER"] = "true"

import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
for noisy in ['pymongo', 'httpx']:
    logging.getLogger(noisy).setLevel(logging.WARNING)

CDP_URL = "http://172.17.0.4:3000"


async def test_naukri_login_full():
    """Test Naukri login flow with full stealth."""
    print("\n" + "=" * 60)
    print("TEST: NAUKRI LOGIN (Full)")
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
    
    print(f"Credentials: {username}")
    
    p = await async_playwright().start()
    
    try:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        print("Connected to CDP")
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            permissions=["geolocation"],
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "max-age=0",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            }
        )
        
        page = await context.new_page()
        
        await page.add_init_script("""() => {
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32', configurable: true });
            window.cdc_adoQpoasnfaofpintcsj = undefined;
            window.$cdc_asdjflasutopfhisd = undefined;
        """)
        
        print("Navigating to Naukri home...")
        await page.goto("https://www.naukri.com/", timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        print(f"Home URL: {page.url}")
        
        print("Navigating to login...")
        await page.goto("https://www.naukri.com/nlogin/login", timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        url = page.url
        title = await page.title()
        
        print(f"URL: {url}")
        print(f"Title: {title[:60]}")
        
        content = await page.content()
        
        if "access denied" in content.lower() or "blocked" in content.lower():
            print("BLOCKED!")
            await page.screenshot(path="/app/naukri_blocked.png")
            return False
        
        print("Login form detected!")
        await page.screenshot(path="/app/naukri_login_form.png")
        
        print("Filling username...")
        username_input = page.locator("input[type='text'], input[type='email']").first
        if await username_input.is_visible():
            await username_input.fill(username)
            print(f"Filled: {username}")
        
        await asyncio.sleep(1)
        
        print("Filling password...")
        pwd_input = page.locator("input[type='password']").first
        if await pwd_input.is_visible():
            await pwd_input.fill(password)
            print("Filled password")
        
        await asyncio.sleep(1)
        await page.screenshot(path="/app/naukri_filled.png")
        
        print("Clicking login...")
        login_btn = page.locator("button[type='submit'], button:has-text('Login'), button:has-text('Sign In')").first
        if await login_btn.is_visible():
            await login_btn.click()
            print("Clicked login")
        else:
            await page.keyboard.press("Enter")
            print("Pressed Enter")
        
        await asyncio.sleep(5)
        
        final_url = page.url
        final_title = await page.title()
        
        print(f"Final URL: {final_url}")
        print(f"Final Title: {final_title[:60]}")
        
        await page.screenshot(path="/app/naukri_after.png")
        
        if "nlogin" not in final_url.lower():
            print("SUCCESS: Logged in!")
            return True
        else:
            print("FAILED: Still on login")
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
    print("=" * 60)
    print("ENHANCED NAUKRI LOGIN TEST")
    print("=" * 60)
    
    success = await test_naukri_login_full()
    
    print("\n" + "=" * 60)
    print(f"RESULT: {'PASS' if success else 'FAIL'}")
    print("=" * 60)
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)