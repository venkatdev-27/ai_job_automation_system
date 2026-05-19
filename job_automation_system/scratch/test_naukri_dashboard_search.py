import asyncio
import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scraper_adapter.playwright_manager import PlaywrightManager
from scraper_adapter.naukri import NaukriScraper
from utils.logger import get_logger

async def test_dashboard_search():
    logger = get_logger("test_naukri_search.log")
    pm = PlaywrightManager(logger)
    scraper = NaukriScraper(logger=logger)
    
    # Use a dummy profile/settings
    class Dummy: pass
    settings = Dummy()
    profile = {
        "candidate_id": "student_4443c80f",
        "email": "divya.peddi@example.com"
    }
    
    try:
        page = await pm.get_page(settings, student_id="student_4443c80f")
        
        # Manually set credentials for test
        email = "divya.peddi@gmail.com" # I saw this in earlier logs
        password = "..." # I don't know it, but I can bypass _ensure_logged_in 
        # if I'm already logged in.
        
        # 1. Login (Manually triggered via direct navigation if needed, 
        # but let's try to mock the credentials resolver)
        
        def mock_resolve(*args):
            return "k.venky5678@gmail.com", "Venkyyamuna@143322", "manual_test" # Corrected credentials
            
        scraper._resolve_naukri_credentials = mock_resolve
        
        logged_in = await scraper._ensure_logged_in(page, settings, profile)
        if not logged_in:
            print("Login failed")
            return

        print(f"Logged in. Current URL: {page.url}")
        
        # 2. Try to search via dashboard
        print("Interacting with dashboard search bar...")
        
        # Click search placeholder to reveal input
        try:
            await page.click(".nI-gNb-sb__placeholder", timeout=5000)
            await asyncio.sleep(1)
        except:
            print("Placeholder not found or already expanded")

        # 2b. Select job type (Mandatory for Campus)
        try:
            # Click dropdown placeholder
            await page.click(".dropdownMainContainer", timeout=5000)
            await asyncio.sleep(1)
            # Click "Jobs" option
            await page.click("text=Jobs", timeout=5000)
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Dropdown selection failed: {e}")

        # Fill input
        await page.fill("input.suggestor-input", "Java Backend Developer")
        await asyncio.sleep(1)
        
        # Click search icon
        await page.click(".nI-gNb-sb__icon-wrapper")
        
        print("Waiting for results...")
        await asyncio.sleep(5)
        print(f"URL after search: {page.url}")
        
        await page.screenshot(path="/app/logs/naukri_search_result_debug.png")
        html = await page.content()
        with open("/app/logs/naukri_search_result_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
            
    finally:
        await pm.close_student_context("student_4443c80f")

if __name__ == "__main__":
    asyncio.run(test_dashboard_search())
