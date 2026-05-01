# Installation Guide

## Overview

This guide covers the complete installation process for the Multi-Robot Trading System on Linux.

## System Requirements

### Minimum Requirements

- **CPU:** 2 cores
- **RAM:** 4GB
- **Storage:** 50GB
- **Network:** Stable internet connection

### Recommended Requirements

- **CPU:** 4+ cores
- **RAM:** 8GB+
- **Storage:** 100GB+ SSD
- **Network:** 100Mbps+ internet connection

## Prerequisites

### Operating System

- Ubuntu 22.04 LTS or later
- Debian 11 or later
- CentOS 8 or later
- Other Linux distributions (with compatible package manager)

### Software Dependencies

- Python 3.10 or higher
- PostgreSQL 14 or higher
- MongoDB 6 or higher
- Redis 7 or higher
- MetaTrader 5 (Windows application, run via Wine on Linux)

## Installation Methods

### Method 1: Automated Installation (Recommended)

Run the automated setup script:

```bash
cd AI_robot
./scripts/setup.sh
```

This will:
1. Install system dependencies
2. Create Python virtual environment
3. Install Python dependencies
4. Setup configuration files
5. Initialize databases
6. Verify installation

### Method 2: Manual Installation

#### Step 1: Install System Dependencies

**Ubuntu/Debian:**
```bash
# Update package list
sudo apt-get update

# Install Python 3.10+
sudo apt-get install -y python3 python3-pip python3-venv python3-dev

# Install PostgreSQL
sudo apt-get install -y postgresql postgresql-contrib

# Install MongoDB
sudo apt-get install -y mongodb

# Install Redis
sudo apt-get install -y redis-server

# Install Wine (for MT5 on Linux)
sudo dpkg --add-architecture i386
sudo apt-get update
sudo apt-get install -y wine64 wine32 winetricks

# Start services
sudo systemctl start postgresql
sudo systemctl start mongod
sudo systemctl start redis-server

# Enable services on boot
sudo systemctl enable postgresql
sudo systemctl enable mongod
sudo systemctl enable redis-server
```

**CentOS/RHEL:**
```bash
# Update system
sudo yum update

# Install Python 3.10+
sudo yum install -y python3 python3-pip python3-virtualenv

# Install PostgreSQL
sudo yum install -y postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Install MongoDB
sudo yum install -y mongodb-server
sudo systemctl start mongod
sudo systemctl enable mongod

# Install Redis
sudo yum install -y redis
sudo systemctl start redis
sudo systemctl enable redis

# Install Wine
sudo yum install -y wine
```

#### Step 2: Setup Python Environment

```bash
cd AI_robot

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

#### Step 3: Install Python Dependencies

```bash
# Install dependencies
pip install -r requirements.txt
```

#### Step 4: Setup MetaTrader 5

**On Linux (via Wine):**
```bash
# Download MT5 installer
cd ~/Downloads
wget https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe

# Install MT5
wine mt5setup.exe

# Configure MT5
# - Open MT5 terminal
# - File → Open an Account
# - Select broker and create demo account
# - Enable "Allow algorithmic trading" in Tools → Options → Expert Advisors
```

**On Windows:**
1. Download MT5 from your broker's website
2. Install and configure with your account
3. Enable "Allow algorithmic trading"
4. Enable "Allow DLL imports"

#### Step 5: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your preferred editor
```

Required variables:
```bash
# MetaTrader 5
MT5_PASSWORD=your_password
MT5_ACCOUNT=your_account_number

# Database
DB_USER=trading_user
DB_PASSWORD=your_postgres_password

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

#### Step 6: Configure the System

Edit `config.yaml`:

```yaml
mt5:
  account_type: "demo"  # or "live"
  account_number: your_account_number
  server: your_broker_server
  password: "${MT5_PASSWORD}"

trading:
  style: "day_trading"  # scalping, day_trading, swing_trading
  risk_profile: "moderate"  # conservative, moderate, aggressive
```

#### Step 7: Initialize Databases

```bash
# Initialize PostgreSQL
python scripts/init_databases.py

