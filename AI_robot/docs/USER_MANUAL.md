# User Manual

## Overview

This manual covers how to use the Multi-Robot Trading System, from basic operation to advanced features.

## Quick Start

### Starting the System

**Method 1: Direct Execution**
```bash
cd AI_robot
source venv/bin/activate
python src/main.py
```

**Method 2: Docker**
```bash
cd AI_robot
docker-compose up -d
```

**Method 3: Systemd**
```bash
sudo systemctl start trading-system
```

### Stopping the System

**Method 1: Direct Execution**
Press `Ctrl+C` in the terminal

**Method 2: Docker**
```bash
docker-compose down
```

**Method 3: Systemd**
```bash
sudo systemctl stop trading-system
```

### Checking Status

**Method 1: Telegram Bot**
Send `/status` command to your bot

**Method 2: Systemd**
```bash
sudo systemctl status trading-system
```

**Method 3: Docker**
```bash
docker-compose ps
```

## Telegram Bot Commands

### Basic Commands

| Command | Description |
|---------|-------------|
| `/start` | Start bot and show menu |
| `/help` | Show help message |
| `/status` | Show system status |
| `/stats` | Show performance statistics |

### Trading Commands

| Command | Description |
|---------|-------------|
| `/trades` | Show open trades |
| `/trades history` | Show trade history |
| `/trades today` | Show today's trades |

### Control Commands

| Command | Description |
|---------|-------------|
| `/pause` | Pause trading |
| `/resume` | Resume trading |
| `/killswitch` | Emergency stop |

### Configuration Commands

| Command | Description |
|---------|-------------|
| `/config` | Show current configuration |
| `/config risk` | Show risk configuration |
| `/config trading` | Show trading configuration |

## System Status

### What's Shown

The `/status` command displays:
- System uptime
- Number of active robots
- Database connection status
- MT5 connection status
- Current balance
- Equity
- Open positions

### Example Output

```
📊 Multi-Robot Trading System

Status: ✅ Running
Uptime: 2 days, 3 hours, 15 minutes

🤖 Active Robots: 10/10
   ✅ Data Collection: 6/6
   ✅ Analysis: 3/3
   ✅ Decision: 1/1
   ✅ Risk: 1/1
   ✅ Execution: 2/2
   ✅ Monitoring: 1/1

💰 Account
   Balance: $1,250.00
   Equity: $1,245.50
   Margin: $125.00
   Free Margin: $1,120.50

📊 Market Data
   Symbol: XAUUSD
   Price: $1,950.25
   Last Update: 2 minutes ago

🔗 Connections
   PostgreSQL: ✅ Connected
   MongoDB: ✅ Connected
   Redis: ✅ Connected
   MT5: ✅ Connected
   Telegram: ✅ Connected
```

## Performance Statistics

### What's Shown

The `/stats` command displays:
- Total trades
- Win rate
- Profit factor
- Total profit/loss
- Max drawdown
- Sharpe ratio
- Daily/weekly/monthly performance

### Example Output

```
📈 Performance Statistics

Total Trades: 156
Win Rate: 58.33%
Profit Factor: 1.45

💰 Profit/Loss
   Total: +$245.50
   Today: +$12.30
   This Week: +$45.60
   This Month: +$125.80

📊 Risk Metrics
   Max Drawdown: 6.2%
   Sharpe Ratio: 1.85
   Profit/Loss Ratio: 1.65

📈 Daily Performance
   Monday: +$5.20 (3 trades)
   Tuesday: +$8.40 (4 trades)
   Wednesday: -$2.10 (2 trades)
   Thursday: +$15.60 (5 trades)
   Friday: +$7.80 (3 trades)
```

## Open Trades

### What's Shown

The `/trades` command displays:
- Trade ID
- Symbol
- Type (BUY/SELL)
- Volume
- Open price
- Current price
- Profit/loss
- Open time
- Stop loss / Take profit

### Example Output

```
💼 Open Trades (3)

1️⃣ Trade #1234
   Symbol: XAUUSD
   Type: BUY
   Volume: 0.10
   Open: $1,945.00
   Current: $1,950.25
   P&L: +$52.50
   Open: 2 hours ago
   SL: $1,940.00 | TP: $1,960.00

2️⃣ Trade #1235
   Symbol: XAUUSD
   Type: SELL
   Volume: 0.10
   Open: $1,948.00
   Current: $1,950.25
   P&L: -$22.50
   Open: 1 hour ago
   SL: $1,953.00 | TP: $1,938.00

3️⃣ Trade #1236
   Symbol: XAUUSD
   Type: BUY
   Volume: 0.15
   Open: $1,947.00
   Current: $1,950.25
   P&L: +$48.75
   Open: 30 minutes ago
   SL: $1,942.00 | TP: $1,955.00

Total P&L: +$78.75
```

