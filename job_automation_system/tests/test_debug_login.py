"""
Enhanced Platform Login Test - Debug version with screenshot
"""
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path("/app/job_automation_system")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["MONGO_URI"] = "mongodb+srv://kosurivenky:venkyyamuna@cluster0.uhbfag1.mongodb.net/ai_bot_resumes?appName=Cluster0"
os.environ["USE_CDP"] = "true"
os.environ["PLAYWRIGHT_BROWSER"] = "chromium"
os.environ["IN_DOCKER"] = "true"

import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
for noisy in ['pymongo', 'httpx']:
    logging.getLogger(noisy).setLevel(logging.WARNING)

CDP_URL = "http://172.17.0.4:3000"


async def test_debug():
    """Debug what's on the login page."""
    print("\n" + "=" * 60)
    print("DEBUG: NAUKRI LOGIN PAGE")
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
    print(f"Password: {'*' * len(password)}")
    
    p = await async_playwright().start()
    
    try:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-IN",
        )
        
        page = await context.new_page()
        
        print("Navigating to login...")
        await page.goto("https://www.naukri.com/nlogin/login", 
                     timeout=30000, 
                     wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        print(f"URL: {page.url}")
        
        # Take screenshot before anything
        await page.screenshot(path="/app/debug_01_login.png")
        
        # Get ALL inputs
        print("\nAll inputs on page:")
        inputs = await page.locator("input").all()
        for i, inp in enumerate(inputs):
            try:
                t = await inp.get_attribute("type") or "text"
                n = await inp.get_attribute("name") or ""
                i_id = await inp.get_attribute("id") or ""
                ph = await inp.get_attribute("placeholder") or ""
                vis = await inp.is_visible()
                print(f"  [{i}] type={t}, name={n}, id={i_id}, placeholder={ph}, visible={vis}")
            except:
                print(f"  [{i}] ERROR getting info")
        
        # Try to find username field by ID
        user_field = page.locator("#usernameField")
        if await user_field.count() > 0:
            print(f"\nFound #usernameField")
            if await user_field.is_visible():
                await user_field.fill(username)
                print("Filled username via #usernameField")
                await page.screenshot(path="/app/debug_02_user_filled.png")
        
        # Try password field by ID
        pwd_field = page.locator("#passwordField")
        if await pwd_field.count() > 0:
            print(f"Found #passwordField")
            if await pwd_field.is_visible():
                await pwd_field.fill(password)
                print("Filled password via #passwordField")
                await page.screenshot(path="/app/debug_03_pwd_filled.png")
        
        # Try clicking the login button
        login_btn = page.locator("button.loginButton")
        if await login_btn.count() > 0:
            print(f"Found button.loginButton")
            if await login_btn.is_visible():
                await login_btn.click()
                print("Clicked login button")
                await asyncio.sleep(3)
                await page.screenshot(path="/app/debug_04_after_click.png")
        
        print(f"\nFinal URL: {page.url}")
        
        if "nlogin" not in page.url.lower():
            print("SUCCESS: Logged in!")
            return True
        else:
            print("NOT LOGGED IN")
            # Get HTML for debugging
            html = await page.content()
            print(f"HTML length: {len(html)}")
            print(f"HTML snippet: {html[500:1000]}")
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
    success = await test_debug()
    print(f"\nRESULT: {'PASS' if success else 'FAIL'}")
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)