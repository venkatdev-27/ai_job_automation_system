#!/bin/bash

# Job Automation System - Start Single Worker
# =============================================

QUEUE=${1:-naukri}
CONCURRENCY=${2:-2}

echo "Starting Celery worker for queue: $QUEUE with concurrency: $CONCURRENCY"

celery -A celery_app.app worker -Q $QUEUE -c $CONCURRENCY --loglevel=info --hostname=$QUEUE-$(hostname)