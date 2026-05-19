#!/bin/bash
# ==============================================================================
# Orphan Lock Cleaner - Job Automation System
# ==============================================================================
# Cleans up orphaned locks that exceed the expected TTL.
# Run via cron: */5 * * * * /opt/job-automation/scripts/clean_orphans.sh
#
# Why: If a worker crashes (SIGKILL/OOM), locks may not be released.
# This script finds stale locks and removes them so jobs can continue.
# ==============================================================================

set -e

REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_DB="${REDIS_DB:-0}"
REDIS_PASSWORD_ARG=""
if [ -n "$REDIS_PASSWORD" ]; then
    REDIS_PASSWORD_ARG="-a $REDIS_PASSWORD"
fi

LOCK_TTL="${LOCK_TTL:-3900}"
BROWSER_TTL="${BROWSER_TTL:-1200}"
ORPHAN_THRESHOLD="$((LOCK_TTL * 2))"

CLEANED=0
WARNINGS=0

echo "[$(date)] Orphan lock cleaner started..."

# Helper: check if redis-cli is available
REDIS_CLI="redis-cli"
if ! command -v $REDIS_CLI &> /dev/null; then
    REDIS_CLI="docker exec job-automation-redis redis-cli"
fi

# --- Clean orphaned student session locks ---
echo "[$(date)] Checking for orphaned student session locks..."
SESSION_KEYS=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG --scan --pattern "lock:student_session:*" 2>/dev/null || echo "")

for key in $SESSION_KEYS; do
    TTL=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG ttl "$key" 2>/dev/null || echo "-2")

    if [ "$TTL" -eq -2 ] || [ "$TTL" -eq -1 ]; then
        echo "[WARN] Lock has no TTL (persistent): $key"
        WARNINGS=$((WARNINGS + 1))
        continue
    fi

    if [ "$TTL" -gt "$ORPHAN_THRESHOLD" ]; then
        echo "[CLEAN] Removing orphaned session lock (TTL=$TTL, threshold=$ORPHAN_THRESHOLD): $key"
        $REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG del "$key" 2>/dev/null
        CLEANED=$((CLEANED + 1))
    fi
done

# --- Clean orphaned student platform locks ---
echo "[$(date)] Checking for orphaned student platform locks..."
PLATFORM_KEYS=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG --scan --pattern "lock:student_platform:*" 2>/dev/null || echo "")

for key in $PLATFORM_KEYS; do
    TTL=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG ttl "$key" 2>/dev/null || echo "-2")

    if [ "$TTL" -eq -2 ] || [ "$TTL" -eq -1 ]; then
        echo "[WARN] Lock has no TTL (persistent): $key"
        WARNINGS=$((WARNINGS + 1))
        continue
    fi

    if [ "$TTL" -gt "$ORPHAN_THRESHOLD" ]; then
        echo "[CLEAN] Removing orphaned platform lock (TTL=$TTL, threshold=$ORPHAN_THRESHOLD): $key"
        $REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG del "$key" 2>/dev/null
        CLEANED=$((CLEANED + 1))
    fi
done

# --- Clean orphaned task locks ---
echo "[$(date)] Checking for orphaned task locks..."
TASK_KEYS=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG --scan --pattern "lock:task:*" 2>/dev/null || echo "")

for key in $TASK_KEYS; do
    TTL=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG ttl "$key" 2>/dev/null || echo "-2")

    if [ "$TTL" -eq -2 ] || [ "$TTL" -eq -1 ]; then
        continue
    fi

    if [ "$TTL" -gt "$ORPHAN_THRESHOLD" ]; then
        echo "[CLEAN] Removing orphaned task lock (TTL=$TTL): $key"
        $REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG del "$key" 2>/dev/null
        CLEANED=$((CLEANED + 1))
    fi
done

