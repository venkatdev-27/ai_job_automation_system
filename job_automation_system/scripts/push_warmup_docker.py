import sys
sys.path.insert(0, 'D:/ai-bot-resumes/job_automation_system')

import os
os.environ['PYTHONPATH'] = 'D:/ai-bot-resumes/job_automation_system'

# Point to docker redis
os.environ['REDIS_HOST'] = 'localhost'
os.environ['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
os.environ['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/1'

from celery_app.app import app

print("=" * 60)
print("PUSHING WARMUP TASK TO CELERY (DOCKER)")
print("=" * 60)

student_id = "student_2b4359c4"

result = app.send_task(
    "tasks.generate_initial_resumes_task.generate_resumes",
    args=[student_id],
    queue="warmup",
    routing_key="warmup"
)

print(f"\nTask pushed to Celery warmup queue!")
print(f"  Student ID: {student_id}")
print(f"  Task ID: {result.id}")
print(f"  Queue: warmup")
print(f"\nMonitor: docker logs -f celery-warmup")
print("=" * 60)