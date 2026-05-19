import sys
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')

import os
os.environ['PYTHONPATH'] = 'D:/ai-bot-resumes/job_automation_system'

from celery_app.app import app

print("=" * 60)
print("PUSHING WARMUP TASK TO CELERY")
print("=" * 60)

# Push warmup task for Phani Krishna
student_id = "student_2b4359c4"

result = app.send_task(
    "tasks.generate_initial_resumes_task.generate_resumes",
    args=[student_id],
    queue="warmup",
    routing_key="warmup"
)

print(f"\n✓ Task pushed successfully!")
print(f"  Student ID: {student_id}")
print(f"  Task ID: {result.id}")
print(f"  Queue: warmup")
print(f"\nMonitor with: celery -A tasks inspect active")
print("=" * 60)