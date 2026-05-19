"""
LinkedIn CDP Connection Test
=============================
Tests the full CDP flow used by LinkedIn scraper.
Run from job_automation_system directory:
    python tests/test_linkedin_cdp.py
"""
import asyncio

_original_sleep = asyncio.sleep
async def _fast_sleep(delay, result=None):
    return await _original_sleep(min(delay, 0.3), result)
asyncio.sleep = _fast_sleep

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
os.environ["MONGO_DB"] = "ai_bot_resumes"
os.environ["CDP_URL"] = "http://localhost:3000"
os.environ["USE_CDP"] = "true"
os.environ["PLAYWRIGHT_HEADLESS"] = "false"

import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
for noisy in ['pymongo', 'dns', 'urllib3', 'hpack', 'httpcore', 'httpx']:
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def test_cdp_connection():
    """Test 1: Direct CDP connection to browserless container."""
    print("\n" + "=" * 60)
    print("TEST 1: Direct CDP Connection")
    print("=" * 60)

    cdp_url = os.environ.get("CDP_URL", "http://localhost:3000")
    use_cdp = os.environ.get("USE_CDP", "true").lower() == "true"

    print(f"CDP_URL: {cdp_url}")
    print(f"USE_CDP: {use_cdp}")

    if not use_cdp:
        print("SKIPPED: USE_CDP=false")
        return False

    try:
        from playwright.async_api import async_playwright

        p = await async_playwright().start()
        print(f"Connecting to CDP: {cdp_url}")
        browser = await p.chromium.connect_over_cdp(cdp_url)
        print("CDP Connected!")

        contexts = browser.contexts
        if contexts and contexts[0].pages:
            page = contexts[0].pages[0]
            print(f"Existing page URL: {page.url}")
        else:
            page = await browser.new_page()
            print("Created new page")

        print("Navigating to LinkedIn...")
        await page.goto("https://www.linkedin.com/", timeout=30000)
        print(f"URL after load: {page.url}")

        cookies = await page.context.cookies()
        print(f"Cookies count: {len(cookies)}")

        title = await page.title()
        print(f"Page title: {title[:80]}")

        await browser.close()
        await p.stop()

        if "login" in page.url.lower():
            print("RESULT: CDP works, but requires login (expected)")
        else:
            print("RESULT: CDP works, session already active!")

        return True

    except Exception as e:
        print(f"FAILED: {e}")
        return False


async def test_cdp_fallback():
    """Test 2: CDP fallback to regular Playwright."""
    print("\n" + "=" * 60)
    print("TEST 2: CDP Fallback to Playwright")
    print("=" * 60)

    try:
        from scraper_adapter.playwright_manager import playwright_manager
        from config.settings import settings

        print("Trying get_page_with_cdp_fallback (CDP first, then Playwright)...")
        page, method = await playwright_manager.get_page_with_cdp_fallback(
            settings=settings,
            student_id="test_cdp_student"
        )

        print(f"Method used: {method.upper()}")

        print("Navigating to LinkedIn...")
        await page.goto("https://www.linkedin.com/", timeout=30000)
        print(f"URL: {page.url}")

        cookies = await page.context.cookies()
        print(f"Cookies: {len(cookies)}")

        title = await page.title()
        print(f"Title: {title[:80]}")

        await playwright_manager.return_page(page)

        if method == "cdp":
            print("RESULT: CDP succeeded!")
        else:
            print("RESULT: CDP failed, Playwright fallback worked!")

        return True

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_linkedin_scraper_login():
    """Test 3: Full LinkedIn scraper with CDP."""
    print("\n" + "=" * 60)
    print("TEST 3: LinkedIn Scraper Login via CDP")
    print("=" * 60)

    try:
        from database import get_student
        from scraper_adapter.linkedin import LinkedIn10_10
        from database.credentials import get_student_credentials

        student_id = "student_4443c80f"
        student = get_student(student_id)
        if not student:
            print(f"Student {student_id} not found!")
            return False

        print(f"Student: {student.name}")

        creds = get_student_credentials(student_id)
        if creds:
            linkedin = creds.get("linkedin", {})
            username = linkedin.get("username") or linkedin.get("email")
            password = linkedin.get("password")
            print(f"Username: {username}")
            print(f"Password: {'*' * len(password) if password else 'MISSING'}")
        else:
            print("No credentials found!")
            return False

        from dataclasses import dataclass

        @dataclass
        class RuntimeSettings:
            target_applies: int = 3
            resume_variant: str = "backend"
            batch_size: int = 2
            max_applies_per_run: int = 3
            max_pages_per_run: int = 1
            ats_threshold: float = 45.0

        scraper = LinkedIn10_10()
        scraper.headless = False

        class SimpleLogger:
            def log_info(self, msg): print(f"  INFO: {msg}")
            def log_warn(self, msg): print(f"  WARN: {msg}")
            def log_err(self, msg): print(f"  ERR: {msg}")
            def log_ok(self, msg): print(f"  OK: {msg}")

        logger2 = SimpleLogger()
        settings = RuntimeSettings()

        print("\nStarting LinkedIn search_and_apply...")
        result = await scraper.search_and_apply(
            profile=student,
            settings=settings,
            logger=logger2,
        )

        print(f"\nApplied: {result.get('applied', 0)}")
        print(f"Skipped: {result.get('skipped', 0)}")
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"Error: {result.get('error', 'none')}")

        return result.get('applied', 0) > 0 or result.get('status') in ('success', 'partial')

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("=" * 60)
    print("LINKEDIN CDP TEST SUITE")
    print("=" * 60)

    results = {}

    results['cdp_direct'] = await test_cdp_connection()
    results['cdp_fallback'] = await test_cdp_fallback()
    results['linkedin_login'] = await test_linkedin_scraper_login()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for test, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {test:20s}: {status}")
    print("=" * 60)

    all_passed = all(results.values())
    if all_passed:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED")


if __name__ == "__main__":
    asyncio.run(main())