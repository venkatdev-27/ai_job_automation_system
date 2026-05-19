@echo off
echo ==========================================
echo STARTING JOB AUTOMATION SYSTEM
echo ==========================================

:: 1. Check if Docker is running
tasklist /FI "IMAGENAME eq Docker Desktop.exe" 2>NUL | find /I /N "Docker Desktop.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [INFO] Docker Desktop is already running.
) else (
    echo [INFO] Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    
    echo [INFO] Waiting for Docker to initialize...
    :wait_docker
    docker info >nul 2>&1
    if errorlevel 1 (
        timeout /t 5 >nul
        goto wait_docker
    )
    echo [OK] Docker is ready.
)

:: 2. Navigate to project directory
cd /d "D:\ai-bot-resumes\job_automation_system"

:: 3. Start the production stack
echo [INFO] Starting automation containers...
docker-compose -f docker-compose-production.yml up -d --remove-orphans

echo ==========================================
echo SYSTEM STARTED SUCCESSFULLY
echo ==========================================
pause
