"""
Platform Login Test - Fixed for Docker with correct CDP URL
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


async def test_cdp_direct_ip():
    """Test CDP with direct IP."""
    print("\n" + "=" * 60)
    print("TEST: CDP CONNECTION (Direct IP)")
    print("=" * 60)
    
    from scraper_adapter.playwright_manager import playwright_manager
    from config.settings import settings
    
    try:
        page, method = await playwright_manager.get_page_with_cdp_fallback(
            settings=settings, 
            student_id="student_test", 
            cdp_url=CDP_URL
        )
        print(f"CDP Success! Method: {method}")
        
        await page.goto("https://www.google.com", timeout=30000)
        print(f"Navigated to: {page.url}")
        
        await page.screenshot(path="/app/test_cdp.png")
        print("Screenshot: /app/test_cdp.png")
        
        await playwright_manager.return_page(page)
        return True
    except Exception as e:
        print(f"CDP Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_login_page():
    """Test navigating to login page."""
    print("\n" + "=" * 60)
    print("TEST: NAUKRI LOGIN PAGE")
    print("=" * 60)
    
    from scraper_adapter.playwright_manager import playwright_manager
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
    
    print(f"Credentials: {username}")
    
    try:
        page, method = await playwright_manager.get_page_with_cdp_fallback(
            settings=settings, 
            student_id=student_id, 
            cdp_url=CDP_URL
        )
        print(f"Page obtained: {method}")
        
        print("Navigating to Naukri...")
        await page.goto("https://www.naukri.com/nlogin/login", timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(5)
        
        print(f"URL: {page.url}")
        print(f"Title: {(await page.title())[:60]}")
        
        await page.screenshot(path="/app/test_naukri_login.png")
        print("Screenshot: /app/test_naukri_login.png")
        
        html = await page.content()
        print(f"HTML length: {len(html)}")
        
        if "username" in html.lower() or "email" in html.lower():
            print("Login form detected!")
        else:
            print("WARNING: Login form not detected")
        
        await playwright_manager.return_page(page)
        return True
    except Exception as e:
        print(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("=" * 60)
    print("LOGIN TEST SUITE")
    print("=" * 60)
    
    results = {}
    
    results['CDP'] = await test_cdp_direct_ip()
    results['Naukri'] = await test_login_page()
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    
    return all(results.values())


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)