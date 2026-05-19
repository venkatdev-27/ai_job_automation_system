import os
from dotenv import load_dotenv
import pymongo
from celery import Celery

load_dotenv('.env')

# Clear MongoDB
c = pymongo.MongoClient(os.getenv('MONGO_URI'))
db = c[os.getenv('MONGO_DB', 'ai_bot_resumes')]
db.job_applications.delete_many({'student_id': 'student_2b4359c4'})
db.task_executions.delete_many({'student_id': 'student_2b4359c4'})
db.students.update_one({'student_id': 'student_2b4359c4'}, {'$unset': {'platform_cooldowns.linkedin': ''}})

print('Cleared remote MongoDB for student_2b4359c4!')

# Clear redis locks
import redis
broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
if 'redis://redis:' in broker_url:
    broker_url = broker_url.replace('redis://redis:', 'redis://localhost:')
elif 'redis:6379' in broker_url and 'localhost' not in broker_url:
    broker_url = broker_url.replace('redis:', 'localhost:')

r = redis.Redis.from_url(broker_url)
for key in r.scan_iter("*lock*"):
    r.delete(key)
print(f'Cleared Redis locks via {broker_url}!')

# Push Celery task
broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
if 'redis://redis:' in broker_url:
    broker_url = broker_url.replace('redis://redis:', 'redis://localhost:')
elif 'redis:6379' in broker_url and 'localhost' not in broker_url:
    # Handle cases where it's just 'redis:6379'
    broker_url = broker_url.replace('redis:', 'localhost:')
celery_app = Celery('job_automation', broker=broker_url)
celery_app.send_task(
    'tasks.linkedin_task.apply_to_job',
    kwargs={
        'student_id': 'student_2b4359c4',
        'platform': 'linkedin',
        'job_url': 'https://www.linkedin.com/jobs/search/?keywords=Java+developer&location=India&f_TPR=r604800&f_WT=2&f_E=1&start=0',
        'resume_variant': 'backend',
        'batch_size': 3
    },
    queue='linkedin'
)
print('Successfully queued LinkedIn task for student_2b4359c4!')
