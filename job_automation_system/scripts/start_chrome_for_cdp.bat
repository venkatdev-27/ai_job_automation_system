@echo off
REM ==============================================
REM Start Chrome with CDP for Docker connection
REM ==============================================
REM Run this BEFORE starting Docker containers
REM ==============================================

setlocal enabledelayedexpansion

echo.
echo ==============================================
echo Starting Chrome with CDP on 0.0.0.0:9222
echo ==============================================

REM Find Chrome installation
set CHROME_PATH=

REM Check default locations
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    set CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
) else (
    REM Try using where command
    for /f "delims=" %%i in ('where chrome 2^>nul') do (
        set CHROME_PATH=%%i
        goto :found_chrome
    )
)

:found_chrome
if defined CHROME_PATH (
    echo Found Chrome: !CHROME_PATH!
) else (
    echo ERROR: Chrome not found. Please install Google Chrome.
    pause
    exit /b 1
)

REM Get host IP address
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do set HOST_IP=%%a
set HOST_IP=%HOST_IP: =%
echo Host IP: %HOST_IP%

REM Kill existing chrome
taskkill /F /IM chrome.exe 2>nul
timeout /t 2 /nobreak >nul

REM Start Chrome with CDP bound to all interfaces
start "" "!CHROME_PATH!" ^
    --remote-debugging-port=9222 ^
    --remote-debugging-address=0.0.0.0 ^
    --user-data-dir="%TEMP%\chrome-cdp-profile" ^
    --no-first-run ^
    --no-default-browser-check ^
    --disable-extensions ^
    --disable-sync ^
    --disable-translate ^
    --metrics-recording-only ^
    --disable-logging ^
    --ignore-certificate-errors ^
    https://www.naukri.com

timeout /t 3 /nobreak >nul

echo.
echo Chrome started with CDP!
echo.
echo Add these to your .env file or docker-compose:
echo   CDP_URL=http://%HOST_IP%:9222
echo   USE_CDP=true
echo.
echo To test: curl http://%HOST_IP%:9222/json/version
echo.
pause