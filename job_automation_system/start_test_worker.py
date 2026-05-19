import os
import subprocess

os.environ['REDIS_HOST'] = 'localhost'
os.environ['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'

# Start single test worker
cmd = [
    'python', '-m', 'celery', 
    '-A', 'celery_app.app', 
    'worker', 
    '-Q', 'naukri', 
    '-c', '2',
    '--loglevel=info',
    '--hostname=naukri-test'
]

print("Starting test worker...")
proc = subprocess.Popen(cmd, cwd='D:/ai-bot-resumes/job_automation_system')
print(f"Worker started with PID: {proc.pid}")
print("Check the output below...")