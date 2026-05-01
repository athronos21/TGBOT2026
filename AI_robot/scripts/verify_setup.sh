#!/bin/bash

# Development Environment Verification Script
# Verifies that all required components are installed and configured

set -e

echo "=========================================="
echo "Development Environment Verification"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

# Track overall status
OVERALL_STATUS=0

# Check Python
echo "Checking Python..."
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
        print_status 0 "Python $PYTHON_VERSION (>= 3.10 required)"
    else
        print_status 1 "Python $PYTHON_VERSION (>= 3.10 required)"
        OVERALL_STATUS=1
    fi
else
    print_status 1 "Python not found"
    OVERALL_STATUS=1
fi
echo ""

# Check PostgreSQL
echo "Checking PostgreSQL..."
if command_exists psql; then
    POSTGRES_VERSION=$(psql --version | cut -d' ' -f3)
    print_status 0 "PostgreSQL $POSTGRES_VERSION"
    
    # Check if PostgreSQL service is running
    if systemctl is-active --quiet postgresql; then
        print_status 0 "PostgreSQL service is running"
    else
        print_status 1 "PostgreSQL service is not running"
        echo "  Run: sudo systemctl start postgresql"
        OVERALL_STATUS=1
    fi
else
    print_status 1 "PostgreSQL not found"
    OVERALL_STATUS=1
fi
echo ""

# Check MongoDB
echo "Checking MongoDB..."
if command_exists mongod; then
    MONGO_VERSION=$(mongod --version | grep "db version" | cut -d'v' -f2)
    print_status 0 "MongoDB $MONGO_VERSION"
    
    # Check if MongoDB service is running
    if systemctl is-active --quiet mongod; then
        print_status 0 "MongoDB service is running"
    else
        print_status 1 "MongoDB service is not running"
        echo "  Run: sudo systemctl start mongod"
        OVERALL_STATUS=1
    fi
else
    print_status 1 "MongoDB not found"
    OVERALL_STATUS=1
fi
echo ""

# Check Redis
echo "Checking Redis..."
if command_exists redis-server; then
    REDIS_VERSION=$(redis-server --version | cut -d'=' -f2 | cut -d' ' -f1)
    print_status 0 "Redis $REDIS_VERSION"
    
    # Check if Redis service is running
    if systemctl is-active --quiet redis-server || systemctl is-active --quiet redis; then
        print_status 0 "Redis service is running"
    else
        print_status 1 "Redis service is not running"
        echo "  Run: sudo systemctl start redis-server"
        OVERALL_STATUS=1
    fi
else
    print_status 1 "Redis not found"
    OVERALL_STATUS=1
fi
echo ""

# Check MetaTrader 5
echo "Checking MetaTrader 5..."
MT5_PATH="$HOME/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe"
if [ -f "$MT5_PATH" ]; then
    print_status 0 "MT5 found at $MT5_PATH"
else
    print_status 1 "MT5 not found at expected path"
    echo "  Run: ./scripts/setup_mt5.sh"
    echo "  Or see: docs/MT5_SETUP.md for manual installation"
    OVERALL_STATUS=1
fi

# Check if Wine is installed (needed for MT5 on Linux)
if command_exists wine; then
    WINE_VERSION=$(wine --version)
    print_status 0 "Wine installed: $WINE_VERSION"
else
    print_status 1 "Wine not found (required for MT5 on Linux)"
    echo "  Run: sudo apt-get install wine64 wine32"
    OVERALL_STATUS=1
fi
echo ""

# Check Python virtual environment
echo "Checking Python virtual environment..."
if [ -d "venv" ]; then
    print_status 0 "Virtual environment exists"
    
    # Check if venv is activated
    if [ -n "$VIRTUAL_ENV" ]; then
        print_status 0 "Virtual environment is activated"
    else
        print_status 1 "Virtual environment is not activated"
        echo "  Run: source venv/bin/activate"
    fi
else
    print_status 1 "Virtual environment not found"
    echo "  Run: python3 -m venv venv"
    OVERALL_STATUS=1
fi
echo ""

# Check required Python packages (if venv is activated)
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Checking Python packages..."
    
    # Check if requirements.txt exists
    if [ -f "requirements.txt" ]; then
        print_status 0 "requirements.txt found"
        
        # Check if packages are installed
        if pip list | grep -q "MetaTrader5"; then
            print_status 0 "MetaTrader5 package installed"
        else
            print_status 1 "MetaTrader5 package not installed"
            echo "  Run: pip install MetaTrader5"
        fi
    else
        print_status 1 "requirements.txt not found"
        echo "  This will be created in task 1.3"
    fi
    echo ""
fi

# Check configuration files
echo "Checking configuration files..."
if [ -f "config.yaml" ]; then
    print_status 0 "config.yaml exists"
else
    print_status 1 "config.yaml not found"
    echo "  This will be created in task 1.4"
fi

if [ -f ".env.example" ]; then
    print_status 0 ".env.example exists"
else
    print_status 1 ".env.example not found"
    echo "  This will be created in task 1.4"
fi
echo ""

# Summary
echo "=========================================="
echo "Verification Summary"
echo "=========================================="
if [ $OVERALL_STATUS -eq 0 ]; then
    echo -e "${GREEN}All required components are installed and configured!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Complete task 1.3: Create requirements.txt"
    echo "2. Complete task 1.4: Setup configuration management"
    echo "3. Complete task 1.5: Setup logging system"
else
    echo -e "${YELLOW}Some components need attention (see above)${NC}"
    echo ""
    echo "Please install missing components before proceeding."
fi
echo ""

exit $OVERALL_STATUS
