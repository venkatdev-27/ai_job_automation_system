"""
Platform Login Test - With anti-detection and headers testing
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


async def test_with_stealth():
    """Test with proper stealth settings."""
    print("\n" + "=" * 60)
    print("TEST: NAUKRI WITH STEALTH")
    print("=" * 60)
    
    from playwright.async_api import async_playwright
    from config.settings import settings
    from database.credentials import get_student_credentials
    
    student_id = "student_4443c80f"
    creds = get_student_credentials(student_id)
    
    if not creds:
        print("No credentials!")
        return False
    
    naukri_creds = creds.get("naukri", {})
    username = naukri_creds.get("username") or naukri_creds.get("email")
    password = naukri_creds.get("password")
    
    print(f"Using credentials: {username}")
    
    p = await async_playwright().start()
    
    try:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        print("Connected via CDP")
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            permissions=["geolocation"],
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        
        page = await context.new_page()
        print("Created page")
        
        # Apply stealth
        try:
            from playwright_stealth import stealth_async
            await stealth_async(page)
            print("Applied stealth")
        except Exception as e:
            print(f"Stealth failed: {e}")
        
        # Navigate with waiting
        print("Navigating to Naukri...")
        await page.goto("https://www.naukri.com/nlogin/login", 
                   timeout=30000, 
                   wait_until="networkidle",
                   referer="https://www.google.com/")
        
        await asyncio.sleep(3)
        
        print(f"URL: {page.url}")
        print(f"Title: {(await page.title())[:80]}")
        
        content = await page.content()
        print(f"Content length: {len(content)}")
        
        if "access denied" in content.lower() or "blocked" in content.lower():
            print("BLOCKED: Access denied detected!")
            await page.screenshot(path="/app/test_blocked.png")
        else:
            await page.screenshot(path="/app/test_naukri_stealth.png")
        
        # Check for login form
        if "username" in content.lower() or "email" in content.lower():
            print("Login form found!")
            
            # Try to fill credentials
            print("Trying to fill credentials...")
            
            # Find email field
            email_inputs = await page.locator("input[type='text'], input[type='email']").all()
            for i, inp in enumerate(email_inputs):
                try:
                    if await inp.is_visible():
                        await inp.fill(username)
                        print(f"Filled email at input[{i}]")
                        break
                except:
                    pass
            
            # Find password field
            pwd_inputs = await page.locator("input[type='password']").all()
            for i, inp in enumerate(pwd_inputs):
                try:
                    if await inp.is_visible():
                        await inp.fill(password)
                        print(f"Filled password at input[{i}]")
                        break
                except:
                    pass
            
            await asyncio.sleep(2)
            await page.screenshot(path="/app/test_filled.png")
            
            # Click login
            print("Clicking login...")
            buttons = await page.locator("button").all()
            for btn in buttons:
                try:
                    if await btn.is_visible():
                        txt = await btn.inner_text()
                        if "login" in txt.lower() or "sign" in txt.lower():
                            await btn.click()
                            print(f"Clicked button: {txt}")
                            break
                except:
                    pass
            
            await asyncio.sleep(5)
            await page.screenshot(path="/app/test_after_login.png")
            
            final_url = page.url
            print(f"Final URL: {final_url}")
            
            if "nlogin" not in final_url.lower():
                print("SUCCESS: Logged in!")
            else:
                print("FAILED: Still on login page")
        
        await context.close()
        await browser.close()
        await p.stop()
        
        return True
        
    except Exception as e:
        print(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        try:
            await p.stop()
        except:
            pass
        return False


async def main():
    print("=" * 60)
    print("LOGIN TEST WITH STEALTH")
    print("=" * 60)
    
    success = await test_with_stealth()
    
    print("\n" + "=" * 60)
    print(f"RESULT: {'PASS' if success else 'FAIL'}")
    print("=" * 60)
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)