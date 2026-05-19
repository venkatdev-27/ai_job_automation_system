import sys
from pathlib import Path
import os

# Add the project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from celery_app.app import app

def trigger():
    print("Triggering Manual Producer Wave...")
    # Trigger the producer task
    result = app.send_task("tasks.producer_beat_task.run_producer", kwargs={"jobs_per_student": 10})
    print(f"Task submitted! ID: {result.id}")

if __name__ == "__main__":
    trigger()
