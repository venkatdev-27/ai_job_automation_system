#!/bin/bash
# ==============================================================================
# Job Automation System - Backup Script
# ==============================================================================
# Automated backup for Redis data
#
# Usage:
#   ./backup.sh              # Manual backup
#   (Add to cron for automated backups)
#   0 2 * * * /opt/job-automation/backup.sh
# ==============================================================================

set -e

# Configuration
BACKUP_DIR="/opt/job-automation/backups"
DATE=$(date +%Y%m%d)
RETENTION_DAYS=7

# Ensure backup directory exists
mkdir -p $BACKUP_DIR

echo "[$(date)] Backup started..."

# Backup Redis data
echo "[$(date)] Backing up Redis data..."
if docker volume ls -q | grep -q "job_automation_redis_data"; then
    docker run --rm \
        -v job_automation_redis_data:/data \
        -v $BACKUP_DIR:/backup \
        alpine:latest \
        tar -czf /backup/redis-$DATE.tar.gz -C /data . 2>/dev/null

    if [ -f "$BACKUP_DIR/redis-$DATE.tar.gz" ]; then
        echo "[$(date)] Redis backup created: $BACKUP_DIR/redis-$DATE.tar.gz"
    else
        echo "[$(date)] ERROR: Redis backup failed"
    fi
else
    echo "[$(date)] WARNING: Redis volume not found"
fi

# Clean old backups (keep 7 days)
echo "[$(date)] Cleaning old backups (keeping $RETENTION_DAYS days)..."
find $BACKUP_DIR -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "[$(date)] Backup completed!"
echo ""
echo "Available backups:"
ls -lh $BACKUP_DIR/*.tar.gz 2>/dev/null || echo "  No backups found"
