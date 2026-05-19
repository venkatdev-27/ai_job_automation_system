
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path("d:/ai-bot-resumes/job_automation_system")
sys.path.insert(0, str(PROJECT_ROOT))

# Mock environment for host dispatch
os.environ["REDIS_HOST"] = "localhost"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/1"

from tasks.producer_platform_task import run_platform

def trigger_test():
    print("Dispatching test batch: 2 jobs per platform...")
    
    platforms = ["naukri"]
    
    for platform in platforms:
        print(f"Dispatching {platform}...")
        try:
            # We use apply_async to send to the worker.
            # run_platform(self, platform, jobs_per_student, ...)
            # When calling apply_async, we don't pass 'self'.
            result = run_platform.apply_async(
                kwargs={
                    "platform": platform,
                    "jobs_per_student": 2
                }
            )
            print(f"  {platform} task ID: {result.id}")
        except Exception as e:
            print(f"  Failed to dispatch {platform}: {e}")

if __name__ == "__main__":
    trigger_test()
