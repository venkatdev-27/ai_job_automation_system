@echo off
REM ============================================================
REM Job Automation System - Worker Startup Script
REM ============================================================
REM This script starts all worker processes on Windows host

setlocal enabledelayedexpansion

echo ========================================
echo   Job Automation Workers - Startup
echo ========================================
echo.

REM Set working directory and PYTHONPATH
set WORK_DIR=d:\ai-bot-resumes\job_automation_system
cd /d %WORK_DIR%
set PYTHONPATH=%WORK_DIR%

REM Use host-based environment
set REDIS_HOST=localhost
set CELERY_BROKER_URL=redis://localhost:6379/0
set CELERY_RESULT_BACKEND=redis://localhost:6379/1

echo [*] Setting up environment...
echo.

REM ============================================================
echo [*] Starting Naukri Workers (3 workers x 3 concurrency = 9 parallel)
REM ============================================================

echo [*] Starting Naukri Worker 1...
start "Celery-Naukri-1" cmd /k "cd /d %WORK_DIR% && python -m celery -A celery_app.app worker -Q naukri -c 3 -O fair --loglevel=info --hostname=naukri-1"
timeout /t 3 /nobreak >nul

echo [*] Starting Naukri Worker 2...
start "Celery-Naukri-2" cmd /k "cd /d %WORK_DIR% && python -m celery -A celery_app.app worker -Q naukri -c 3 -O fair --loglevel=info --hostname=naukri-2"
timeout /t 3 /nobreak >nul

echo [*] Starting Naukri Worker 3...
start "Celery-Naukri-3" cmd /k "cd /d %WORK_DIR% && python -m celery -A celery_app.app worker -Q naukri -c 3 -O fair --loglevel=info --hostname=naukri-3"
timeout /t 3 /nobreak >nul

echo.

REM ============================================================
echo [*] Starting LinkedIn Workers (3 workers x 2 concurrency = 6 parallel)
REM ============================================================

echo [*] Starting LinkedIn Worker 1...
start "Celery-LinkedIn-1" cmd /k "cd /d %WORK_DIR% && python -m celery -A celery_app.app worker -Q linkedin -c 2 -O fair --loglevel=info --hostname=linkedin-1"
timeout /t 3 /nobreak >nul

echo [*] Starting LinkedIn Worker 2...
start "Celery-LinkedIn-2" cmd /k "cd /d %WORK_DIR% && python -m celery -A celery_app.app worker -Q linkedin -c 2 -O fair --loglevel=info --hostname=linkedin-2"
timeout /t 3 /nobreak >nul

echo [*] Starting LinkedIn Worker 3...
start "Celery-LinkedIn-3" cmd /k "cd /d %WORK_DIR% && python -m celery -A celery_app.app worker -Q linkedin -c 2 -O fair --loglevel=info --hostname=linkedin-3"
timeout /t 3 /nobreak >nul

echo.

REM ============================================================
echo [*] Starting FoundIt Workers (2 workers x 3 concurrency = 6 parallel)
REM ============================================================

echo [*] Starting FoundIt Worker 1...
start "Celery-FoundIt-1" cmd /k "cd /d %WORK_DIR% && python -m celery -A celery_app.app worker -Q foundit -c 3 -O fair --loglevel=info --hostname=foundit-1"
timeout /t 3 /nobreak >nul

echo [*] Starting FoundIt Worker 2...
start "Celery-FoundIt-2" cmd /k "cd /d %WORK_DIR% && python -m celery -A celery_app.app worker -Q foundit -c 3 -O fair --loglevel=info --hostname=foundit-2"
timeout /t 3 /nobreak >nul

echo.

echo ========================================
echo   Workers Started Successfully!
echo ========================================
echo.
echo Summary:
echo   - Naukri: 3 workers (9 parallel)
echo   - LinkedIn: 3 workers (6 parallel)
echo   - FoundIt: 2 workers (6 parallel)
echo   - Total: 8 workers (21 parallel)
echo.
echo Keep these windows open while running!
echo.
pause