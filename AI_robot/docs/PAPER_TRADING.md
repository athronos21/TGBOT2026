# Paper Trading Setup Guide

## Overview

Paper trading allows you to test the trading system with real market data without risking real money. This guide covers setting up a paper trading environment with a demo MT5 account.

## Prerequisites

- MetaTrader 5 terminal installed
- Demo MT5 account from your broker
- System configured and running

## Step 1: Create Demo MT5 Account

### Option 1: Through MT5 Terminal

1. Open MetaTrader 5 terminal
2. File → Open an Account
3. Select your broker
4. Choose "Demo Account"
5. Fill in the registration form:
   - First name: Your name
   - Last name: Your last name
   - Email: Your email
   - Phone: Your phone number
6. Select account type:
   - Standard (for most trading styles)
   - Micro (for conservative risk)
   - Pro (for advanced features)
7. Set leverage (500:1 is common for demo)
8. Save your credentials

### Option 2: Through Broker Website

1. Visit your broker's website
2. Navigate to "Open Demo Account"
3. Fill in the registration form
4. Download MT5 if not already installed
5. Log in with your demo credentials

## Step 2: Configure System for Paper Trading

### Update Configuration

Edit `config.yaml`:

```yaml
mt5:
  account_type: "demo"  # Set to "demo" for paper trading
  account_number: YOUR_DEMO_ACCOUNT_NUMBER
  server: "YOUR_BROKER_DEMO_SERVER"

trading:
  risk_profile: "conservative"  # Start conservative
  style: "day_trading"  # Or scalping/swing_trading

safety:
  kill_switch:
    enabled: true
  circuit_breaker:
    enabled: true
  loss_protection:
    enabled: true
```

### Set Environment Variables

Edit `.env`:

```bash
MT5_ACCOUNT=YOUR_DEMO_ACCOUNT_NUMBER
MT5_PASSWORD=YOUR_DEMO_PASSWORD
MT5_SERVER=YOUR_BROKER_DEMO_SERVER
```

## Step 3: Configure Risk Profile

### Conservative (Recommended for Paper Trading)

```yaml
risk:
  profile: "conservative"
  conservative:
    risk_per_trade: 0.5  # 0.5% per trade
    max_daily_loss: 2.0  # 2% max daily loss
    max_drawdown: 8.0    # 8% max drawdown
    max_trades_per_day: 10
```

### Moderate

```yaml
risk:
  profile: "moderate"
  moderate:
    risk_per_trade: 1.0
    max_daily_loss: 3.0
    max_drawdown: 10.0
    max_trades_per_day: 15
```

### Aggressive

```yaml
risk:
  profile: "aggressive"
  aggressive:
    risk_per_trade: 2.0
    max_daily_loss: 5.0
    max_drawdown: 15.0
    max_trades_per_day: 20
```

## Step 4: Enable Notifications

### Telegram Notifications

Edit `.env`:

```bash
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_CHAT_ID
```

### Notification Settings

```yaml
notifications:
  enabled: true
  trade_entries: true
  trade_exits: true
  daily_summary: true
  errors: true
  warnings: true
```

## Step 5: Start Paper Trading

### Method 1: Direct Execution

```bash
cd AI_robot
source venv/bin/activate
python src/main.py --mode paper
```

### Method 2: Using Docker

```bash
cd AI_robot
docker-compose up -d
```

### Method 3: Using Systemd

```bash
sudo systemctl start trading-system
```

## Step 6: Monitor Paper Trading

### Daily Review

1. Check Telegram notifications for trade entries/exits
2. Review daily summary
3. Check system status via `/status` command

### Weekly Analysis

1. Review performance metrics
2. Analyze winning/losing trades
3. Identify patterns
4. Adjust parameters if needed

### Monthly Review

1. Evaluate overall performance
2. Check win rate and profit factor
3. Review drawdown
4. Plan next month's strategy

## Step 7: Validate MVP Success Criteria

### Week 1-2: Basic Functionality

- [ ] System starts without errors
- [ ] MT5 connection stable
- [ ] Data collection working
- [ ] Trade execution working
- [ ] Notifications working

### Week 3-4: Performance Validation

- [ ] Win rate > 45%
- [ ] Profit factor > 1.1
- [ ] Max drawdown < 10%
- [ ] System uptime > 99%

### Week 5-6: Stability Validation

- [ ] Win rate > 50%
- [ ] Profit factor > 1.2
- [ ] Max drawdown < 8%
- [ ] System uptime > 99.5%

### Week 7-8: Final Validation

- [ ] Win rate > 55%
- [ ] Profit factor > 1.3
- [ ] Max drawdown < 6%
- [ ] System uptime > 99.9%

## Step 8: Make Adjustments

### If Win Rate is Low

1. Increase confluence requirements
2. Reduce trade frequency
3. Adjust entry zones
4. Review risk parameters

### If Drawdown is High

1. Reduce risk per trade
2. Tighten stop losses
3. Add more safety checks
4. Review position sizing

### If System is Unstable

1. Check logs for errors
2. Verify MT5 connection
3. Review resource usage
4. Consider reducing robot count

## Step 9: Transition to Live Trading

### When Ready

1. Start with minimum capital
2. Use conservative risk profile
3. Monitor closely for first 30 days
4. Gradually increase capital
5. Continue monitoring

### Safety Checklist

- [ ] Paper trading successful (30+ days)
- [ ] Win rate > 50%
- [ ] Profit factor > 1.2
- [ ] Max drawdown < 8%
- [ ] System uptime > 99%
- [ ] Emergency procedures tested
- [ ] Backup systems in place

## Troubleshooting

### MT5 Connection Issues

- Ensure MT5 terminal is running
- Verify account credentials
- Check internet connection
- Try different broker server

### Trade Execution Failures

- Check margin requirements
- Verify account type (demo vs live)
- Review broker restrictions
- Check slippage settings

### Notifications Not Working

- Verify Telegram bot token
- Check chat ID
- Test bot with `/start` command
- Review bot permissions

## Resources

- [MT5 Demo Account Guide](https://www.metatrader5.com/en/terminal/help/demo_accounts)
- [Risk Management](docs/RISK_MANAGEMENT.md)
- [Performance Metrics](docs/PERFORMANCE_METRICS.md)

## Disclaimer

**IMPORTANT:** Paper trading is a simulation. Real trading involves additional factors like:
- Market liquidity
- Execution speed
- Slippage
- Broker policies

Always start with small capital when transitioning to live trading.
