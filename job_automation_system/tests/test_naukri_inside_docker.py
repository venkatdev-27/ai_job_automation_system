"""
Naukri selector diagnostic - runs INSIDE Docker container.
Uses Playwright fallback (CDP is blocked by Naukri WAF in Docker).
"""
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path("/app")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
os.environ["USE_CDP"] = "false"
os.environ["PLAYWRIGHT_HEADLESS"] = "true"
os.environ["IN_DOCKER"] = "true"

import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
for noisy in ['pymongo', 'dns', 'urllib3', 'hpack', 'httpcore', 'httpx']:
    logging.getLogger(noisy).setLevel(logging.WARNING)


async def test():
    print("=" * 60)
    print("NAUKRI - INSIDE DOCKER (PLAYWRIGHT)")
    print("=" * 60)

    from scraper_adapter.playwright_manager import playwright_manager
    from config.settings import settings
    from database.credentials import get_student_credentials

    page, method = await playwright_manager.get_page_with_cdp_fallback(
        settings=settings, student_id="test", cdp_url=None
    )
    print(f"Method: {method}")

    print("\nNavigating to Naukri login...")
    await page.goto("https://www.naukri.com/nlogin/login", timeout=60000, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    print(f"URL: {page.url}")
    print(f"Title: {(await page.title())[:80]}")

    print("\n--- All input fields ---")
    inputs = await page.locator("input").all()
    print(f"Total: {len(inputs)}")
    for i, inp in enumerate(inputs):
        t = await inp.get_attribute("type") or ""
        n = await inp.get_attribute("name") or ""
        i_id = await inp.get_attribute("id") or ""
        c = await inp.get_attribute("class") or ""
        a = await inp.get_attribute("autocomplete") or ""
        vis = await inp.is_visible()
        ph = await inp.get_attribute("placeholder") or ""
        print(f"  [{i}] type={t}, name={n}, id={i_id}, class={c[:40]}, autocomplete={a}, visible={vis}, placeholder={ph}")

    print("\n--- Code selectors check ---")
    for sel in ["#usernameField", "#passwordField", "button[type='submit']", "#loginForm", "form"]:
        loc = page.locator(sel)
        cnt = await loc.count()
        if cnt > 0:
            vis = await loc.first.is_visible()
            print(f"  '{sel}': count={cnt}, visible={vis}")
        else:
            print(f"  '{sel}': NOT FOUND")

    print("\n--- Check for alternate selectors ---")
    for sel in ["[name='email']", "[name='username']", "[type='email']", "[placeholder*='Email']", "[placeholder*='Username']"]:
        loc = page.locator(sel)
        cnt = await loc.count()
        if cnt > 0:
            print(f"  '{sel}': count={cnt}")

    await page.screenshot(path="/app/logs/naukri_login_actual.png")
    html = await page.content()
    print(f"\nHTML length: {len(html)}")
    print(f"HTML snippet (first 800 chars):\n{html[:800]}")

    await playwright_manager.return_page(page)
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(test())