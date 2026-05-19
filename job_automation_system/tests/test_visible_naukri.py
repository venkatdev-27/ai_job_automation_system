"""
Direct Local Test with Visible Browser
Runs the scraper directly (not via Celery) for visible Chrome
"""
import asyncio

# --- FAST TEST MODE ---
# Overrides asyncio.sleep to drastically speed up local UI testing 
# without modifying the production scraper's anti-bot delays.
_original_sleep = asyncio.sleep
async def _fast_sleep(delay, result=None):
    return await _original_sleep(min(delay, 0.2), result)
asyncio.sleep = _fast_sleep
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Any
import logging

# Setup live logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# MongoDB connection
os.environ["MONGO_URI"] = os.environ.get("MONGO_URI", os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation"))
os.environ["MONGO_DB"] = os.environ.get("MONGO_DB", "ai_bot_resumes")

# Headless mode - force true in Docker/container
if os.environ.get("IN_DOCKER") or os.environ.get("PLAYWRIGHT_HEADLESS", "false").lower() == "true":
    os.environ["PLAYWRIGHT_HEADLESS"] = "true"
else:
    os.environ["PLAYWRIGHT_HEADLESS"] = os.environ.get("PLAYWRIGHT_HEADLESS", "false")

os.environ["PLAYWRIGHT_BROWSER"] = "chromium"

from database import get_student

@dataclass
class RuntimeSettings:
    target_applies: int = 10
    resume_variant: str = "backend"
    batch_size: int = 5
    max_applies_per_run: int = 10
    max_pages_per_run: int = 1
    ats_threshold: float = 35.0
    max_experience_years: int = 5
    min_fetch_delay_seconds: float = 2.0
    max_fetch_delay_seconds: float = 5.0
    extra_delay_after_n_applies: int = 5
    extra_delay_min: float = 4.0
    extra_delay_max: float = 10.0
    strict_fresher_only: bool = True
    preferred_job_types: list = field(default_factory=list)
    preferred_locations: list = field(default_factory=list)

async def run_direct_test():
    student_id = "student_2b4359c4"
    platform = "naukri"
    
    print("=" * 60)
    print("DIRECT NAUKRI TEST WITH VISIBLE BROWSER")
    print("=" * 60)
    
    # Get student
    student = get_student(student_id)
    if not student:
        print(f"ERROR: Student {student_id} not found!")
        return
    
    print(f"\nStudent: {student.name}")
    print(f"Skills: {student.skills[:5]}...")
    
    # Get credentials
    username = None
    password = None
    if hasattr(student, 'credentials'):
        creds = student.credentials
        if hasattr(creds, platform):
            platform_creds = getattr(creds, platform)
            username = platform_creds.username if hasattr(platform_creds, 'username') else None
            password = platform_creds.password if hasattr(platform_creds, 'password') else None
    
    print(f"\nCredentials: {username}")
    print(f"Resume variant: backend")
    
    if not username or not password:
        print(f"ERROR: No credentials for {platform}")
        return
    
    # Import scraper
    from scraper_adapter.naukri import NaukriScraper
    
    print("\n" + "=" * 60)
    print("STARTING VISIBLE BROWSER (AI + RAG ANSWERS MODE)...")
    print("=" * 60)
    
    scraper = NaukriScraper(max_results=5, timeout_seconds=30)
    scraper.headless = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    
    # Setup logger
    from utils.logger import get_logger
    scraper.logger = get_logger("naukri_visible.log")
    
    settings = RuntimeSettings(
        target_applies=10,
        resume_variant="backend"
    )
    
    try:
        # Run the main workflow
        result = await scraper.search_and_apply(
            profile=student,
            settings=settings,
        )
        
        print("\n" + "=" * 60)
        print("RESULT:")
        print(f"Applied: {result.get('applied', 0)}")
        print(f"Skipped: {result.get('skipped', 0)}")
        print(f"Status: {result.get('status', 'unknown')}")
        print("=" * 60)
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_direct_test())
