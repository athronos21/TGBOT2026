# Multi-Robot Trading System

## Overview
A distributed automated trading ecosystem composed of multiple intelligent robots (agents) that collaborate to analyze markets, detect trading opportunities, manage risk, execute trades, and learn from performance.

**Target Asset:** XAUUSD (Gold)  
**Execution Platform:** MetaTrader 5  
**System Concept:** Many small intelligent robots working together to achieve profitable trading

## System Architecture

The system consists of 6 main robot swarms:
- **Data Collection Swarm** (6 robots) - Real-time market data collection
- **Analysis Swarm** (7 robots) - ICT-style market structure analysis
- **Decision Swarm** (5 robots) - Signal generation and confluence checking
- **Risk Management Swarm** (4 robots) - Position sizing and exposure control
- **Execution Swarm** (4 robots) - Trade execution and management
- **Monitoring Swarm** (3 robots) - System health and performance tracking

## Project Structure
```
AI_robot/
├── src/
│   ├── core/              # Core framework (Robot base, MessageBus, MasterController)
│   ├── database/          # Database managers (PostgreSQL, MongoDB, Redis)
│   ├── integrations/      # External integrations (MT5, Telegram, APIs)
│   ├── config/            # Configuration management
│   ├── robots/            # Robot implementations
│   │   ├── data_collection/
│   │   ├── analysis/
│   │   ├── decision/
│   │   ├── risk/
│   │   ├── execution/
│   │   ├── monitoring/
│   │   └── communication/
│   ├── ai/                # AI/ML models
│   └── utils/             # Utility functions
├── tests/
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── e2e/               # End-to-end tests
├── models/                # Trained AI models
├── data/                  # Historical data for backtesting
├── logs/                  # System logs
├── backups/               # Database backups
├── strategies/            # Custom trading strategies
├── docs/                  # Documentation
├── scripts/               # Setup and utility scripts
└── .kiro/                 # Kiro IDE configuration
    └── specs/             # Feature specifications
```

## Tech Stack
- **Language:** Python 3.10+
- **Trading Platform:** MetaTrader 5 (Python API)
- **Databases:** PostgreSQL, MongoDB, Redis
- **Message Bus:** Redis Pub/Sub
- **AI/ML:** PyTorch
- **Notifications:** python-telegram-bot
- **Deployment:** Docker, systemd
- **Web Dashboard:** Flask/FastAPI (optional)

## Getting Started

### Prerequisites
- Python 3.10 or higher
- PostgreSQL 14+
- MongoDB 6+
- Redis 7+
- MetaTrader 5 terminal
- Broker account with MT5 support

### Quick Setup

**Automated Setup (Recommended):**
```bash
# Clone the repository
git clone <repository-url>
cd AI_robot

# Run the setup script
./scripts/setup.sh
```

**Verify Installation:**
```bash
# Check that all components are installed
./scripts/verify_setup.sh
```

### Manual Installation

If you prefer to install components manually:

#### 1. Install System Dependencies

**On Ubuntu/Debian:**
```bash
# Update package list
sudo apt-get update

# Install Python 3.10+
sudo apt-get install -y python3 python3-pip python3-venv

# Install PostgreSQL
sudo apt-get install -y postgresql postgresql-contrib

# Install MongoDB
# See docs/MT5_SETUP.md for detailed MongoDB installation

# Install Redis
sudo apt-get install -y redis-server

# Start services
sudo systemctl start postgresql
sudo systemctl start mongod
sudo systemctl start redis-server

# Enable services to start on boot
sudo systemctl enable postgresql
sudo systemctl enable mongod
sudo systemctl enable redis-server
```

#### 2. Setup Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

#### 3. Install Python Dependencies

```bash
# Install dependencies (once requirements.txt is created in task 1.3)
pip install -r requirements.txt
```

#### 4. Setup MetaTrader 5

**On Linux:**
```bash
# Run the MT5 setup script
./scripts/setup_mt5.sh

# Or follow the detailed guide
cat docs/MT5_SETUP.md
```

**On Windows:**
- Download MT5 from your broker's website
- Install and configure with your account
- Enable "Allow algorithmic trading" in Tools → Options → Expert Advisors
- Enable "Allow DLL imports" in the same section

**For detailed MT5 setup instructions, see:** [docs/MT5_SETUP.md](docs/MT5_SETUP.md)

#### 5. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your preferred editor
```

Required environment variables:
- `MT5_PASSWORD` - Your MT5 account password
- `DB_USER` - PostgreSQL username
- `DB_PASSWORD` - PostgreSQL password
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID

#### 6. Configure the System

Edit `config.yaml` to set:
- MT5 broker credentials
- Trading style (scalping/day_trading/swing_trading)
- Risk profile (conservative/moderate/aggressive)
- Telegram bot token and chat ID
- Database connection details

#### 7. Initialize Databases

```bash
# Initialize PostgreSQL and MongoDB schemas
python scripts/init_databases.py
```

#### 8. Verify Setup

```bash
# Run verification script to check all components
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