# --- Clean stale browser semaphore leases (tokens that expired but weren't removed) ---
echo "[$(date)] Checking for stale browser semaphore leases..."
BROWSER_LEASES=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG zrangebyscore "semaphore:browsers:leases" 0 "$(( $(date +%s) - BROWSER_TTL ))" 2>/dev/null || echo "")
for token in $BROWSER_LEASES; do
    echo "[CLEAN] Removing stale browser lease token: $token"
    $REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG zrem "semaphore:browsers:leases" "$token" 2>/dev/null
    CLEANED=$((CLEANED + 1))
done

# --- Clean stale circuit breaker states that are stuck open ---
echo "[$(date)] Checking for stale circuit breaker states..."
CIRCUIT_KEYS=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG --scan --pattern "circuit:*:state" 2>/dev/null || echo "")
for key in $CIRCUIT_KEYS; do
    STATE=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG get "$key" 2>/dev/null || echo "")
    if [ "$STATE" = "open" ]; then
        LAST_FAILURE=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG get "${key/state/last_failure}" 2>/dev/null || echo "")
        if [ -n "$LAST_FAILURE" ]; then
            ELAPSED=$(($(date +%s) - ${LAST_FAILURE%.*}))
            if [ "$ELAPSED" -gt 600 ]; then
                echo "[CLEAN] Resetting stuck circuit breaker (>10min open): $key"
                $REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG del "$key" 2>/dev/null
                $REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG del "${key/state/failures}" 2>/dev/null
                $REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG del "${key/state/last_failure}" 2>/dev/null
                CLEANED=$((CLEANED + 1))
            fi
        fi
    fi
done

# --- Clean old idempotency keys that failed to clear ---
echo "[$(date)] Checking for stale idempotency keys..."
IDEMP_KEYS=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG --scan --pattern "idemp:apply:*" 2>/dev/null || echo "")
ORPHAN_COUNT=0
for key in $IDEMP_KEYS; do
    TTL=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG ttl "$key" 2>/dev/null || echo "-2")
    if [ "$TTL" -eq -2 ] || [ "$TTL" -eq -1 ]; then
        continue
    fi
    if [ "$TTL" -gt 172800 ]; then
        echo "[CLEAN] Removing very old apply key (>48h): $key"
        $REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG del "$key" 2>/dev/null
        ORPHAN_COUNT=$((ORPHAN_COUNT + 1))
    fi
done

# --- Clean stale session keys from crashed workers (completed status but job never ran) ---
echo "[$(date)] Checking for stale session keys (idemp:session:*)..."
SESSION_KEYS=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG --scan --pattern "idemp:session:*" 2>/dev/null || echo "")
SESSION_CLEANED=0
SESSION_WARNINGS=0
for key in $SESSION_KEYS; do
    STATE=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG get "$key" 2>/dev/null || echo "")
    TTL=$($REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG ttl "$key" 2>/dev/null || echo "-2")
    if [ "$STATE" = "completed" ] || [ "$TTL" -gt 14400 ]; then
        echo "[CLEAN] Removing stale session key (state=$STATE, TTL=$TTL): $key"
        $REDIS_CLI -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" $REDIS_PASSWORD_ARG del "$key" 2>/dev/null
        SESSION_CLEANED=$((SESSION_CLEANED + 1))
    fi
    if [ "$TTL" -eq -1 ]; then
        echo "[WARN] Session key has no TTL (persistent): $key"
        SESSION_WARNINGS=$((SESSION_WARNINGS + 1))
    fi
done

echo "[$(date)] Orphan cleaner complete: cleaned=$CLEANED, warnings=$WARNINGS, old_apply_keys=$ORPHAN_COUNT, stale_sessions=$SESSION_CLEANED, session_warnings=$SESSION_WARNINGS"

if [ "$CLEANED" -gt 0 ] || [ "$WARNINGS" -gt 0 ]; then
    echo "[$(date)] ALERT: Orphan cleanup performed. Check logs above."
fi