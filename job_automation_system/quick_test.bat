@echo off
REM Quick single worker test - just one window
cd /d d:\ai-bot-resumes\job_automation_system
set REDIS_HOST=localhost
set CELERY_BROKER_URL=redis://localhost:6379/0
echo Starting test worker...
python -m celery -A celery_app.app worker -Q naukri -c 2 --loglevel=info --hostname=naukri-test