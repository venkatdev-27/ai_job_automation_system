param(
    [string]$JobUrl = "https://www.linkedin.com/jobs/search/?keywords=python%20developer&location=India&f_AL=true"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Host "[1/4] Ensuring Redis is up..." -ForegroundColor Cyan
docker compose up -d redis | Out-Host

Write-Host "[2/4] Stopping Docker LinkedIn worker (so local worker gets the task)..." -ForegroundColor Cyan
docker compose stop celery-linkedin-1 | Out-Host

Write-Host "[3/4] Restarting LOCAL visible LinkedIn worker..." -ForegroundColor Cyan
# Stop older local linkedin workers so new code is loaded.
$oldWorkers = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match "celery -A celery_app.app worker" -and $_.CommandLine -match "-Q linkedin" }
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
python -m celery -A celery_app.app worker -Q linkedin --pool=solo -c 1 --loglevel=info --hostname=linkedin-live@%h
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $workerCommand | Out-Null

Start-Sleep -Seconds 6

Write-Host "[4/4] Queueing one live-watch LinkedIn task..." -ForegroundColor Cyan
$env:TEST_CELERY_BROKER_URL = "redis://localhost:6379/0"
$env:TEST_CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
$env:YAMUNA_LINKEDIN_JOB_URL = $JobUrl
$env:YAMUNA_LINKEDIN_UNIQUE = "1"
python tests/test_yamuna_linkedin.py

Write-Host ""
Write-Host "Live watch mode started." -ForegroundColor Green
Write-Host "A Chrome window should open from the LOCAL LinkedIn worker window." -ForegroundColor Green
Write-Host ""
Write-Host "After watching, you can restore Docker worker with:" -ForegroundColor Yellow
Write-Host "docker compose up -d celery-linkedin-1" -ForegroundColor Yellow
