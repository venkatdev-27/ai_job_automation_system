# Job Automation System - Production Deployment Guide

## Overview

This guide covers deploying the Job Automation System in a production environment on a VPS.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  VPS (Production Server)                                    │
│  ────────────────────────────────────────────────────────    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Docker Containers                                    │   │
│  │                                                       │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │   │
│  │  │  Redis   │  │ AI Eng   │  │ Chrome   │           │   │
│  │  │ (persist)│  │          │  │  CDP     │           │   │
│  │  └──────────┘  └──────────┘  └──────────┘           │   │
│  │                                                       │   │
│  │  ┌───────────────────────────────────────────┐      │   │
│  │  │      Celery Workers                        │      │   │
│  │  │  naukri | linkedin | foundit | producer   │      │   │
│  │  └───────────────────────────────────────────┘      │   │
│  │                                                       │   │
│  │  ┌───────────────────────────────────────────┐      │   │
│  │  │      Node API (Port 5000)                  │      │   │
│  │  └───────────────────────────────────────────┘      │   │
│  │                                                       │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │   │
│  │  │Pro mets │  │ Grafana  │  │cAdvisor │           │   │
│  │  └──────────┘  └──────────┘  └──────────┘           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Requirement | Specification |
|-------------|---------------|
| OS | Ubuntu 22.04 LTS / Debian 12 |
| RAM | 8GB minimum (16GB recommended) |
| CPU | 4 cores minimum |
| Disk | 50GB SSD |
| Docker | Latest stable |
| Domain | Optional (for HTTPS) |

---

## Installation

### Option 1: Fresh VPS (Automated)

```bash
# SSH into your VPS
ssh root@your-vps-ip

# Run the setup script
wget -O setup-vps.sh <url-to-script> && chmod +x setup-vps.sh && ./setup-vps.sh

# Edit environment file
nano /opt/job-automation/.env.production

# Start services
systemctl start job-automation
```

### Option 2: Manual Installation

```bash
# 1. Install Docker
apt update && apt install -y docker.io docker-compose

# 2. Create directories
mkdir -p /opt/job-automation/{backups,logs,chrome_profile}

# 3. Copy project files
scp -r job_automation_system user@your-vps:/opt/

# 4. Create environment file
cp .env.production.example .env.production
nano .env.production  # Fill in your values

# 5. Start services
cd /opt/job_automation_system
docker-compose -f docker-compose-production.yml up -d
```

---

## Configuration

### Environment Variables (Required)

| Variable | Description | Example |
|----------|-------------|---------|
| `MONGO_URI` | MongoDB Atlas connection string | `mongodb+srv://user:pass@cluster...` |
| `GROQ_API_KEY` | Groq API key for LLM | `gsk_...` |
| `GEMINI_API_KEY` | Google AI API key (optional) | `AIza...` |
| `GRAFANA_PASSWORD` | Grafana admin password | `your-secure-password` |

### Environment Variables (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `DAILY_JOB_LIMIT` | 100 | Max jobs per day |
| `AUTO_STOP_TIME` | 23:59 | Auto-stop time |
| `BEAT_SCHEDULE_TIMES` | 06:00,11:00,17:00,20:00 | Scheduled run times |

---

## Service Management

### Systemd Commands

```bash
# Start service
systemctl start job-automation

# Stop service
systemctl stop job-automation

# Restart service
systemctl restart job-automation

# Check status
systemctl status job-automation

# View logs
journalctl -u job-automation -f

# Enable on boot
systemctl enable job-automation
```

### Manual Docker Commands

```bash
# Start all containers
docker-compose -f docker-compose-production.yml up -d

# Stop all containers
docker-compose -f docker-compose-production.yml down

# View logs
docker-compose -f docker-compose-production.yml logs -f

# View specific container
docker-compose -f docker-compose-production.yml logs -f node-api

# Restart specific container
docker-compose -f docker-compose-production.yml restart celery-naukri-1
```

---

## Access URLs

