"""
Naukri end-to-end login test via CDP.
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
os.environ["PLAYWRIGHT_BROWSER"] = "chromium"
os.environ["STEALTH"] = "true"

import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
for noisy in ['pymongo', 'dns', 'urllib3', 'hpack', 'httpcore', 'httpx']:
    logging.getLogger(noisy).setLevel(logging.WARNING)


async def test():
    print("=" * 60)
    print("NAUKRI CDP - END-TO-END LOGIN TEST")
    print("=" * 60)

    from scraper_adapter.playwright_manager import playwright_manager
    from config.settings import settings
    from database.credentials import get_student_credentials

    student_id = "student_4443c80f"
    creds = get_student_credentials(student_id)
    if not creds:
        print("No credentials!")
        return

    naukri = creds.get("naukri", {})
    username = naukri.get("username") or naukri.get("email")
    password = naukri.get("password")
    print(f"Credentials: {username}")

    print("\nStep 1: Get CDP page")
    page, method = await playwright_manager.get_page_with_cdp_fallback(
        settings=settings, student_id=student_id, cdp_url="http://localhost:3000"
    )
    print(f"Method: {method}")

    print("\nStep 2: Navigate to Naukri login")
    try:
        await page.goto("https://www.naukri.com/nlogin/login", timeout=60000, wait_until="domcontentloaded")
    except Exception as e:
        print(f"Navigation error: {e}")
        await asyncio.sleep(2)
    await asyncio.sleep(5)
    print(f"URL: {page.url}")
    print(f"Title: {(await page.title())[:80]}")
    print(f"Method used: {method}")

    print("\nStep 3: Debug all input fields")
    inputs = await page.locator("input").all()
    print(f"Total inputs: {len(inputs)}")
    for i, inp in enumerate(inputs):
        t = await inp.get_attribute("type") or ""
        n = await inp.get_attribute("name") or ""
        i_id = await inp.get_attribute("id") or ""
        a = await inp.get_attribute("autocomplete") or ""
        c = await inp.get_attribute("class") or ""
        vis = await inp.is_visible()
        ph = await inp.get_attribute("placeholder") or ""
        print(f"  [{i}] type={t}, name={n}, id={i_id}, autocomplete={a}, visible={vis}, class={c[:40]}, placeholder={ph}")

    await page.screenshot(path="D:/ai-bot-resumes/naukri_login_page.png")
    print("\nScreenshot saved: D:/ai-bot-resumes/naukri_login_page.png")

    html = await page.content()
    print(f"HTML length: {len(html)}")
    print(f"HTML snippet (first 500 chars): {html[:500]}")
    print(f"URL at screenshot: {page.url}")

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

    print("\nStep 5: Fill using brute-force visible inputs")
    filled_username = False
    filled_password = False

    all_inputs = await page.locator("input").all()
    for i, inp in enumerate(all_inputs):
        try:
            vis = await inp.is_visible()
            t = await inp.get_attribute("type") or ""
            if not vis:
                continue
            if t in ["text", "email", "tel", ""] and not filled_username:
                await inp.fill(username)
                print(f"Filled username at input[{i}], type={t}")
                filled_username = True
            elif t == "password" and not filled_password:
                await inp.fill(password)
                print(f"Filled password at input[{i}], type={t}")
                filled_password = True
            if filled_username and filled_password:
                break
        except Exception as e:
            print(f"Input[{i}] error: {e}")

    print(f"Fill result: username={filled_username}, password={filled_password}")

    if not filled_username or not filled_password:
        print("Step 5b: Retry using code selectors")
        if not filled_username:
            try:
                loc = page.locator("#usernameField").first
                if await loc.is_visible():
                    await loc.fill(username, timeout=5000)
                    print("Filled via #usernameField")
                    filled_username = True
            except Exception as e:
                print(f"#usernameField fill failed: {e}")
        if not filled_password:
            try:
                loc = page.locator("#passwordField").first
                if await loc.is_visible():
                    await loc.fill(password, timeout=5000)
                    print("Filled via #passwordField")
                    filled_password = True
            except Exception as e:
                print(f"#passwordField fill failed: {e}")

    print("\nStep 6: Click submit")
    await asyncio.sleep(1)

    submit_selectors = ["button[type='submit']", "button:has-text('Login')", "button:has-text('Sign In')"]
    for sel in submit_selectors:
        btn = page.locator(sel)
        cnt = await btn.count()
        if cnt > 0 and await btn.first.is_visible():
            print(f"Clicking: {sel}")
            await btn.first.click(timeout=5000)
            break
    else:
        print("Submit button not found, pressing Enter")
        try:
            pwd_field = page.locator("#passwordField").first
            if await pwd_field.is_visible():
                await pwd_field.press("Enter", timeout=5000)
        except:
            pass

    print("Waiting for navigation...")
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        await asyncio.sleep(3)
    except Exception:
        print("Navigation timeout - checking current state")

    try:
        final_url = page.url
        final_title = (await page.title())[:80]
        print(f"After login URL: {final_url}")
        print(f"Title: {final_title}")
        await page.screenshot(path="D:/ai-bot-resumes/naukri_after_login.png")
        print("Screenshot saved: D:/ai-bot-resumes/naukri_after_login.png")

        page_text = await page.locator("body").inner_text()
        if "wrong" in page_text.lower() or "incorrect" in page_text.lower() or "invalid" in page_text.lower():
            print("ERROR: Login error message detected")
        if "access denied" in page_text.lower() or "blocked" in page_text.lower():
            print("WARNING: Access denied or blocked")

        if "nlogin" not in final_url.lower() and final_url:
            print("SUCCESS: Login appears successful!")
        else:
            print("WARNING: May not have logged in")
    except Exception as e:
        print(f"Result check error: {e}")
        try:
            await page.screenshot(path="D:/ai-bot-resumes/naukri_error.png")
        except:
            pass

    try:
        await playwright_manager.return_page(page)
    except Exception:
        pass

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(test())