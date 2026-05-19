# Job Automation System

## Quick Start (3 Steps)

```
1. Open Docker Desktop (wait 30-60 seconds)

2. Start Admin Dashboard
   cd admin-dashboard
   npm run dev
   Open: http://localhost:5173

3. Click START button on dashboard
   Click RUN NOW to trigger job automation
```

See [QUICK_START.md](QUICK_START.md) for detailed instructions.

---

## System Architecture

```
Admin Dashboard (React)          http://localhost:5173
       ↓
Node API (Docker/Express)        http://localhost:5000
       ↓
┌─────────────────────────────────────────┐
│  Docker Containers                       │
│                                          │
│  ┌────────┐  ┌──────────┐  ┌─────────┐  │
│  │ Redis  │  │ AI Engine│  │ Chrome  │  │
│  └────────┘  └──────────┘  └─────────┘  │
│                                          │
│  ┌─────────────────────────────────┐    │
│  │  Celery Workers                  │    │
│  │  naukri | linkedin | foundit     │    │
│  └─────────────────────────────────┘    │
└──────────────────────────────────────────┘
```

---

## Buttons

| Button | Action |
|--------|--------|
| **START** | Starts all Docker containers (redis, ai-engine, chrome-cdp, node-api, celery workers) |
| **STOP** | Stops workers only (keeps node-api running for dashboard access) |
| **RUN NOW** | Triggers job automation across all platforms |

---

## Files

| File | Description |
|------|-------------|
| `QUICK_START.md` | Detailed 3-step workflow guide |
| `start.bat` | Windows convenience script |
| `job_automation_system/docker-compose-minimal.yml` | Container definitions |
| `admin-dashboard/` | React admin dashboard |

---

## Requirements

- Docker Desktop (running)
- Node.js 18+
- npm

---

## Troubleshooting

See [QUICK_START.md](QUICK_START.md) - Troubleshooting section

---

*For production deployment, see the production deployment plan.*
