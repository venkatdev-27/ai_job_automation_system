#!/bin/bash
# ==============================================================================
# Job Automation System - VPS Setup Script
# ==============================================================================
# Run this script ONCE on a fresh VPS to set up the entire system
#
# Usage:
#   wget -O setup-vps.sh <url> && chmod +x setup-vps.sh && ./setup-vps.sh
# ==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_warn "Running as non-root. Some operations may require sudo."
fi

# ==============================================================================
# STEP 1: System Update & Docker Installation
# ==============================================================================
step1_install_docker() {
    log_info "Step 1: Installing Docker and dependencies..."

    apt update
    apt install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        wget \
        unzip \
        ufw \
        fail2ban

    # Add Docker GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Add Docker repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
        $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt update
    apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Enable Docker
    systemctl enable docker
    systemctl start docker

    # Install docker-compose as fallback (for older systems)
    curl -SL https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose 2>/dev/null && chmod +x /usr/local/bin/docker-compose || true

    # Enable Docker
    systemctl enable docker
    systemctl start docker

    log_info "Docker installed successfully"
}

# ==============================================================================
# STEP 2: Firewall Setup
# ==============================================================================
step2_setup_firewall() {
    log_info "Step 2: Setting up firewall..."

    # Allow SSH
    ufw allow 22/tcp

    # Allow services
    ufw allow 5000/tcp   # Node API
    ufw allow 5173/tcp   # Admin Dashboard (dev)
    ufw allow 3000/tcp   # Chrome CDP
    ufw allow 3001/tcp   # Grafana
    ufw allow 8000/tcp   # AI Engine
    ufw allow 9090/tcp   # Prometheus
    ufw allow 8080/tcp   # cAdvisor

    # Enable firewall
    echo "y" | ufw enable

    log_info "Firewall configured"
}

# ==============================================================================
# STEP 3: Directory Setup
# ==============================================================================
step3_setup_directories() {
    log_info "Step 3: Creating directories..."

    mkdir -p /opt/job-automation
    mkdir -p /opt/job-automation/backups
    mkdir -p /opt/job-automation/logs
    mkdir -p /opt/job-automation/chrome_profile

    log_info "Directories created"
}

# ==============================================================================
# STEP 4: Clone Repository
# ==============================================================================
step4_clone_repo() {
    log_info "Step 4: Clone or update repository..."

    if [ -d "/opt/job-automation/.git" ]; then
        log_info "Repository already exists, pulling latest..."
        cd /opt/job-automation
        git pull
    else
        log_warn "Please manually copy your repository to /opt/job-automation"
        log_warn "Or update this script with your git clone command:"
        log_warn "  git clone <your-repo-url> /opt/job-automation"
    fi

    log_info "Repository setup complete"
}

# ==============================================================================
# STEP 5: Environment Configuration
# ==============================================================================
step5_setup_env() {
    log_info "Step 5: Setting up environment file..."

    if [ ! -f /opt/job-automation/.env.production ]; then
        if [ -f /opt/job-automation/.env.production.example ]; then
            cp /opt/job-automation/.env.production.example /opt/job-automation/.env.production
            log_warn "Created .env.production from example"
            log_warn "Please edit /opt/job-automation/.env.production and fill in your values"
        else
            log_error ".env.production.example not found"
        fi
    fi

    log_info "Environment file ready"
}

# ==============================================================================
# STEP 6: Systemd Service
# ==============================================================================
step6_setup_service() {
    log_info "Step 6: Setting up systemd service..."

    cat > /etc/systemd/system/job-automation.service << 'EOF'
[Unit]
Description=Job Automation System
Requires=docker.service
After=docker.service
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/job-automation
ExecStartPre=/usr/bin/docker compose -f docker-compose-production.yml pull
ExecStart=/usr/bin/docker compose -f docker-compose-production.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose-production.yml down
TimeoutStartSec=300
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable job-automation.service

    log_info "Systemd service installed"
}

# ==============================================================================
# STEP 7: Fail2Ban Configuration
# ==============================================================================
step7_setup_fail2ban() {
    log_info "Step 7: Configuring Fail2Ban..."

    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log
EOF

    systemctl enable fail2ban
    systemctl start fail2ban

    log_info "Fail2Ban configured"
}

# ==============================================================================
# STEP 8: Start Services
# ==============================================================================
step8_start_services() {
    log_info "Step 8: Starting services..."

    systemctl start job-automation

    log_info "Services started"
    log_info "Check status with: systemctl status job-automation"
    log_info "View logs with: docker compose -f docker-compose-production.yml logs -f"
}

# ==============================================================================
# MAIN
# ==============================================================================
main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║         JOB AUTOMATION SYSTEM - VPS SETUP                  ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # Steps
    step1_install_docker
    step2_setup_firewall
    step3_setup_directories
    step4_clone_repo
    step5_setup_env
    step6_setup_service
    step7_setup_fail2ban
    step8_start_services

    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                  SETUP COMPLETE!                           ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Next steps:"
    echo "  1. Edit /opt/job-automation/.env.production with your values"
    echo "  2. Run: systemctl restart job-automation"
    echo "  3. Access dashboard at: http://your-vps-ip:5173"
    echo ""
}

main "$@"
