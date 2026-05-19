"""
Naukri selector diagnostic test - inspect actual login page selectors.
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
for noisy in ['pymongo', 'dns', 'urllib3', 'hpack', 'httpcore', 'httpx']:
    logging.getLogger(noisy).setLevel(logging.WARNING)


async def test():
    print("=" * 60)
    print("NAUKRI CDP - CHECK PAGE SELECTORS")
    print("=" * 60)

    from scraper_adapter.playwright_manager import playwright_manager
    from config.settings import settings

    print("\nStep 1: Get CDP page")
    page, method = await playwright_manager.get_page_with_cdp_fallback(
        settings=settings, student_id="test", cdp_url="http://localhost:3000"
    )
    print(f"Method: {method}")

    print("\nStep 2: Navigate to Naukri login")
    await page.goto("https://www.naukri.com/nlogin/login", timeout=60000, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    print(f"URL: {page.url}")
    print(f"Title: {(await page.title())[:80]}")

    print("\nStep 3: Debug all input fields")
    inputs = await page.locator("input").all()
    print(f"Total input fields: {len(inputs)}")
    for i, inp in enumerate(inputs):
        try:
            inp_type = await inp.get_attribute("type") or ""
            inp_name = await inp.get_attribute("name") or ""
            inp_id = await inp.get_attribute("id") or ""
            inp_class = await inp.get_attribute("class") or ""
            inp_autocomplete = await inp.get_attribute("autocomplete") or ""
            inp_visible = await inp.is_visible()
            inp_placeholder = await inp.get_attribute("placeholder") or ""
            print(f"  [{i}] type={inp_type}, name={inp_name}, id={inp_id}, class={inp_class[:40]}, autocomplete={inp_autocomplete}, visible={inp_visible}, placeholder={inp_placeholder}")
        except:
            print(f"  [{i}] Error reading")

    await page.screenshot(path="D:/ai-bot-resumes/naukri_login_page.png")
    print("\nScreenshot saved: D:/ai-bot-resumes/naukri_login_page.png")

    print("\nStep 4: Check specific selectors used in code")
    code_selectors = ["#usernameField", "#passwordField", "button[type='submit']"]
    for sel in code_selectors:
        loc = page.locator(sel)
        cnt = await loc.count()
        if cnt > 0:
            vis = await loc.first.is_visible()
            print(f"  '{sel}': count={cnt}, visible={vis}")
        else:
            print(f"  '{sel}': NOT FOUND")

    await playwright_manager.return_page(page)
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(test())