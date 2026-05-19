"""
Platform Login Test Suite - Tests CDP connection and login for all 3 platforms.
Run inside Docker container to test actual celery worker environment.
"""
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path("/app/job_automation_system")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
os.environ["CDP_URL"] = "http://chrome-cdp:3000"
os.environ["USE_CDP"] = "true"
os.environ["PLAYWRIGHT_BROWSER"] = "chromium"
os.environ["IN_DOCKER"] = "true"

import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
for noisy in ['pymongo', 'dns', 'urllib3', 'httpx']:
    logging.getLogger(noisy).setLevel(logging.WARNING)


async def test_cdp_connection():
    """Test CDP connection to chrome-cdp container."""
    print("\n" + "=" * 60)
    print("TEST 1: CDP CONNECTION")
    print("=" * 60)
    
    from scraper_adapter.playwright_manager import playwright_manager
    from config.settings import settings
    
    try:
        page, method = await playwright_manager.get_page_with_cdp_fallback(
            settings=settings, 
            student_id="student_test_cdp", 
            cdp_url="http://chrome-cdp:3000"
        )
        print(f"CDP Connection: SUCCESS")
        print(f"  Method used: {method}")
        print(f"  Page URL: {page.url}")
        
        await page.goto("https://www.google.com", timeout=30000)
        await asyncio.sleep(2)
        print(f"  Navigated to: {page.url}")
        title = await page.title()
        print(f"  Page title: {title[:50]}")
        
        await page.screenshot(path="/app/test_cdp_google.png")
        print(f"  Screenshot: /app/test_cdp_google.png")
        
        await playwright_manager.return_page(page)
        return True
    except Exception as e:
        print(f"CDP Connection FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_naukri_login():
    """Test Naukri login via CDP."""
    print("\n" + "=" * 60)
    print("TEST 2: NAUKRI LOGIN")
    print("=" * 60)
    
    from scraper_adapter.playwright_manager import playwright_manager
    from scraper_adapter.naukri import NaukriScraper
    from config.settings import settings
    from database.credentials import get_student_credentials
    
    student_id = "student_4443c80f"
    creds = get_student_credentials(student_id)
    
    if not creds:
        print(f"No credentials found for {student_id}")
        return False
        
    naukri_creds = creds.get("naukri", {})
    username = naukri_creds.get("username") or naukri_creds.get("email")
    password = naukri_creds.get("password")
    
    print(f"Using credentials: {username}")
    
    try:
        page, method = await playwright_manager.get_page_with_cdp_fallback(
            settings=settings, 
            student_id=student_id, 
            cdp_url="http://chrome-cdp:3000"
        )
        print(f"CDP Page: SUCCESS (method: {method})")
        
        scraper = NaukriScraper(settings, student_id)
        scraper.logger = type('obj', (object,), {'log_info': print, 'log_err': print, 'log_warn': print, 'log_ok': print})()
        
        print("Attempting Naukri login...")
        login_result = await scraper._login(page, student_id, settings)
        
        print(f"Login result: {login_result}")
        
        await asyncio.sleep(3)
        final_url = page.url
        print(f"Final URL: {final_url}")
        
        if "nlogin" not in final_url.lower():
            print("SUCCESS: Logged into Naukri!")
            await page.screenshot(path="/app/test_naukri_success.png")
        else:
            print("FAILED: Still on login page")
            await page.screenshot(path="/app/test_naukri_failed.png")
        
        await playwright_manager.return_page(page)
        return "nlogin" not in final_url.lower()
        
    except Exception as e:
        print(f"Naukri login FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_linkedin_login():
    """Test LinkedIn login via CDP."""
    print("\n" + "=" * 60)
    print("TEST 3: LINKEDIN LOGIN")
    print("=" * 60)
    
    from scraper_adapter.playwright_manager import playwright_manager
    from scraper_adapter.linkedin import LinkedInScraper
    from config.settings import settings
    from database.credentials import get_student_credentials
    
    student_id = "student_4443c80f"
    creds = get_student_credentials(student_id)
    
    if not creds:
        print(f"No credentials found for {student_id}")
        return False
        
    linkedin_creds = creds.get("linkedin", {})
    username = linkedin_creds.get("username") or linkedin_creds.get("email")
    password = linkedin_creds.get("password")
    
    print(f"Using credentials: {username}")
    
    try:
        page, method = await playwright_manager.get_page_with_cdp_fallback(
            settings=settings, 
            student_id=student_id, 
            cdp_url="http://chrome-cdp:3000"
        )
        print(f"CDP Page: SUCCESS (method: {method})")
        
        scraper = LinkedInScraper(settings, student_id)
        scraper.logger = type('obj', (object,), {'log_info': print, 'log_err': print, 'log_warn': print, 'log_ok': print})()
        
        print("Attempting LinkedIn login...")
        login_result = await scraper._login(page, student_id, settings)
        
        print(f"Login result: {login_result}")
        
        await asyncio.sleep(3)
        final_url = page.url
        print(f"Final URL: {final_url}")
        
        if "login" not in final_url.lower() or "feed" in final_url.lower():
            print("SUCCESS: Logged into LinkedIn!")
            await page.screenshot(path="/app/test_linkedin_success.png")
        else:
            print("FAILED: Still on login page")
            await page.screenshot(path="/app/test_linkedin_failed.png")
        
        await playwright_manager.return_page(page)
        return "login" not in final_url.lower() or "feed" in final_url.lower()
        
    except Exception as e:
        print(f"LinkedIn login FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_foundit_login():
    """Test FoundIt login via CDP."""
    print("\n" + "=" * 60)
    print("TEST 4: FOUNDIT LOGIN")
    print("=" * 60)
    
    from scraper_adapter.playwright_manager import playwright_manager
    from scraper_adapter.foundit import FounditScraper
    from config.settings import settings
    from database.credentials import get_student_credentials
    
    student_id = "student_4443c80f"
    creds = get_student_credentials(student_id)
    
    if not creds:
        print(f"No credentials found for {student_id}")
        return False
        
    foundit_creds = creds.get("foundit", {})
    username = foundit_creds.get("username") or foundit_creds.get("email")
    password = foundit_creds.get("password")
    
    print(f"Using credentials: {username}")
    
    try:
        page, method = await playwright_manager.get_page_with_cdp_fallback(
            settings=settings, 
            student_id=student_id, 
            cdp_url="http://chrome-cdp:3000"
        )
        print(f"CDP Page: SUCCESS (method: {method})")
        
        scraper = FounditScraper(settings, student_id)
        scraper.logger = type('obj', (object,), {'log_info': print, 'log_err': print, 'log_warn': print, 'log_ok': print})()
        
        print("Attempting FoundIt login...")
        login_result = await scraper._login(page, student_id, settings)
        
        print(f"Login result: {login_result}")
        
        await asyncio.sleep(3)
        final_url = page.url
        print(f"Final URL: {final_url}")
        
        if "login" not in final_url.lower():
            print("SUCCESS: Logged into FoundIt!")
            await page.screenshot(path="/app/test_foundit_success.png")
        else:
            print("FAILED: Still on login page")
            await page.screenshot(path="/app/test_foundit_failed.png")
        
        await playwright_manager.return_page(page)
        return "login" not in final_url.lower()
        
    except Exception as e:
        print(f"FoundIt login FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("=" * 60)
    print("PLATFORM LOGIN TEST SUITE")
    print("=" * 60)
    
    results = {}
    
    # Test 1: CDP Connection
    results['CDP'] = await test_cdp_connection()
    
    # Test 2: Naukri Login
    if results['CDP']:
        results['Naukri'] = await test_naukri_login()
    else:
        results['Naukri'] = False
        print("Skipping Naukri - CDP failed")
    
    # Test 3: LinkedIn Login
    if results['CDP']:
        results['LinkedIn'] = await test_linkedin_login()
    else:
        results['LinkedIn'] = False
        print("Skipping LinkedIn - CDP failed")
    
    # Test 4: FoundIt Login
    if results['CDP']:
        results['FoundIt'] = await test_foundit_login()
    else:
        results['FoundIt'] = False
        print("Skipping FoundIt - CDP failed")
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    for test, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {test}: {status}")
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    print(f"\nTotal: {passed}/{total} passed")
    
    return all(results.values())


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)