@echo off
REM ============================================================
REM Job Automation - Stop All Workers
REM ============================================================
echo ========================================
echo   Stopping All Workers
echo ========================================

taskkill /F /FI "WINDOWTITLE eq Celery-*" 2>nul
taskkill /F /FI "WINDOWTITLE eq Celery-*" 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq Celery-*" 2>nul

echo Done!
timeout /t 2 /nobreak >nul