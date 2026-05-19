@echo off
REM Worker with solo pool (no process pool, single thread)
cd /d d:\ai-bot-resumes\job_automation_system
set PYTHONPATH=d:\ai-bot-resumes\job_automation_system
set REDIS_HOST=localhost
set CELERY_BROKER_URL=redis://localhost:6379/0
set CELERY_RESULT_BACKEND=redis://localhost:6379/1
python -m celery -A celery_app.app worker -Q warmup,naukri,linkedin,foundit,producer -c 1 --pool=solo --loglevel=debug --hostname=host-worker-1 2>&1