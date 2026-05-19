import sys
from pathlib import Path
import os

# Add the project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from celery_app.app import app

def trigger():
    print("Triggering Manual NAUKRI Platform Wave...")
    # Trigger specifically the naukri platform task
    result = app.send_task("tasks.producer_platform_task.run_naukri", kwargs={"jobs_per_student": 10})
    print(f"Naukri Task submitted! ID: {result.id}")

if __name__ == "__main__":
    trigger()