### Configuration

**Trading Styles:**
- **Scalping:** Quick trades, 5-15 minute duration, 5+ pip targets
- **Day Trading:** Close all positions by end of day, 10+ pip targets
- **Swing Trading:** Hold for days/weeks, 50+ pip targets

**Risk Profiles:**
- **Conservative:** 0.5% risk per trade, 2% max daily loss, 8% max drawdown
- **Moderate:** 1% risk per trade, 3% max daily loss, 10% max drawdown
- **Aggressive:** 2% risk per trade, 5% max daily loss, 15% max drawdown

Edit `config.yaml` to change settings:
```yaml
trading:
  style: "day_trading"
  risk_profile: "moderate"
```

### Running the System

**Start all robots:**
```bash
python src/main.py
```

**Start specific robot swarm:**
```bash
python src/main.py --swarm data_collection
```

**Run in paper trading mode:**
```bash
python src/main.py --mode paper
```

**Run backtesting:**
```bash
python scripts/backtest.py --start 2024-01-01 --end 2025-12-31
```

### Telegram Bot Commands

Once running, interact with the system via Telegram:
- `/start` - Start bot and show menu
- `/status` - Show system status
- `/stats` - Show performance statistics
- `/trades` - Show open trades
- `/pause` - Pause trading
- `/resume` - Resume trading
- `/killswitch` - Emergency stop all trading

## Development

### Running Tests
```bash
# Run all tests
pytest tests/

# Run unit tests only
pytest tests/unit/

# Run with coverage
pytest --cov=src tests/
```

### Code Style
```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

### Adding a New Robot

1. Create robot class in appropriate swarm directory
2. Inherit from `Robot` base class
3. Implement required methods: `initialize()`, `process()`, `cleanup()`
4. Register robot in `config.yaml`
5. Add unit tests in `tests/unit/robots/`

Example:
```python
from src.core.robot import Robot

class MyCustomBot(Robot):
    async def initialize(self):
        # Setup resources
        pass
        
    async def process(self, data):
        # Main logic
        result = self.analyze(data)
        await self.send_message('my_event', result)
        return result
        
    async def cleanup(self):
        # Cleanup resources
        pass
```

## Deployment

### Docker Deployment
```bash
docker-compose up -d
```

### Systemd Service
```bash
sudo cp scripts/trading-system.service /etc/systemd/system/
sudo systemctl enable trading-system
sudo systemctl start trading-system
```

### Monitoring
```bash
# View logs
journalctl -u trading-system -f

# Check status
systemctl status trading-system
```

## Safety Features

- **Kill Switch:** Emergency stop via Telegram command
- **Circuit Breaker:** Automatic pause on daily/weekly/monthly loss limits
- **Loss Protection:** Pause after consecutive losses
- **Trading Limits:** Max trades per day/hour, minimum time between trades
- **Risk Validation:** All trades validated against risk profile before execution

## Performance Metrics

The system tracks:
- Win rate
- Profit factor
- Maximum drawdown
- Sharpe ratio
- Total trades
- Average profit/loss per trade
- Daily/weekly/monthly P&L

Access via:
- Telegram bot (`/stats`)
- Web dashboard (if enabled)
- Database queries

## Roadmap

**Phase 1 (Months 1-3):** MVP with 10 core robots  
**Phase 2 (Months 4-6):** Expand to 44 robots with advanced features  
**Phase 3 (Months 7-12):** Scale to 100+ robots with advanced AI

See `.kiro/specs/multi-robot-trading-system/` for detailed specifications.

## Documentation

- [Requirements](/.kiro/specs/multi-robot-trading-system/requirements.md)
- [Design Document](/.kiro/specs/multi-robot-trading-system/design.md)
- [Task List](/.kiro/specs/multi-robot-trading-system/tasks.md)
- [API Documentation](/docs/api.md) (coming soon)
- [User Manual](/docs/user-manual.md) (coming soon)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions:
- Open an issue on GitHub
- Check documentation in `/docs`
- Review specs in `.kiro/specs/`

## License

[Add license information]

## Disclaimer

**IMPORTANT:** This is an automated trading system. Trading involves substantial risk of loss. Use at your own risk. Always start with paper trading and small amounts. Never trade with money you cannot afford to lose.

## Acknowledgments

- ICT (Inner Circle Trader) methodology
- MetaTrader 5 platform
- Open source community
