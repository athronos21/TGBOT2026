#!/usr/bin/env bash
# Quick local setup script
set -e

echo "=== IT Schedule Management Bot — Setup ==="

# 1. Copy env file
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✅ Created .env — please fill in BOT_TOKEN and DB_PASSWORD"
else
  echo "ℹ️  .env already exists"
fi

# 2. Create virtual environment
if [ ! -d venv ]; then
  python3 -m venv venv
  echo "✅ Virtual environment created"
fi

# 3. Install dependencies
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "✅ Dependencies installed"

echo ""
echo "Next steps:"
echo "  1. Edit .env with your BOT_TOKEN and database credentials"
echo "  2. Start PostgreSQL (or run: docker-compose up -d db)"
echo "  3. Run the bot: python -m src.main"
echo "  4. In Telegram, send /seed_slots once to initialize time slots"
