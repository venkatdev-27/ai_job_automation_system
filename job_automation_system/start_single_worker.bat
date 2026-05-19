@echo off
REM Start single test worker with proper PYTHONPATH and Redis settings
cd /d d:\ai-bot-resumes\job_automation_system
set PYTHONPATH=d:\ai-bot-resumes\job_automation_system;d:\ai-bot-resumes\job_automation_system\job_automation_system
set REDIS_HOST=localhost
set CELERY_BROKER_URL=redis://localhost:6379/0
set CELERY_RESULT_BACKEND=redis://localhost:6379/1
python -m celery -A celery_app.app worker -Q naukri -c 2 --loglevel=info --hostname=naukri-test