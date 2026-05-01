#!/bin/bash

# Multi-Robot Trading System - Backup Script
# This script creates backups of the database and configuration

set -e

echo "=========================================="
echo "Multi-Robot Trading System - Backup"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
BACKUP_DIR="/opt/trading-system/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE=$(date +%Y%m%d)

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL
echo -e "${YELLOW}Backing up PostgreSQL database...${NC}"
PG_BACKUP="$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"
pg_dump -U "${DB_USER:-trading_user}" -h "${DB_HOST:-localhost}" "${DB_NAME:-trading_db}" | gzip > "$PG_BACKUP"
echo -e "${GREEN}PostgreSQL backup: $PG_BACKUP${NC}"

# Backup MongoDB
echo -e "${YELLOW}Backing up MongoDB database...${NC}"
MONGO_BACKUP="$BACKUP_DIR/mongodb_${TIMESTAMP}.tar.gz"
mongodump --host "${MONGO_HOST:-localhost}" --username "${MONGO_USER:-mongo_user}" --password "${MONGO_PASSWORD:-mongo_password}" --archive | gzip > "$MONGO_BACKUP"
echo -e "${GREEN}MongoDB backup: $MONGO_BACKUP${NC}"

# Backup configuration
echo -e "${YELLOW}Backing up configuration files...${NC}"
CONFIG_BACKUP="$BACKUP_DIR/config_${TIMESTAMP}.tar.gz"
tar -czf "$CONFIG_BACKUP" -C /opt/trading-system config.yaml .env
echo -e "${GREEN}Configuration backup: $CONFIG_BACKUP${NC}"

# Clean up old backups (keep last 30 days)
echo -e "${YELLOW}Cleaning up old backups...${NC}"
find "$BACKUP_DIR" -type f -mtime +30 -delete
echo -e "${GREEN}Old backups cleaned up${NC}"

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}Backup completed successfully!${NC}"
echo -e "${GREEN}==========================================${NC}"

# List backups
echo ""
echo "Current backups:"
ls -lh "$BACKUP_DIR"
echo ""
