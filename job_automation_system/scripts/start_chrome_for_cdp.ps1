#!/bin/bash
# Start Chrome with CDP enabled and bound to all interfaces (0.0.0.0)
# This allows Docker containers to connect to your host Chrome

set -e

# Find the host IP address
HOST_IP=$(hostname -I | awk '{print $1}')

echo "=========================================="
echo "Starting Chrome with CDP on 0.0.0.0:9222"
echo "Host IP: $HOST_IP"
echo "=========================================="

# Kill any existing chrome instances
taskkill //F //IM chrome.exe 2>/dev/null || true
sleep 2

# Start Chrome with CDP bound to all interfaces
# --remote-debugging-address=0.0.0.0 makes it accessible from Docker
# Using a temp profile to avoid conflicts
chrome.exe \
    --remote-debugging-port=9222 \
    --remote-debugging-address=0.0.0.0 \
    --user-data-dir="$TEMP/chrome-cdp-profile" \
    --no-first-run \
    --no-default-browser-check \
    --disable-extensions \
    --disable-sync \
    --disable-translate \
    --metrics-recording-only \
    --disable-logging \
    --enable-features=NetworkService,NetworkServiceInProcess \
    --ignore-certificate-errors \
    --ignore-ssl-errors \
    --ignore-certificate-errors-spki-list=* \
    "https://www.naukri.com" &

sleep 3

echo ""
echo "Chrome started with CDP!"
echo "CDP URL for Docker: http://$HOST_IP:9222"
echo ""
echo "To use in Docker, set environment variable:"
echo "  CDP_URL=http://$HOST_IP:9222"
echo "  USE_CDP=true"
echo ""
echo "To test: curl http://$HOST_IP:9222/json/version"