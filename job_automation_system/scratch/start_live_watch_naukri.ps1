param(
    [string]$JobUrl = "https://www.naukri.com/python-developer-jobs-in-india?k=python%20developer&l=india"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Host "[1/4] Ensuring Redis is up..." -ForegroundColor Cyan
docker compose up -d redis | Out-Host

Write-Host "[2/4] Stopping Docker Naukri workers (so local worker gets the task)..." -ForegroundColor Cyan
docker compose stop celery-naukri-1 celery-naukri-2 celery-naukri-3 | Out-Host

Write-Host "[3/4] Restarting LOCAL visible worker..." -ForegroundColor Cyan
# Stop older local naukri workers so new code is loaded.
$oldWorkers = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match "celery -A celery_app.app worker" -and $_.CommandLine -match "-Q naukri" }
foreach ($p in $oldWorkers) {
    try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
}

$workerCommand = @"
Set-Location '$projectRoot'
`$env:REDIS_HOST='localhost'
`$env:REDIS_PORT='6379'
`$env:CELERY_BROKER_URL='redis://localhost:6379/0'
`$env:CELERY_RESULT_BACKEND='redis://localhost:6379/1'
`$env:PLAYWRIGHT_HEADLESS='false'
`$env:PYTHONUTF8='1'
python -m celery -A celery_app.app worker -Q naukri --pool=solo -c 1 --loglevel=info --hostname=naukri-live@%h
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $workerCommand | Out-Null

Start-Sleep -Seconds 6

Write-Host "[4/4] Queueing one live-watch task..." -ForegroundColor Cyan
$env:TEST_CELERY_BROKER_URL = "redis://localhost:6379/0"
$env:TEST_CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
$env:YAMUNA_NAUKRI_JOB_URL = $JobUrl
$env:YAMUNA_NAUKRI_UNIQUE = "1"
python tests/test_yamuna_naukri.py

Write-Host "" 
Write-Host "Live watch mode started." -ForegroundColor Green
Write-Host "A Chrome window should open from the LOCAL worker window." -ForegroundColor Green
Write-Host ""
Write-Host "After watching, you can restore Docker workers with:" -ForegroundColor Yellow
Write-Host "docker compose up -d celery-naukri-1 celery-naukri-2 celery-naukri-3" -ForegroundColor Yellow
