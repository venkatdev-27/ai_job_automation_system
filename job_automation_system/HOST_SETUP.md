# Job Automation System - Host-Based Workers Setup

## Files Created

| File | Purpose |
|------|---------|
| `.env.host` | Host environment configuration |
| `run_workers.bat` | Start all 8 workers |
| `setup_auto_start.bat` | Setup Task Scheduler auto-start |
| `stop_workers.bat` | Stop all workers |
| `test_worker.bat` | Test single worker |
| `clear_redis.bat` | Clear Redis data |

---

## Quick Start Guide

### Option 1: Manual Start (No Auto-Start)

1. Make sure Redis is running locally
2. Double-click `run_workers.bat`
3. All 8 workers will start in new windows
4. Keep these windows open while running

### Option 2: Auto-Start on Boot (Recommended)

1. Right-click `setup_auto_start.bat`
2. Select "Run as administrator"
3. All workers will start automatically on Windows boot

### Testing Single Worker

1. Double-click `test_worker.bat`
2. Watch for "Connected to redis" message
3. If successful, you're ready!

---

## Worker Configuration

| Platform | Workers | Concurrency | Total Parallel |
|----------|---------|--------------|---------------|
| Naukri | 3 | 3 | 9 |
| LinkedIn | 3 | 2 | 6 |
| FoundIt | 2 | 3 | 6 |
| **Total** | **8** | - | **21** |

---

## Troubleshooting

### Redis Connection Failed
- Make sure Redis is running locally
- Check port 6379 is not blocked

### Workers Not Starting
- Check Python is in PATH: `python --version`
- Check you're in the right directory

### Auto-Start Not Working
- Run `setup_auto_start.bat` as Administrator
- Check Task Scheduler: `taskschd.msc`

---

## Production Usage

1. Run `setup_auto_start.bat` as Administrator (one time)
2. Workers will auto-start on Windows boot
3. Monitor via API: http://localhost:5000
4. Dashboard: http://localhost:5174

---

## Stop Workers

Double-click `stop_workers.bat` to stop all workers.

---

## Migration Complete!