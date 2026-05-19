#!/bin/bash

# Job Automation System - Start All Workers
# ===========================================

set -e

echo "============================================"
echo "Job Automation System - Starting Workers"
echo "============================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running. Please start Docker first."
    exit 1
fi

# Start Chrome CDP container (no manual Chrome needed!)
echo "Starting Chrome CDP container (automatic)..."
docker-compose up -d chrome-cdp
sleep 3

# Start infrastructure (Redis + MongoDB)
echo "Starting infrastructure services..."
docker-compose up -d redis mongodb

# Wait for Redis
echo "Waiting for Redis..."
sleep 5

# Wait for MongoDB
echo "Waiting for MongoDB..."
sleep 5

# Start all workers
echo "Starting Celery workers..."

# Naukri workers (3 workers, 2 concurrency each = 6 max)
docker-compose up -d celery-naukri-1 celery-naukri-2 celery-naukri-3

# LinkedIn worker (1 worker, 1 concurrency - STRICT)
docker-compose up -d celery-linkedin-1

# Start monitoring
echo "Starting monitoring services..."
docker-compose up -d flower prometheus grafana

echo ""
echo "============================================"
echo "System Started!"
echo "============================================"
echo ""
echo "Services:"
echo "  - Chrome CDP:      localhost:9222 (CDP), localhost:3000 (Web)"
echo "  - Redis:           localhost:6379"
echo "  - MongoDB:         localhost:27017"
echo "  - Flower:          http://localhost:5555"
echo "  - Prometheus:      http://localhost:9090"
echo "  - Grafana:         http://localhost:3000 (admin/admin)"
echo ""
echo "Workers:"
echo "  - Naukri:   3 workers (2 concurrency each) = 6 max"
echo "  - LinkedIn: 1 worker  (1 concurrency)       = 1 max"
echo ""
echo "Total max concurrent tasks: 7 (browser limit: 6-8)"
echo ""
echo "Run 'docker-compose logs -f' to see worker logs"
echo "Run 'docker-compose down' to stop all services"