## Trading Control

### Pause Trading

```bash
# Via Telegram
/pause

# Or via command
python src/main.py --pause
```

### Resume Trading

```bash
# Via Telegram
/resume

# Or via command
python src/main.py --resume
```

### Emergency Stop (Kill Switch)

```bash
# Via Telegram
/killswitch

# Or via command
python src/main.py --killswitch
```

**Warning:** This will close all open positions and stop all trading activity.

## Configuration

### View Current Configuration

```bash
# Via Telegram
/config

# Or view config file directly
cat config.yaml
```

### Change Risk Profile

Edit `config.yaml`:

```yaml
risk:
  profile: "conservative"  # conservative, moderate, aggressive
```

### Change Trading Style

Edit `config.yaml`:

```yaml
trading:
  style: "day_trading"  # scalping, day_trading, swing_trading
```

### Enable/Disable Robots

Edit `config.yaml`:

```yaml
robots:
  enabled:
    - price_bot
    - structure_bot
    - liquidity_bot
    # ... add/remove robots
```

## Monitoring

### View Logs

**Method 1: Direct**
```bash
tail -f logs/trading.log
```

**Method 2: Systemd**
```bash
journalctl -u trading-system -f
```

**Method 3: Docker**
```bash
docker-compose logs -f
```

### Check System Health

**Method 1: Telegram**
Send `/status` command

**Method 2: Health Check Script**
```bash
./scripts/health_check.sh
```

**Method 3: Dashboard**
Access the web dashboard (if enabled)

## Backtesting

### Run Backtest

```bash
# Basic backtest
python scripts/backtest.py --start 2024-01-01 --end 2024-12-31

# Backtest with specific symbol
python scripts/backtest.py --symbol XAUUSD --start 2024-01-01 --end 2024-12-31

# Backtest with specific timeframe
python scripts/backtest.py --timeframe H1 --start 2024-01-01 --end 2024-12-31

# Backtest with specific robots
python scripts/backtest.py --robots structure_bot,liquidity_bot --start 2024-01-01 --end 2024-12-31
```

### View Backtest Report

```bash
# View in terminal
python scripts/backtest.py --start 2024-01-01 --end 2024-12-31 --report

# Save to file
python scripts/backtest.py --start 2024-01-01 --end 2024-12-31 --output reports/backtest_2024.json
```

## Safety Features

### Kill Switch

The kill switch is enabled by default and can be triggered via:
- Telegram command `/killswitch`
- Maximum drawdown exceeded
- Critical error
- Manual trigger

### Circuit Breaker

The circuit breaker automatically pauses trading when:
- Daily loss limit exceeded
- Weekly loss limit exceeded
- Monthly loss limit exceeded

### Loss Protection

Loss protection automatically pauses trading after:
- Consecutive losses threshold reached
- Configurable pause duration
- Optional automatic resume

## Troubleshooting

### System Won't Start

**Check logs:**
```bash
tail -f logs/trading.log
```

**Common issues:**
- MT5 not installed or not running
- Database connection failed
- Configuration error
- Missing dependencies

### MT5 Connection Failed

**Check:**
1. MT5 terminal is running
2. Account credentials are correct
3. "Allow algorithmic trading" is enabled
4. Internet connection is stable

### Database Connection Failed

**Check:**
1. Database services are running
2. Connection parameters are correct
3. Network connectivity
4. Firewall settings

### Trade Execution Failed

**Check:**
1. Sufficient margin
2. Account type (demo vs live)
3. Broker restrictions
4. Slippage settings

## Best Practices

### Daily Routine

1. Check system status in the morning
2. Review overnight trades
3. Check for any errors or warnings
4. Monitor market conditions

### Weekly Review

1. Review performance statistics
2. Analyze winning/losing trades
3. Identify patterns
4. Adjust parameters if needed

### Monthly Audit

1. Full system review
2. Performance evaluation
3. Risk assessment
4. Security audit

## Support

For issues:
1. Check documentation
2. Review logs
3. Test with demo account first
4. Contact support if needed

## Disclaimer

**IMPORTANT:** This is an automated trading system. Trading involves substantial risk of loss. Use at your own risk.

Always:
- Start with paper trading
- Use conservative risk settings
- Monitor the system
- Understand the strategy
- Never trade with money you cannot afford to lose
