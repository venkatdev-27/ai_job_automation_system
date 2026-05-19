#!/bin/bash
# ==============================================================================
# Job Automation System - Deployment Script
# ==============================================================================
# Zero-downtime deployment for production VPS
#
# Usage:
#   ./deploy.sh                    # Normal deployment
#   ./deploy.sh --force-rebuild    # Force rebuild all images
#   ./deploy.sh --skip-backup      # Skip backup before deploy
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose-production.yml"
ENV_FILE=".env.production"
BACKUP_DIR="/opt/job-automation/backups"
DATE=$(date +%Y%m%d-%H%M%S)

# Parse arguments
FORCE_REBUILD=false
SKIP_BACKUP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --force-rebuild)
            FORCE_REBUILD=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --help)
            echo "Usage: ./deploy.sh [--force-rebuild] [--skip-backup] [--help]"
            echo ""
            echo "Options:"
            echo "  --force-rebuild    Force rebuild all Docker images"
            echo "  --skip-backup      Skip backup before deployment"
            echo "  --help             Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if environment file exists
check_env() {
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file '$ENV_FILE' not found!"
        log_error "Please copy '.env.production.example' to '.env.production' and fill in your values"
        exit 1
    fi
    log_info "Environment file found"
}

# Backup current state
backup() {
    if [ "$SKIP_BACKUP" = true ]; then
        log_warn "Skipping backup (--skip-backup flag set)"
        return
    fi

    log_info "Creating backup..."
    mkdir -p $BACKUP_DIR

    # Backup Redis data
    if docker volume ls -q | grep -q "job_automation_redis_data"; then
        docker run --rm \
            -v job_automation_redis_data:/data \
            -v $BACKUP_DIR:/backup \
            alpine:latest \
            tar -czf /backup/redis-$DATE.tar.gz -C /data . || true
        log_info "Redis backup created: redis-$DATE.tar.gz"
    fi

    log_info "Backup completed"
}

# Pull latest images
pull_images() {
    log_info "Pulling latest images..."
    docker compose -f $COMPOSE_FILE pull
}

# Build images
build_images() {
    if [ "$FORCE_REBUILD" = true ]; then
        log_warn "Force rebuild enabled"
        docker compose -f $COMPOSE_FILE build --no-cache
    else
        log_info "Building images (using cached layers)..."
        docker compose -f $COMPOSE_FILE build
    fi
}

# Deploy
deploy() {
    log_info "Deploying containers..."

    # Stop current containers
    log_info "Stopping current containers..."
    docker compose -f $COMPOSE_FILE down || true

    # Start new containers
    log_info "Starting new containers..."
    docker compose -f $COMPOSE_FILE up -d

    log_info "Waiting for services to be healthy..."
    sleep 30
}

# Verify deployment
verify() {
    log_info "Verifying deployment..."

    # Check if all containers are running
    RUNNING=$(docker compose -f $COMPOSE_FILE ps | grep -c "Up" || echo "0")
    TOTAL=$(docker compose -f $COMPOSE_FILE ps | grep -c "celery\|node-api\|ai-engine\|redis\|chrome" || echo "0")

    if [ "$RUNNING" -ge "$TOTAL" ]; then
        log_info "All containers are running"
    else
        log_info "Some containers failed to start (running: $RUNNING / expected: $TOTAL)"
        log_info "Check logs with: docker compose -f $COMPOSE_FILE logs"
        exit 1
    fi

    # Health check
    if curl -sf http://localhost:5000/api/system/health > /dev/null; then
        log_info "Node API is healthy"
    else
        log_error "Node API health check failed"
        exit 1
    fi

    if curl -sf http://localhost:8000/health > /dev/null; then
        log_info "AI Engine is healthy"
    else
        log_error "AI Engine health check failed"
        exit 1
    fi
}

# Main execution
main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║         JOB AUTOMATION SYSTEM - DEPLOYMENT                 ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    log_info "Deployment started at: $(date)"
    echo ""

    check_env
    backup
    pull_images
    build_images
    deploy
    verify

    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                  DEPLOYMENT COMPLETE!                      ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    log_info "Dashboard: http://localhost:5173"
    log_info "API: http://localhost:5000"
    log_info "AI Engine: http://localhost:8000"
    log_info "Prometheus: http://localhost:9090"
    log_info "Grafana: http://localhost:3001"
    echo ""
}

main "$@"
