#!/bin/bash
# ==============================================================================
# Stuck Job Reaper - Job Automation System
# ==============================================================================
# Finds and revives Celery tasks that have been PENDING for too long.
# Run via cron: */5 * * * * /opt/job-automation/scripts/reap_stuck_jobs.sh
#
# Why: If a worker dies mid-task, the task stays PENDING forever.
# This script detects stale tasks and revokes + requeues them.
# ==============================================================================

set -e

CELERY_INSPECT="celery -A celery_app.app inspect"
STUCK_THRESHOLD=600
RESULTS_CLEANED=0
TASKS_REAPED=0
WARNINGS=0

echo "[$(date)] Stuck job reaper started..."

# --- Find tasks that have been in PENDING state for too long ---
STUCK_TASKS=$(celery -A celery_app.app inspect active 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    stuck = []
    for worker, tasks in data.items():
        for task in (tasks or []):
            t = task.get('time', 0)
            import time
            elapsed = time.time() - t if t else 0
            if elapsed > $STUCK_THRESHOLD:
                stuck.append({
                    'worker': worker,
                    'id': task.get('id'),
                    'name': task.get('name'),
                    'elapsed': int(elapsed),
                })
    for s in stuck:
        print(f\"{s['worker']}|{s['id']}|{s['name']}|{s['elapsed']}\")
except Exception as e:
    print('', file=sys.stderr)
" 2>/dev/null || echo "")

if [ -z "$STUCK_TASKS" ]; then
    echo "[$(date)] No stuck tasks found."
    exit 0
fi

# --- Revoke stuck tasks ---
echo "[$(date)] Found stuck tasks:"
echo "$STUCK_TASKS" | while IFS='|' read -r worker task_id task_name elapsed; do
    if [ -z "$task_id" ]; then
        continue
    fi

    echo "[STUCK] Worker=$worker Task=$task_name ID=$task_id Elapsed=${elapsed}s"

    echo "[REAP] Revoking task: $task_id"
    celery -A celery_app.app revoke "$task_id" --terminate 2>/dev/null || true
    TASKS_REAPED=$((TASKS_REAPED + 1))

    echo "[REAP] Removing result from backend: $task_id"
    redis-cli del "celery_task_meta_$task_id" 2>/dev/null || true
    RESULTS_CLEANED=$((RESULTS_CLEANED + 1))
done

# --- Check for stale results in Redis (tasks that completed but meta wasn't cleaned) ---
echo "[$(date)] Checking for stale task results..."
STALE_RESULTS=$(redis-cli --scan --pattern "celery_task_meta_*" 2>/dev/null | head -50 || echo "")

for key in $STALE_RESULTS; do
    TTL=$(redis-cli ttl "$key" 2>/dev/null || echo "-2")
    if [ "$TTL" -eq -1 ]; then
        echo "[CLEAN] Removing result with no TTL: $key"
        redis-cli del "$key" 2>/dev/null
        RESULTS_CLEANED=$((RESULTS_CLEANED + 1))
    fi
done

# --- Check for dead letter queue buildup ---
echo "[$(date)] Checking dead letter queue..."
DLQ_COUNT=$(celery -A celery_app.app inspect stats 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    total = 0
    for worker, info in data.items():
        for queue, stats in (info.get('pool', {}) or {}).items():
            if 'failed_jobs' in queue:
                total += 1
    print(total)
except:
    print(0)
" 2>/dev/null || echo "0")

if [ "$DLQ_COUNT" -gt 20 ]; then
    echo "[WARN] DLQ has $DLQ_COUNT failed jobs. Check logs."
    WARNINGS=$((WARNINGS + 1))
fi

echo "[$(date)] Reaper complete: tasks_reaped=$TASKS_REAPED, results_cleaned=$RESULTS_CLEANED, warnings=$WARNINGS"

if [ "$TASKS_REAPED" -gt 0 ] || [ "$RESULTS_CLEANED" -gt 0 ]; then
    echo "[$(date)] ALERT: Job reaper performed actions. Check logs above."
fi