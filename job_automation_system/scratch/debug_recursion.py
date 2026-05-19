
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path("d:/ai-bot-resumes/job_automation_system")
sys.path.insert(0, str(PROJECT_ROOT))

# Mock environment
os.environ["REDIS_HOST"] = "localhost"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/1"

from tasks.naukri_task import apply_to_naukri

class MockTask:
    def __init__(self):
        self.request = type('obj', (object,), {'id': 'test-id'})
    def retry(self, *args, **kwargs):
        print("Retry called")
        return Exception("Retry")

# Create instance of the task class
from tasks.naukri_task import NaukriApplyTask
task_inst = NaukriApplyTask()
task_inst.request = type('obj', (object,), {'id': 'test-id'})

print("Running task logic directly...")
try:
    # We call the function which calls BasePlatformTask.run
    # We need to pass task_inst as 'self'
    result = apply_to_naukri(
        task_inst,
        student_id="student_4443c80f",
        job_url="https://www.naukri.com/job-listings-test",
        resume_variant="backend"
    )
    print("Result:", result)
except Exception as e:
    import traceback
    traceback.print_exc()
