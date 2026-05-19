#!/bin/bash
# Quick Test Runner for 3 Platform System
# =======================================
# Uses minimal workers (1 per platform)

echo "========================================"
echo "3 Platform Integration Test Runner"
echo "========================================"

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found"
    exit 1
fi

echo ""
echo "Starting test environment..."

# Start minimal test setup
echo "Starting Redis and MongoDB..."
docker-compose -f docker-compose.test.yml up -d redis mongodb

# Wait for services
echo "Waiting for Redis..."
sleep 2

echo "Waiting for MongoDB..."
sleep 3

echo ""
echo "Starting workers..."
docker-compose -f docker-compose.test.yml up -d celery-naukri-test celery-linkedin-test celery-foundit-test celery-producer-test

echo ""
echo "Starting Flower monitoring..."
docker-compose -f docker-compose.test.yml up -d flower

echo ""
echo "========================================"
echo "Services Status"
echo "========================================"
docker-compose -f docker-compose.test.yml ps

echo ""
echo "========================================"
echo "Access Points"
echo "========================================"
echo "Flower (Celery Monitoring): http://localhost:5555"
echo ""

echo ""
echo "To trigger test jobs, use:"
echo "  # Naukri"
echo '  curl -X POST http://localhost:5000/api/apply -H "Content-Type: application/json" -d "{\"student_id\": \"test\", \"platform\": \"naukri\", \"job_url\": \"https://example.com/job\"}"'
echo ""
echo "  # LinkedIn"
echo '  curl -X POST http://localhost:5000/api/apply -H "Content-Type: application/json" -d "{\"student_id\": \"test\", \"platform\": \"linkedin\", \"job_url\": \"https://example.com/job\"}"'
echo ""
echo "  # FoundIT"
echo '  curl -X POST http://localhost:5000/api/apply -H "Content-Type: application/json" -d "{\"student_id\": \"test\", \"platform\": \"foundit\", \"job_url\": \"https://example.com/job\"}"'

echo ""
echo "To run tests (once Redis is running):"
echo "  cd job_automation_system"
echo "  python tests/test_integration.py"

echo ""
echo "To stop test environment:"
echo "  docker-compose -f docker-compose.test.yml down"

echo ""
echo "Done!"
