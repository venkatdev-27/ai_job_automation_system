
import sys
import os
from pathlib import Path
import unittest.mock as mock

# Add project root to path
PROJECT_ROOT = Path("d:/ai-bot-resumes/job_automation_system")
sys.path.insert(0, str(PROJECT_ROOT))

# Mock environment
os.environ["REDIS_HOST"] = "localhost"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/1"

from tasks.naukri_task import NaukriApplyTask, apply_to_naukri

def test_recursion():
    print("Initializing task instance...")
    task_inst = NaukriApplyTask()
    
    # Mock request
    mock_request = mock.MagicMock()
    mock_request.id = "test-task-id-12345"
    
    # In Celery Task, request is a property. We can use patch to mock it.
    with mock.patch.object(NaukriApplyTask, 'request', new_callable=mock.PropertyMock) as mock_req_prop:
        mock_req_prop.return_value = mock_request
        
        print("Running apply_to_naukri(task_inst, ...)")
        try:
            # Use very short timeouts/limits to avoid real browser launch if possible
            # But here we want to see if it even GETS to the logic
            result = apply_to_naukri.run(
                task_inst,
                student_id="student_4443c80f",
                job_url="https://www.naukri.com/job-listings-test",
                resume_variant="backend"
            )
            print("Success! Result:", result)
        except Exception as e:
            print("\nCAUGHT EXCEPTION:")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_recursion()
