"""
Single isolated LinkedIn CDP test - check actual page selectors.
"""
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
os.environ["CDP_URL"] = "http://localhost:3000"
os.environ["USE_CDP"] = "true"
os.environ["PLAYWRIGHT_HEADLESS"] = "false"

import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

async def test():
    from scraper_adapter.playwright_manager import playwright_manager
    from config.settings import settings

    print("=" * 60)
    print("LINKEDIN CDP - CHECK PAGE SELECTORS")
    print("=" * 60)

    page, method = await playwright_manager.get_page_with_cdp_fallback(
        settings=settings, student_id="test", cdp_url="http://localhost:3000"
    )
    print(f"Method: {method}")

    # Go to LinkedIn login
    await page.goto("https://www.linkedin.com/login", timeout=60000, wait_until="domcontentloaded")
    print(f"URL: {page.url}")
    print(f"Title: {await page.title()}")

    await asyncio.sleep(2)

    # Get all input fields
    inputs = await page.locator("input").all()
    print(f"\nTotal input fields: {len(inputs)}")
    for i, inp in enumerate(inputs):
        try:
            inp_type = await inp.get_attribute("type") or ""
            inp_name = await inp.get_attribute("name") or ""
            inp_id = await inp.get_attribute("id") or ""
            inp_aria = await inp.get_attribute("aria-label") or ""
            inp_autocomplete = await inp.get_attribute("autocomplete") or ""
            inp_visible = await inp.is_visible()
            inp_placeholder = await inp.get_attribute("placeholder") or ""
            print(f"  [{i}] type={inp_type}, name={inp_name}, id={inp_id}, aria={inp_aria}, autocomplete={inp_autocomplete}, visible={inp_visible}, placeholder={inp_placeholder}")
        except:
            print(f"  [{i}] Error reading")

    # Take screenshot
    await page.screenshot(path="D:/ai-bot-resumes/linkedin_login_page.png")
    print("\nScreenshot saved: D:/ai-bot-resumes/linkedin_login_page.png")

    await playwright_manager.return_page(page)

if __name__ == "__main__":
    asyncio.run(test())