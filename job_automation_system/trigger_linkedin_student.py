import sys
from pathlib import Path
import os

# Add the project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from celery_app.app import app

def trigger(student_id):
    print(f"Triggering Manual LINKEDIN Task for {student_id}...")
    # Trigger specifically the linkedin application task
    result = app.send_task(
        "tasks.linkedin_task.apply_to_job", 
        args=[student_id],
        kwargs={
            "resume_variant": "backend",
            "job_batch": [{"url": "manual_trigger"}] * 2
        },
        queue="linkedin"
    )
    print(f"LinkedIn Task submitted! ID: {result.id}")

if __name__ == "__main__":
    student_id = "student_4443c80f"
    if len(sys.argv) > 1:
        student_id = sys.argv[1]
    trigger(student_id)
