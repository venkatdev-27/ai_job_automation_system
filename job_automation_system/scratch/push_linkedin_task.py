import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv('.env')

broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
if 'redis://redis:' in broker_url:
    broker_url = broker_url.replace('redis://redis:', 'redis://localhost:')

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
print('Task pushed!')
