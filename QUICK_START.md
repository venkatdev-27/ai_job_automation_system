# Job Automation System - Quick Start Guide

## Your 3-Step Workflow

This guide explains how to run the Job Automation System with just 3 steps.

---

## Prerequisites

1. **Docker Desktop** installed and running
2. **Node.js** (v18+) installed
3. **npm** (comes with Node.js)

---

## Step 1: Start Docker Desktop

```
1. Open Docker Desktop application
2. Wait 30-60 seconds for Docker to fully start
3. Verify: Docker whale icon in system tray (no red error indicator)
```

**Quick Test**: Open terminal and run:
```bash
docker info
```
If you see "Server Version" output, Docker is ready.

---

## Step 2: Start Admin Dashboard

```bash
# Terminal 1: Start the React dashboard
cd D:\ai-bot-resumes\admin-dashboard
npm run dev
```

```
Expected output:
  VITE v8.0.1  ready in 200 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.168.x.x:5173/

  API connected: http://localhost:5000
```

Open your browser: **http://localhost:5173**

---

## Step 3: Click START Button

```
On the admin dashboard:
1. Click the "START" button (red/green toggle)
2. Wait 15-20 seconds for containers to start
3. Status changes from "Stopped" to "Ready"
```

### What Happens When You Click START:

| Container | Purpose | Status |
|-----------|---------|--------|
| redis | Message broker (Celery) | ✅ Starting |
| chrome-cdp | Browser automation | ✅ Starting |
| ai-engine | AI resume generation | ✅ Starting |
| node-api | REST API server | ✅ Starting |
| celery-naukri-1 | Naukri job applications | ✅ Starting |
| celery-naukri-2 | Naukri job applications | ✅ Starting |
| celery-linkedin-1 | LinkedIn applications | ✅ Starting |
| celery-linkedin-2 | LinkedIn applications | ✅ Starting |
| celery-foundit-1 | FoundIt applications | ✅ Starting |
| celery-foundit-2 | FoundIt applications | ✅ Starting |
| celery-producer | Job producer | ✅ Starting |
| celery-beat | Scheduled jobs | ✅ Starting |

---

## Running Jobs

### Click "RUN NOW" Button

```
1. Ensure START button is ON (green)
2. Click "RUN NOW" button
3. Status changes to "Running"
4. Jobs execute across all platforms
```

### Stopping Jobs

```
1. Click "STOP" button
2. Workers stop (Node API stays running)
3. Dashboard remains accessible
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  YOUR LAPTOP                                               │
│  ────────────────────────────────────────────────────────  │
│                                                             │
│  ┌─────────────────┐                                       │
│  │ Admin Dashboard │ (localhost:5173)                     │
│  │   (React)       │                                       │
│  └────────┬────────┘                                       │
│           │                                                 │
│           │ axios                                           │
│           ▼                                                 │
│  ┌─────────────────┐                                       │
│  │  Node API       │ (localhost:5000)                      │
│  │  (Docker)       │                                       │
│  └────────┬────────┘                                       │
│           │                                                 │
│           │ REST API                                        │
│           ▼                                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  DOCKER CONTAINERS (via docker-compose)              │   │
│  │                                                      │   │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐             │   │
│  │  │ Redis   │  │ AI Eng  │  │ Chrome   │             │   │
│  │  │         │  │         │  │ CDP      │             │   │
│  │  └────┬────┘  └────┬─────┘  └────┬─────┘             │   │
│  │       │            │            │                     │   │
│  │  ┌────┴────────────┴────────────┴────┐               │   │
│  │  │     Celery Workers                │               │   │
│  │  │  naukri │ linkedin │ foundit      │               │   │
│  │  └─────────────────────────────────┘               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### "Connection refused" on Dashboard

**Cause**: Node API not running (START wasn't clicked)

**Fix**:
```bash
# Click START button on dashboard
# OR manually check containers:
docker ps
```

### Docker Desktop not responding

**Fix**:
1. Right-click Docker icon in tray
2. Restart Docker Desktop
3. Wait 60 seconds
4. Try again

### START button fails

**Cause**: Docker not running or permission issue

**Fix**:
```bash
# Verify Docker
docker info

# Check containers
docker-compose -p automation -f docker-compose-minimal.yml ps
```

---

## Quick Commands Reference

| Action | Command |
|--------|---------|
| View running containers | `docker ps` |
| View all containers | `docker ps -a` |
| View logs | `docker-compose -p automation -f docker-compose-minimal.yml logs -f` |
| Stop all containers | `docker-compose -p automation -f docker-compose-minimal.yml down` |
| Restart containers | Click START again |

---

## File Locations

| Component | Path |
|-----------|------|
| Admin Dashboard | `D:\ai-bot-resumes\admin-dashboard` |
| Node API | `D:\ai-bot-resumes\job_automation_system\node-api` |
| Docker Compose | `D:\ai-bot-resumes\job_automation_system\docker-compose-minimal.yml` |
| Celery Workers | `D:\ai-bot-resumes\job_automation_system` |
| AI Engine | `D:\ai-bot-resumes\ai_engine` |

---

## Support

If you encounter issues:

1. **Check Docker Desktop** is running
2. **Click START** on dashboard
3. **Wait 15-20 seconds** for containers to initialize
4. **Check browser console** for errors (F12 → Console)

---

*Last Updated: May 2026*
