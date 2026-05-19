"""
Platform Login Test - Test all 3 platforms with different strategies
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


async def test_platform(url, name):
    """Test a platform with proper stealth."""
    print(f"\n{'=' * 60}")
    print(f"TEST: {name}")
    print(f"{'=' * 60}")
    
    from playwright.async_api import async_playwright
    
    p = await async_playwright().start()
    
    try:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            permissions=["geolocation"],
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
        )
        
        page = await context.new_page()
        
        # Add CDP detection evasion
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        print(f"Navigating to {url}...")
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        url_result = page.url
        title = await page.title()
        
        print(f"URL: {url_result}")
        print(f"Title: {title[:60]}")
        
        content = await page.content()
        content_lower = content.lower()
        
        blocked = "access denied" in content_lower or "blocked" in content_lower or "captcha" in content_lower
        
        if blocked:
            print("STATUS: BLOCKED")
        else:
            print("STATUS: OK")
            
            if "login" in content_lower and "email" in content_lower:
                print("Found: Login form")
            elif "login" in content_lower and "username" in content_lower:
                print("Found: Login form")
        
        screenshot_name = f"/app/test_{name.lower()}.png"
        await page.screenshot(path=screenshot_name)
        print(f"Screenshot: {screenshot_name}")
        
        await context.close()
        await browser.close()
        await p.stop()
        
        return not blocked
        
    except Exception as e:
        print(f"ERROR: {e}")
        try:
            await p.stop()
        except:
            pass
        return False


async def main():
    print("=" * 60)
    print("PLATFORM LOGIN TEST SUITE")
    print("=" * 60)
    
    results = {}
    
    # Test all 3 platforms
    results['Naukri'] = await test_platform("https://www.naukri.com/nlogin/login", "Naukri")
    results['LinkedIn'] = await test_platform("https://www.linkedin.com/login", "LinkedIn")
    results['FoundIt'] = await test_platform("https://www.foundit.in/login", "FoundIt")
    
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for platform, result in results.items():
        status = "PASS" if result else "BLOCKED"
        print(f"  {platform}: {status}")
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    print(f"\nTotal: {passed}/{total} accessible")
    
    return passed > 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)