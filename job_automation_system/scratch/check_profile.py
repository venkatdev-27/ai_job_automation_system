import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
os.environ["MONGO_DB"] = "ai_bot_resumes"

from scraper_adapter.playwright_manager import playwright_manager
from scraper_adapter.naukri import NaukriScraper

class MockProfile:
    student_id = "student_2b4359c4"

class MockSettings:
    max_pages_per_run = 1
    max_applies_per_run = 1

async def main():
    profile = MockProfile()
    settings = MockSettings()
    
    page = await playwright_manager.get_page(settings, student_id=profile.student_id)
    scraper = NaukriScraper(logger=None)
    
    print("Navigating to profile...")
    await page.goto("https://www.naukri.com/mnjuser/profile", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(5)
    
    print("Dumping body text to see what loaded:")
    body_text = await page.inner_text("body")
    print(body_text[:1000])
    
    print("\nDumping HTML for 'resume' related elements:")
    try:
        # Find any element containing the word resume
        elements = await page.locator("*:has-text('resume')").all()
        for el in elements[-10:]:  # Print innermost elements
            tag = await el.evaluate("e => e.tagName")
            classes = await el.get_attribute("class")
            text = await el.inner_text()
            print(f"Tag: {tag}, Class: {classes}, Text: {text.strip()[:50]}")
    except Exception as e:
        print("Error finding elements:", e)
        
    await playwright_manager.close_all()

if __name__ == "__main__":
    asyncio.run(main())
