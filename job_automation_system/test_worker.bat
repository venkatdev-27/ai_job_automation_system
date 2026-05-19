@echo off
REM ============================================================
REM Quick Test - Single Worker Test
REM ============================================================
echo ========================================
echo   Testing Single Worker
echo ========================================

cd /d d:\ai-bot-resumes\job_automation_system

set REDIS_HOST=localhost
set CELERY_BROKER_URL=redis://localhost:6379/0

echo [*] Testing single Naukri worker...
start "Worker-Test" cmd /k "cd /d d:\ai-bot-resumes\job_automation_system && python -m celery -A celery_app.app worker -Q naukri -c 1 --loglevel=info --hostname=naukri-test"

echo.
echo Worker started in new window!
echo Check if it connects to Redis successfully.
echo.
pause