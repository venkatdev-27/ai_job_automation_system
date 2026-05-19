@echo off
REM ============================================================================
REM Job Automation System - Quick Start Script
REM ============================================================================
REM This script checks prerequisites and provides quick commands
REM ============================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%job_automation_system"
set "DASHBOARD_DIR=%SCRIPT_DIR%admin-dashboard"

:menu
cls
echo.
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║       JOB AUTOMATION SYSTEM - QUICK START                      ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.
echo  Your 3-Step Workflow:
echo  ─────────────────────────────────────────────────────────────────
echo.
echo   Step 1: Open Docker Desktop (wait 30-60 seconds)
echo.
echo   Step 2: Press [D] - Start Admin Dashboard
echo.
echo   Step 3: Press [S] - Open Dashboard, then click START button
echo.
echo  ─────────────────────────────────────────────────────────────────
echo.
echo  Troubleshooting:
echo  ─────────────────────────────────────────────────────────────────
echo.
echo   [1] Check if Docker is running
echo   [2] Check if containers are running
echo   [3] View container logs
echo   [4] Stop all containers
echo   [5] Restart all containers
echo.
echo  ─────────────────────────────────────────────────────────────────
echo.
echo   [Q] Quit
echo.
echo  ═══════════════════════════════════════════════════════════════════
echo.
set /p "choice=Enter your choice: "

if /i "%choice%"=="d" goto start_dashboard
if /i "%choice%"=="s" goto open_dashboard
if /i "%choice%"=="1" goto check_docker
if /i "%choice%"=="2" goto check_containers
if /i "%choice%"=="3" goto view_logs
if /i "%choice%"=="4" goto stop_containers
if /i "%choice%"=="5" goto restart_containers
if /i "%choice%"=="q" goto end

goto menu

:start_dashboard
cls
echo.
echo  Starting Admin Dashboard...
echo.
cd /d "%DASHBOARD_DIR%"
start cmd /k "npm run dev"
echo.
echo  Dashboard will open at: http://localhost:5173
echo.
echo  Now click START button on the dashboard!
echo.
pause
goto menu

:open_dashboard
start http://localhost:5173
goto menu

:check_docker
cls
echo.
echo  Checking Docker status...
echo.
docker info >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Docker is not running!
    echo.
    echo  Please:
    echo   1. Open Docker Desktop
    echo   2. Wait 30-60 seconds
    echo   3. Try again
) else (
    echo  OK: Docker is running
    echo.
    docker version --format "Docker Version: {{.Server.Version}}"
)
echo.
pause
goto menu

:check_containers
cls
echo.
echo  Checking container status...
echo.
cd /d "%PROJECT_DIR%"
docker-compose -p automation -f docker-compose-minimal.yml ps
echo.
pause
goto menu

:view_logs
cls
echo.
echo  Viewing container logs (Ctrl+C to exit)...
echo.
cd /d "%PROJECT_DIR%"
docker-compose -p automation -f docker-compose-minimal.yml logs -f
goto menu

:stop_containers
cls
echo.
echo  Stopping all containers...
echo.
cd /d "%PROJECT_DIR%"
docker-compose -p automation -f docker-compose-minimal.yml down
echo.
echo  Done. Containers stopped.
echo.
pause
goto menu

:restart_containers
cls
echo.
echo  Restarting all containers...
echo.
cd /d "%PROJECT_DIR%"
docker-compose -p automation -f docker-compose-minimal.yml down
docker-compose -p automation -f docker-compose-minimal.yml up -d
echo.
echo  Done. All containers started.
echo.
pause
goto menu

:end
cls
echo.
echo  Thank you for using Job Automation System!
echo.
exit /b 0
