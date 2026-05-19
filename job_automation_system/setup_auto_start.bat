@echo off
REM ============================================================
REM Job Automation - Auto-Start Setup via Task Scheduler
REM ============================================================
REM Run this script as Administrator to set up auto-start on Windows boot

echo ========================================
echo   Job Automation - Auto-Start Setup
echo ========================================
echo.

REM Check for administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Please run as Administrator!
    echo    Right-click on this file and select "Run as administrator"
    pause
    exit /b 1
)

echo [*] Setting up auto-start tasks...

REM ============================================================
REM Naukri Workers Auto-Start
REM ============================================================

echo [*] Creating Naukri-1 auto-start task...
schtasks /create /tn "JobAutomation-Naukri-1" /tr "cmd /c cd /d d:\ai-bot-resumes\job_automation_system && python -m celery -A celery_app.app worker -Q naukri -c 3 -O fair --loglevel=info --hostname=naukri-1" /sc onstart /ri 60 /f >nul 2>&1

echo [*] Creating Naukri-2 auto-start task...
schtasks /create /tn "JobAutomation-Naukri-2" /tr "cmd /c cd /d d:\ai-bot-resumes\job_automation_system && python -m celery -A celery_app.app worker -Q naukri -c 3 -O fair --loglevel=info --hostname=naukri-2" /sc onstart /ri 60 /f >nul 2>&1

echo [*] Creating Naukri-3 auto-start task...
schtasks /create /tn "JobAutomation-Naukri-3" /tr "cmd /c cd /d d:\ai-bot-resumes\job_automation_system && python -m celery -A celery_app.app worker -Q naukri -c 3 -O fair --loglevel=info --hostname=naukri-3" /sc onstart /ri 60 /f >nul 2>&1

echo.

REM ============================================================
REM LinkedIn Workers Auto-Start
REM ============================================================

echo [*] Creating LinkedIn-1 auto-start task...
schtasks /create /tn "JobAutomation-LinkedIn-1" /tr "cmd /c cd /d d:\ai-bot-resumes\job_automation_system && python -m celery -A celery_app.app worker -Q linkedin -c 2 -O fair --loglevel=info --hostname=linkedin-1" /sc onstart /ri 60 /f >nul 2>&1

echo [*] Creating LinkedIn-2 auto-start task...
schtasks /create /tn "JobAutomation-LinkedIn-2" /tr "cmd /c cd /d d:\ai-bot-resumes\job_automation_system && python -m celery -A celery_app.app worker -Q linkedin -c 2 -O fair --loglevel=info --hostname=linkedin-2" /sc onstart /ri 60 /f >nul 2>&1

echo [*] Creating LinkedIn-3 auto-start task...
schtasks /create /tn "JobAutomation-LinkedIn-3" /tr "cmd /c cd /d d:\ai-bot-resumes\job_automation_system && python -m celery -A celery_app.app worker -Q linkedin -c 2 -O fair --loglevel=info --hostname=linkedin-3" /sc onstart /ri 60 /f >nul 2>&1

echo.

REM ============================================================
REM FoundIt Workers Auto-Start
REM ============================================================

echo [*] Creating FoundIt-1 auto-start task...
schtasks /create /tn "JobAutomation-FoundIt-1" /tr "cmd /c cd /d d:\ai-bot-resumes\job_automation_system && python -m celery -A celery_app.app worker -Q foundit -c 3 -O fair --loglevel=info --hostname=foundit-1" /sc onstart /ri 60 /f >nul 2>&1

echo [*] Creating FoundIt-2 auto-start task...
schtasks /create /tn "JobAutomation-FoundIt-2" /tr "cmd /c cd /d d:\ai-bot-resumes\job_automation_system && python -m celery -A celery_app.app worker -Q foundit -c 3 -O fair --loglevel=info --hostname=foundit-2" /sc onstart /ri 60 /f >nul 2>&1

echo.

REM ============================================================
REM Producer Worker Auto-Start
REM ============================================================

echo [*] Creating Producer auto-start task...
schtasks /create /tn "JobAutomation-Producer" /tr "cmd /c cd /d d:\ai-bot-resumes\job_automation_system && python -m celery -A celery_app.app worker -Q producer -c 1 -O fair --loglevel=info --hostname=producer-1" /sc onstart /ri 60 /f >nul 2>&1

echo.

echo ========================================
echo   Auto-Start Setup Complete!
echo ========================================
echo.
echo Tasks created:
echo   - Naukri: 3 workers
echo   - LinkedIn: 3 workers
echo   - FoundIt: 2 workers
echo   - Producer: 1 worker
echo   - Total: 9 workers
echo.
echo All workers will start automatically on Windows boot!
echo.

REM Show created tasks
echo [*] Verifying tasks...
echo.
schtasks /query /fo list | findstr "JobAutomation"
echo.

pause