# Initialize MongoDB
python scripts/init_mongodb.py
```

#### Step 8: Verify Installation

```bash
# Run verification script
./scripts/verify_setup.sh
```

This will check:
- ✓ Python 3.10+ installed
- ✓ PostgreSQL installed and running
- ✓ MongoDB installed and running
- ✓ Redis installed and running
- ✓ MetaTrader 5 installed
- ✓ Virtual environment created
- ✓ Configuration files present

## Docker Installation

### Prerequisites

- Docker installed
- Docker Compose installed

### Quick Start

```bash
cd AI_robot

# Build and start containers
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### Configuration

Edit `docker-compose.yml` to customize:

```yaml
services:
  postgres:
    environment:
      POSTGRES_USER: your_user
      POSTGRES_PASSWORD: your_password
  
  mongodb:
    environment:
      MONGO_INITDB_ROOT_USERNAME: your_user
      MONGO_INITDB_ROOT_PASSWORD: your_password
```

## Systemd Service Installation

### Create Service File

```bash
sudo cp scripts/trading-system.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/trading-system.service
```

### Configure Service

Edit `/etc/systemd/system/trading-system.service`:

```ini
[Service]
User=trading
WorkingDirectory=/opt/trading-system
ExecStart=/opt/trading-system/venv/bin/python /opt/trading-system/src/main.py
Environment="MT5_PASSWORD=your_password"
Environment="DB_USER=your_user"
Environment="DB_PASSWORD=your_password"
```

### Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-system
sudo systemctl start trading-system
```

### Manage Service

```bash
# Start
sudo systemctl start trading-system

# Stop
sudo systemctl stop trading-system

# Restart
sudo systemctl restart trading-system

# Status
sudo systemctl status trading-system

# Logs
journalctl -u trading-system -f
```

## Testing the Installation

### Test MT5 Connection

Create a test script `test_mt5.py`:

```python
import MetaTrader5 as mt5

# Initialize
if not mt5.initialize():
    print("MT5 initialization failed")
    quit()

# Get account info
account_info = mt5.account_info()
print(f"Account: {account_info.login}")
print(f"Balance: {account_info.balance}")

# Shutdown
mt5.shutdown()
```

Run:
```bash
python test_mt5.py
```

### Test Database Connection

Create a test script `test_db.py`:

```python
import asyncio
from src.database.postgresql_manager import PostgreSQLManager
from src.database.mongodb_manager import MongoDBManager

async def test():
    # Test PostgreSQL
    pg = PostgreSQLManager()
    await pg.connect()
    print("PostgreSQL connected")
    await pg.disconnect()
    
    # Test MongoDB
    mongo = MongoDBManager()
    await mongo.connect()
    print("MongoDB connected")
    await mongo.disconnect()

asyncio.run(test())
```

Run:
```bash
python test_db.py
```

### Test Full System

```bash
python src/main.py --test
```

## Troubleshooting

### Python Import Errors

```
ModuleNotFoundError: No module named 'MetaTrader5'
```

**Solution:**
```bash
pip install MetaTrader5
```

### Database Connection Errors

```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Solution:**
```bash
# Check if database is running
sudo systemctl status postgresql
sudo systemctl status mongod

# Start if not running
sudo systemctl start postgresql
sudo systemctl start mongod
```

### MT5 Connection Errors

```
MT5 initialization failed
```

**Solution:**
- Ensure MT5 terminal is running
- Verify account credentials
- Check "Allow algorithmic trading" is enabled

### Permission Errors

```
Permission denied
```

**Solution:**
```bash
# Check file permissions
ls -la

# Fix permissions
chmod +x scripts/*.sh
```

## Next Steps

After successful installation:

1. [Configuration Guide](CONFIGURATION.md)
2. [MT5 Setup Guide](MT5_SETUP.md)
3. [Paper Trading Guide](PAPER_TRADING.md)
4. [User Manual](USER_MANUAL.md)

## Support

For issues:
- Check documentation in `/docs`
- Review logs in `/logs`
- Open issue on GitHub
