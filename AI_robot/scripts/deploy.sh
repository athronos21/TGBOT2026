#!/bin/bash

# Multi-Robot Trading System - Deployment Script
# This script sets up the trading system for production deployment

set -e

echo "=========================================="
echo "Multi-Robot Trading System - Deployment"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}Project directory: $PROJECT_DIR${NC}"

# Create trading user if it doesn't exist
if ! id -u "trading" >/dev/null 2>&1; then
    echo -e "${YELLOW}Creating trading user...${NC}"
    useradd -m -s /bin/bash trading
fi

# Create necessary directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p /opt/trading-system/logs
mkdir -p /opt/trading-system/data
mkdir -p /opt/trading-system/models
mkdir -p /opt/trading-system/backups
mkdir -p /opt/trading-system/venv

# Copy application files
echo -e "${YELLOW}Copying application files...${NC}"
cp -r "$PROJECT_DIR"/* /opt/trading-system/

# Set ownership
chown -R trading:trading /opt/trading-system

# Create Python virtual environment
echo -e "${YELLOW}Creating Python virtual environment...${NC}"
cd /opt/trading-system
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Create systemd service
echo -e "${YELLOW}Setting up systemd service...${NC}"
cp "$SCRIPT_DIR/trading-system.service" /etc/systemd/system/
chmod 644 /etc/systemd/system/trading-system.service

# Reload systemd
systemctl daemon-reload

# Enable service
systemctl enable trading-system

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${GREEN}==========================================${NC}"

echo ""
echo "Next steps:"
echo "1. Configure environment variables in /opt/trading-system/.env"
echo "2. Configure trading parameters in /opt/trading-system/config.yaml"
echo "3. Start the service: systemctl start trading-system"
echo "4. Check status: systemctl status trading-system"
echo "5. View logs: journalctl -u trading-system -f"
echo ""
