@echo off
REM Worker with eventlet pool (fixes Python 3.13 compatibility)
cd /d d:\ai-bot-resumes\job_automation_system
set PYTHONPATH=d:\ai-bot-resumes\job_automation_system
set REDIS_HOST=localhost
set CELERY_BROKER_URL=redis://localhost:6379/0
set CELERY_RESULT_BACKEND=redis://localhost:6379/1
python -m celery -A celery_app.app worker -Q warmup,naukri,linkedin,foundit,producer -c 2 --pool=eventlet --loglevel=info --hostname=host-worker-1