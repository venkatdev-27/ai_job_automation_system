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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
os.environ["MONGO_DB"] = "ai_bot_resumes"
os.environ["PLAYWRIGHT_HEADLESS"] = "false"
os.environ["PLAYWRIGHT_BROWSER"] = "chromium"

import logging

# Setup live logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

base_logger = logging.getLogger("job_automation_system")
base_logger.setLevel(logging.INFO)
logging.getLogger().setLevel(logging.INFO)
# Silence noisy libraries
for noisy in ['pymongo', 'dns', 'urllib3', 'asyncio', 'hpack', 'httpcore', 'httpx']:
    logging.getLogger(noisy).setLevel(logging.WARNING)

def create_app_logger(name: str) -> logging.Logger:
    """Create a logger with custom methods (log_info, log_err, etc.)"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    def log_info(msg, *args): logger.info(msg, *args)
    def log_warn(msg, *args): logger.warning(msg, *args)
    def log_err(msg, *args): logger.error(msg, *args)
    def log_ok(msg, *args): logger.log(25, msg, *args)
    
    logger.log_info = log_info
    logger.log_warn = log_warn
    logger.log_err = log_err
    logger.log_ok = log_ok
    
    return logger

logger = logging.getLogger(__name__)


@dataclass
class RuntimeSettings:
    target_applies: int = 6
    resume_variant: str = "backend"
    batch_size: int = 5
    max_applies_per_run: int = 6
    max_pages_per_run: int = 2
    ats_threshold: float = 45.0


async def run_linkedin_test():
    student_id = "student_2b4359c4"
    
    print("=" * 60)
    print("LINKEDIN TEST WITH VISIBLE BROWSER")
    print("=" * 60)
    
    from database import get_student
    from scraper_adapter.linkedin import LinkedIn10_10
    
    student = get_student(student_id)
    if not student:
        print(f"ERROR: Student {student_id} not found!")
        return
    
    print(f"\nStudent: {student.name}")
    print(f"Skills: {student.skills[:6]}...")
    
    username = None
    password = None
    if hasattr(student, 'credentials'):
        creds = student.credentials
        if hasattr(creds, 'linkedin'):
            platform_creds = getattr(creds, 'linkedin')
            username = platform_creds.username if hasattr(platform_creds, 'username') else None
            password = platform_creds.password if hasattr(platform_creds, 'password') else None
    
    print(f"\nCredentials: {username}")
    print(f"Resume variant: backend")
    
    if not username or not password:
        print(f"ERROR: No LinkedIn credentials!")
        return
    
    settings = RuntimeSettings(
        target_applies=6,
        resume_variant="backend"
    )
    
    scraper = LinkedIn10_10()
    scraper.headless = False
    scraper.logger = create_app_logger("linkedin")
    
    print("\n" + "=" * 60)
    print("STARTING LINKEDIN BROWSER...")
    print("=" * 60)
    
    try:
        result = await scraper.search_and_apply(
            profile=student,
            settings=settings,
            logger=scraper.logger,
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
    asyncio.run(run_linkedin_test())
