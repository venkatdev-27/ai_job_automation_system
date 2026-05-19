"""
Fully Automated Local Test with Visible Browser
Runs all 3 platforms (Naukri, LinkedIn, FoundIt) sequentially with visible Chrome

Usage:
    python tests/test_visible_all_platforms.py

This script will:
1. Open visible Chrome browser
2. Apply to jobs on Naukri
3. Wait 5 seconds
4. Apply to jobs on LinkedIn
5. Wait 5 seconds
6. Apply to jobs on FoundIt
7. Show final summary
"""
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/job_automation")
os.environ["MONGO_DB"] = "ai_bot_resumes"

os.environ["PLAYWRIGHT_HEADLESS"] = "false"
os.environ["PYTHONUNBUFFERED"] = "1"

from dataclasses import dataclass
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

base_logger = logging.getLogger("job_automation_system")
base_logger.setLevel(logging.INFO)

def create_app_logger(name: str) -> logging.Logger:
    """Create a logger with the custom methods (log_info, log_err, etc.)."""
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

logger = create_app_logger("main")


@dataclass
class RuntimeSettings:
    target_applies: int = 5
    resume_variant: str = "backend"
    batch_size: int = 5
    max_applies_per_run: int = 5
    ats_threshold: float = 65.0


def get_credentials(student, platform: str):
    """Extract credentials for a specific platform."""
    username = None
    password = None
    if hasattr(student, 'credentials'):
        creds = student.credentials
        if hasattr(creds, platform):
            platform_creds = getattr(creds, platform)
            username = platform_creds.username if hasattr(platform_creds, 'username') else None
            password = platform_creds.password if hasattr(platform_creds, 'password') else None
    return username, password


async def run_naukri(student, settings):
    """Run Naukri scraper with visible browser."""
    from scraper_adapter.naukri import NaukriScraper
    
    username, password = get_credentials(student, "naukri")
    if not username or not password:
        logger.error("No Naukri credentials found!")
        return {"applied": 0, "skipped": 0, "status": "no_credentials"}
    
    logger.info("=" * 70)
    logger.info(">>> STARTING NAUKRI WITH VISIBLE BROWSER <<<")
    logger.info("=" * 70)
    logger.info(f"Username: {username}")
    logger.info(f"Resume variant: {settings.resume_variant}")
    
    scraper = NaukriScraper(max_results=5, timeout_seconds=30)
    scraper.headless = False
    scraper.logger = create_app_logger("naukri")
    
    try:
        result = await scraper.search_and_apply(
            profile=student,
            settings=settings,
        )
        return result
    except Exception as e:
        import traceback
        logger.error(f"Naukri error: {e}")
        traceback.print_exc()
        return {"applied": 0, "skipped": 0, "status": "error", "error": str(e)}


async def run_linkedin(student, settings):
    """Run LinkedIn scraper with visible browser."""
    from scraper_adapter.linkedin import LinkedIn10_10
    
    username, password = get_credentials(student, "linkedin")
    if not username or not password:
        logger.error("No LinkedIn credentials found!")
        return {"applied": 0, "skipped": 0, "status": "no_credentials"}
    
    logger.info("=" * 70)
    logger.info(">>> STARTING LINKEDIN WITH VISIBLE BROWSER <<<")
    logger.info("=" * 70)
    logger.info(f"Username: {username}")
    logger.info(f"Resume variant: {settings.resume_variant}")
    
    scraper = LinkedIn10_10()
    scraper.headless = False
    scraper.logger = create_app_logger("linkedin")
    
    try:
        result = await scraper.search_and_apply(
            profile=student,
            settings=settings,
            logger=logging.getLogger("linkedin"),
        )
        return result
    except Exception as e:
        import traceback
        logger.error(f"LinkedIn error: {e}")
        traceback.print_exc()
        return {"applied": 0, "skipped": 0, "status": "error", "error": str(e)}


async def run_foundit(student, settings):
    """Run FoundIt scraper with visible browser."""
    from scraper_adapter.foundit import FoundItScraper
    
    username, password = get_credentials(student, "foundit")
    if not username or not password:
        logger.error("No FoundIt credentials found!")
        return {"applied": 0, "skipped": 0, "status": "no_credentials"}
    
    logger.info("=" * 70)
    logger.info(">>> STARTING FOUNDIT WITH VISIBLE BROWSER <<<")
    logger.info("=" * 70)
    logger.info(f"Username: {username}")
    logger.info(f"Resume variant: {settings.resume_variant}")
    
    scraper = FoundItScraper(max_results=5, timeout_seconds=30)
    scraper.headless = False
    scraper.logger = create_app_logger("foundit")
    
    try:
        result = await scraper.search_and_apply(
            profile=student,
            settings=settings,
        )
        return result
    except Exception as e:
        import traceback
        logger.error(f"FoundIt error: {e}")
        traceback.print_exc()
        return {"applied": 0, "skipped": 0, "status": "error", "error": str(e)}


async def run_all_platforms():
    """Run all 3 platforms sequentially with visible browser."""
    student_id = "student_2b4359c4"
    
    print("\n" + "=" * 70)
    print(">>> FULL AUTOMATION TEST - ALL 3 PLATFORMS WITH VISIBLE BROWSER <<<")
    print("=" * 70)
    
    from database import get_student
    
    student = get_student(student_id)
    if not student:
        logger.error(f"Student {student_id} not found!")
        print(f"\nERROR: Student {student_id} not found in database!")
        return
    
    print(f"\n{'='*70}")
    print(f"Student: {student.name}")
    print(f"Skills: {student.skills[:10] if student.skills else 'None'}...")
    print(f"{'='*70}")
    
    settings = RuntimeSettings(
        target_applies=3,
        resume_variant="backend"
    )
    
    total_applied = 0
    total_skipped = 0
    platforms_completed = 0
    
    platforms = [
        ("naukri", run_naukri),
        ("linkedin", run_linkedin),
        ("foundit", run_foundit),
    ]
    
    for platform_name, run_func in platforms:
        print(f"\n>>> PLATFORM: {platform_name.upper()} <<<\n")
        
        try:
            result = await run_func(student, settings)
            
            applied = result.get("applied", 0)
            skipped = result.get("skipped", 0)
            status = result.get("status", "unknown")
            
            total_applied += applied
            total_skipped += skipped
            platforms_completed += 1
            
            print(f"\n--- {platform_name.upper()} COMPLETE ---")
            print(f"  Applied: {applied}")
            print(f"  Skipped: {skipped}")
            print(f"  Status: {status}")
            
            if platform_name != "foundit":
                print(f"\n--- Waiting 5 seconds before next platform ---")
                await asyncio.sleep(5)
                
        except Exception as e:
            logger.error(f"Error running {platform_name}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print(">>> FINAL SUMMARY <<<")
    print("=" * 70)
    print(f"Total Applied: {total_applied}")
    print(f"Total Skipped: {total_skipped}")
    print(f"Platforms Completed: {platforms_completed}/3")
    print("=" * 70)
    
    if total_applied > 0:
        print(f"\nSUCCESS: Applied to {total_applied} jobs across {platforms_completed} platforms!")
    else:
        print(f"\nNOTE: No applications made. Check credentials and logs.")


if __name__ == "__main__":
    asyncio.run(run_all_platforms())