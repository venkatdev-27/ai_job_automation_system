@echo off
REM Worker with solo pool - disable multiprocessing logging
cd /d d:\ai-bot-resumes\job_automation_system
set PYTHONPATH=d:\ai-bot-resumes\job_automation_system
set REDIS_HOST=localhost
set CELERY_BROKER_URL=redis://localhost:6379/0
set CELERY_RESULT_BACKEND=redis://localhost:6379/1
set PYTHONWARNINGS=ignore
python -m celery -A celery_app.app worker -Q warmup,naukri,linkedin,foundit,producer -c 1 --pool=solo --loglevel=info --hostname=host-worker-1