| Service | Port | URL |
|---------|------|-----|
| Admin Dashboard | Dev only | `npm run dev` on local |
| Node API | 5000 | `http://your-vps:5000` |
| AI Engine | 8000 | `http://your-vps:8000` |
| Chrome CDP | 3000 | Internal only |
| Redis | 6379 | Internal only |
| Prometheus | 9090 | `http://your-vps:9090` |
| Grafana | 3001 | `http://your-vps:3001` |
| cAdvisor | 8080 | `http://your-vps:8080` |

---

## Monitoring

### Prometheus Alerts

Alerts are configured in `prometheus/alerts.yml`:

- `ContainerDown` - Container not responding for 2 minutes
- `HighJobFailureRate` - Failure rate > 10% over 5 minutes
- `HighMemoryUsage` - Memory usage > 90%
- `HighCPUUsage` - CPU usage > 90%

### Grafana Dashboards

1. **System Overview** - Jobs completed, workers online, resource usage
2. **Platform Distribution** - Jobs by platform (Naukri/LinkedIn/FoundIt)
3. **Infrastructure** - CPU, Memory, Disk metrics

Access Grafana at `http://your-vps:3001` with:
- Username: `admin`
- Password: (from `GRAFANA_PASSWORD` env var)

---

## Scheduled Jobs

Jobs run automatically at configured times (via Celery Beat):

| Time | Platform | Jobs |
|------|----------|------|
| 06:00 | Naukri | 5 per student |
| 11:00 | FoundIt | 5 per student |
| 17:00 | LinkedIn | 5 per student |
| 20:00 | All | 5 per student |

### Modify Schedule

Edit in `.env.production`:
```
BEAT_SCHEDULE_TIMES=06:00,11:00,17:00,20:00
```

Then restart:
```bash
systemctl restart job-automation
```

---

## Backup & Recovery

### Automated Backup

Add to crontab:
```bash
crontab -e
# Add line:
0 2 * * * /opt/job-automation/scripts/backup.sh
```

### Manual Backup
```bash
./scripts/backup.sh
```

### Recovery

```bash
# 1. Stop services
systemctl stop job-automation

# 2. Restore Redis data
docker run --rm \
    -v job_automation_redis_data:/data \
    -v /opt/job-automation/backups:/backup \
    alpine:latest \
    tar -xzf /backup/redis-YYYYMMDD.tar.gz -C /data

# 3. Start services
systemctl start job-automation
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose -f docker-compose-production.yml logs [container-name]

# Common issues:
# - Missing environment variables
# - Port already in use
# - Volume permissions
```

### Dashboard Shows "Connection Refused"

```bash
# Check Node API is running
curl http://localhost:5000/api/system/health

# Check containers
docker ps

# Restart Node API
docker-compose -f docker-compose-production.yml restart node-api
```

### Jobs Not Running

```bash
# Check Celery workers
docker-compose -f docker-compose-production.yml logs celery-naukri-1

# Check Redis
docker exec job-automation-redis redis-cli ping

# Check Beat scheduler
docker-compose -f docker-compose-production.yml logs celery-beat
```

---

## Security

### Firewall (UFW)

Only expose necessary ports:
```bash
ufw allow 22/tcp     # SSH
ufw allow 5000/tcp   # Node API
ufw allow 3001/tcp   # Grafana
ufw allow 9090/tcp   # Prometheus (optional)
```

### Fail2Ban

Automatically blocks brute-force attempts:
```bash
systemctl status fail2ban
```

### SSL/TLS (Optional)

For HTTPS, use Nginx as reverse proxy:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:5173;
    }

    location /api {
        proxy_pass http://localhost:5000;
    }
}
```

---

## Performance Tuning

### Recommended Resource Limits

| Service | CPU | Memory |
|---------|-----|--------|
| redis | 0.5 | 512M |
| chrome-cdp | 1 | 1G |
| ai-engine | 2 | 4G |
| node-api | 0.5 | 512M |
| celery-naukri | 1 | 2G |
| celery-linkedin | 0.5 | 1G |
| celery-foundit | 1 | 2G |

### Scaling Workers

Add more workers:
```bash
docker-compose -f docker-compose-production.yml up -d --scale celery-naukri=4
```

---

## Support

For issues:
1. Check logs: `docker-compose -f docker-compose-production.yml logs`
2. Check service status: `systemctl status job-automation`
3. Verify environment: `cat .env.production`

---

*Last Updated: May 2026*
