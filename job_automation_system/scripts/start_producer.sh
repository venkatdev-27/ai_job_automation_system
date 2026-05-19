#!/bin/bash

# Job Automation System - Start Producer
# =========================================

set -e

echo "Starting Job Producer..."

# Run producer with default settings
docker-compose run --rm producer

echo "Producer completed!"