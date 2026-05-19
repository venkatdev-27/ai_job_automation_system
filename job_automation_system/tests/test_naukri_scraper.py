import asyncio
import os
import sys
from pathlib import Path

# Adjust path when running in Docker
PROJECT_ROOT = Path("/app")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Setup environment for Docker test
os.environ["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
os.environ["USE_CDP"] = "false"
os.environ["PLAYWRIGHT_HEADLESS"] = "true"
os.environ["IN_DOCKER"] = "true"

import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

from scraper_adapter.naukri import NaukriScraper
from config.settings import settings
from scraper_adapter.playwright_manager import playwright_manager

class DummyLogger:
    def log_info(self, msg): print(f"[INFO] {msg}")
    def log_err(self, msg): print(f"[ERR] {msg}")
    def log_warn(self, msg): print(f"[WARN] {msg}")
    def log_ok(self, msg): print(f"[OK] {msg}")

class DummyProfile:
    def __init__(self):
        self.student_id = "student_4443c80f"
        self._id = "student_4443c80f"
        self.username = ""
        self.password = ""
        self.target_role = "Software Engineer"

async def test():
    print("============================================================")
    print("TESTING NAUKRI SCRAPER LOGIN (INSIDE DOCKER)")
    print("============================================================")
    
    logger = DummyLogger()
    scraper = NaukriScraper(logger=logger)
    profile = DummyProfile()
    
    # We don't use CDP here to test the pure Playwright fallback flow that was failing
    page = await playwright_manager.get_page(settings, student_id=profile.student_id)
    
    from utils.session_manager import SessionManager
    session_mgr = SessionManager(profile.student_id, "naukri")
    await session_mgr.clear_session()
    
    print("Invoking scraper._ensure_logged_in()...")
    result = await scraper._ensure_logged_in(page, settings, profile)
    
    if result:
        await page.screenshot(path="/app/logs/naukri_test_success.png")
        print("Captured screenshot at /app/logs/naukri_test_success.png")
        
    print(f"\nFinal Result: {'SUCCESS' if result else 'FAILED'}")
    await playwright_manager.return_page(page)

if __name__ == "__main__":
    asyncio.run(test())
