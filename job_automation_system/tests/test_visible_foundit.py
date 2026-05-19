"""
Direct Local Test with Visible Browser for FoundIt
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
from dataclasses import dataclass
import logging

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["MONGO_URI"] = "mongodb+srv://kosurivenky:venkyyamuna@cluster0.uhbfag1.mongodb.net/ai_bot_resumes?appName=Cluster0"
os.environ["MONGO_DB"] = "ai_bot_resumes"
os.environ["PLAYWRIGHT_HEADLESS"] = "false"
os.environ["PLAYWRIGHT_BROWSER"] = "chromium"

# Setup live logging - only show scraper steps, suppress MongoDB/network noise
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
# Silence noisy libraries
for noisy in ['pymongo', 'dns', 'urllib3', 'asyncio', 'hpack', 'httpcore', 'httpx']:
    logging.getLogger(noisy).setLevel(logging.WARNING)

class AppLogger:
    """Wrapper to add custom log methods to standard logger"""
    def __init__(self, logger):
        self.logger = logger
    
    def log_info(self, msg, *args):
        self.logger.info(msg, *args)
    
    def log_warn(self, msg, *args):
        self.logger.warning(msg, *args)
    
    def log_err(self, msg, *args):
        self.logger.error(msg, *args)
    
    def log_ok(self, msg, *args):
        self.logger.log(25, msg, *args)
    
    def log_application_success(self, job_id, title, company, platform):
        self.logger.info(f"APPLIED: {job_id} | {title} @ {company} on {platform}")

from database import get_student

@dataclass
class RuntimeSettings:
    target_applies: int = 10
    resume_variant: str = "backend"
    batch_size: int = 5
    ats_threshold: float = 20.0

async def run_foundit_test():
    student_id = "student_2b4359c4"
    
    print("=" * 60)
    print("FOUNDIT TEST WITH VISIBLE BROWSER - LIVE LOGS")
    print("=" * 60)
    
    student = get_student(student_id)
    if not student:
        print(f"ERROR: Student {student_id} not found!")
        return
    
    print(f"\nStudent: {student.name}")
    print(f"Skills: {student.skills[:10]}")
    print(f"Resume variant: backend")
    
    from scraper_adapter.foundit import FoundItScraper
    
    scraper = FoundItScraper(max_results=2, timeout_seconds=90)
    scraper.headless = False
    
    scraper.logger = AppLogger(logging.getLogger("foundit"))
    scraper.profile = student
    
    settings = RuntimeSettings(target_applies=10, resume_variant="backend")
    
    try:
        print("\n=== STARTING FOUNDIT SCRAPER ===")
        result = await scraper.search_and_apply(student, settings)
        
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
    finally:
        # Clean Playwright resources to avoid Event loop closed / EPIPE on script exit.
        try:
            from scraper_adapter.playwright_manager import playwright_manager
            await playwright_manager.shutdown()
        except Exception:
            pass
        asyncio.sleep = _original_sleep

if __name__ == "__main__":
    asyncio.run(run_foundit_test())
