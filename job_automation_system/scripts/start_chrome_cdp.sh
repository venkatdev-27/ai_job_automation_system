#!/bin/bash
# Chrome CDP Container Startup Script
# ===================================
# Starts browserless Chrome container for CDP (Chrome DevTools Protocol)
# No manual Chrome required - fully automated!

set -e

echo "============================================"
echo "Chrome CDP Container - Starting"
echo "============================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running. Please start Docker first."
    exit 1
fi

# Check if chrome-cdp service already exists
if docker ps -a --format '{{.Names}}' | grep -q "^job-automation-chrome-cdp$"; then
    echo "Chrome CDP container already exists. Checking status..."
    
    if docker ps --format '{{.Names}}' | grep -q "^job-automation-chrome-cdp$"; then
        echo "Chrome CDP container is already RUNNING."
        echo "Health check:"
        curl -sf http://localhost:3000/health || echo "Container running but health check failed"
    else
        echo "Chrome CDP container exists but stopped. Starting..."
        docker start job-automation-chrome-cdp
    fi
else
    echo "Starting Chrome CDP container..."
    docker-compose up -d chrome-cdp
fi

# Wait for container to be ready
echo "Waiting for Chrome CDP to be ready..."
sleep 3

# Verify CDP is accessible
MAX_RETRIES=10
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -sf http://localhost:9222/json > /dev/null 2>&1; then
        echo "✓ Chrome CDP is ready at http://localhost:9222"
        echo "✓ Web interface available at http://localhost:3000"
        break
    fi
    echo "  Waiting for CDP... ($((RETRY_COUNT+1))/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT+1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "WARNING: CDP may not be fully ready yet. Checking container status..."
    docker ps --filter "name=job-automation-chrome-cdp"
fi

echo ""
echo "============================================"
echo "Chrome CDP Status"
echo "============================================"
docker ps --filter "name=job-automation-chrome-cdp" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "CDP Endpoints:"
echo "  - CDP Debug: http://localhost:9222/json"
echo "  - Web UI:    http://localhost:3000"
echo "  - Docker:    http://chrome-cdp:9222 (internal)"
echo ""