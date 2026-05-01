# Configuration Management Guide

## Overview

The Multi-Robot Trading System uses a centralized configuration management system that supports:

- YAML-based configuration files
- Environment variable substitution
- Dynamic configuration updates
- Configuration validation
- Configuration watching/callbacks

## Quick Start

### 1. Setup Environment Variables

Copy the `.env.example` file to `.env` and fill in your actual values:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# MetaTrader 5
MT5_PASSWORD=your_actual_password
MT5_ACCOUNT=12345678

# Database
DB_USER=trading_user
DB_PASSWORD=your_postgres_password

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

**Important:** Never commit `.env` to version control!

### 2. Configure Trading Parameters

Edit `config.yaml` to set your trading preferences:

```yaml
trading:
  style: "day_trading"  # scalping, day_trading, swing_trading

risk:
  profile: "moderate"  # conservative, moderate, aggressive
```

### 3. Use Configuration in Code

```python
from src.config.config_manager import ConfigurationManager

# Initialize
config = ConfigurationManager('config.yaml')

# Get values
trading_style = config.get('trading.style')
risk_profile = config.get('risk.profile')

# Get risk configuration for current profile
risk_config = config.get_risk_config()
print(f"Risk per trade: {risk_config['risk_per_trade']}%")
```

## Environment Variable Substitution

The configuration system supports environment variable substitution using the `${VAR}` syntax.

### Basic Substitution

```yaml
database:
  postgresql:
    user: "${DB_USER}"
    password: "${DB_PASSWORD}"
```

### With Default Values

```yaml
system:
  environment: "${ENVIRONMENT:development}"
```

If `ENVIRONMENT` is not set, it defaults to `development`.

### Multiple Variables

```yaml
mt5:
  server: "${MT5_SERVER:ICMarketsSC-Demo}"
  account: "${MT5_ACCOUNT:0}"
  password: "${MT5_PASSWORD}"
```

## Configuration Structure

### System Configuration

```yaml
system:
  name: "Multi-Robot Trading System"
  version: "1.0.0"
  environment: "development"  # development, staging, production
```

### Trading Styles

#### Scalping
```yaml
trading:
  style: "scalping"
  scalping:
    max_trade_duration: 15  # minutes
    min_profit_target: 5    # pips
```

#### Day Trading
```yaml
trading:
  style: "day_trading"
  day_trading:
    close_all_by: "23:00"   # UTC time
    min_profit_target: 10   # pips
```

#### Swing Trading
```yaml
trading:
  style: "swing_trading"
  swing_trading:
    max_trade_duration: 72  # hours
    min_profit_target: 50   # pips
```

### Risk Profiles

#### Conservative
```yaml
risk:
  profile: "conservative"
  conservative:
    risk_per_trade: 0.5  # 0.5% per trade
    max_daily_loss: 2.0  # 2% max daily loss
    max_drawdown: 8.0    # 8% max drawdown
```

#### Moderate
```yaml
risk:
  profile: "moderate"
  moderate:
    risk_per_trade: 1.0
    max_daily_loss: 3.0
    max_drawdown: 10.0
```

#### Aggressive
```yaml
risk:
  profile: "aggressive"
  aggressive:
    risk_per_trade: 2.0
    max_daily_loss: 5.0
    max_drawdown: 15.0
```

## Dynamic Configuration Updates

### Update Single Value

```python
config.set('risk.profile', 'aggressive')
```

### Update Multiple Values

```python
config.update({
    'risk.profile': 'conservative',
    'trading.style': 'day_trading',
    'execution.max_simultaneous_trades': 3
})
```

### Save Configuration

```python
# Save with backup
config.save_config(backup=True)

# Save without backup
config.save_config(backup=False)
```

## Configuration Watching

Register callbacks to be notified when configuration changes:

```python
def on_risk_change(key, value):
    print(f"Risk profile changed to: {value}")
    # Adjust robot behavior...

config.watch('risk.profile', on_risk_change)
```

## Configuration Validation

Validate configuration before using:

```python
try:
    config.validate()
    print("Configuration is valid")
except ValueError as e:
    print(f"Invalid configuration: {e}")
```

## Helper Methods

### Get Risk Configuration

```python
risk_config = config.get_risk_config()
# Returns configuration for current risk profile
```

### Get Trading Configuration

```python
trading_config = config.get_trading_config()
# Returns configuration for current trading style
```

### Get Robot Configuration

```python
price_bot_config = config.get_robot_config('price_bot')
```

### Check if Robot is Enabled

```python
if config.is_robot_enabled('price_bot'):
    # Start price bot
    pass
```

## Robot Configuration

### Enable/Disable Robots

```yaml
robots:
  enabled:
    - price_bot
    - structure_bot
    - liquidity_bot
    # ... add more robots
```

### Robot-Specific Settings

```yaml
robots:
  price_bot:
    update_interval: 1  # seconds
    symbols: ["XAUUSD"]
    
  structure_bot:
    timeframes: ["M15", "H1", "H4"]
    lookback_periods: 100
```

## Safety Configuration

### Trading Limits

```yaml
safety:
  trading_limits:
    max_trades_per_day: 10
    min_time_between_trades: 5  # minutes
    max_trades_per_hour: 3
```

### Loss Protection

```yaml
safety:
  loss_protection:
    pause_after_consecutive_losses: 3
    pause_duration: 60  # minutes
    resume_automatically: true
```

### Kill Switch

```yaml
safety:
  kill_switch:
    enabled: true
    triggers:
      - "telegram_command"
      - "max_drawdown_exceeded"
      - "critical_error"
    action: "close_all_and_pause"
```

## Best Practices

1. **Never commit sensitive data**: Use environment variables for passwords and API keys
2. **Backup before changes**: Always backup configuration before making changes
3. **Validate after updates**: Run validation after updating configuration
4. **Use watchers for critical changes**: Monitor important configuration changes
5. **Test in development**: Test configuration changes in development environment first
6. **Document custom settings**: Add comments to explain custom configuration values

## Example Usage

See `examples/config_usage_example.py` for a complete demonstration of the configuration system.

```bash
python examples/config_usage_example.py
```

## Troubleshooting

### Configuration File Not Found

```
FileNotFoundError: Configuration file not found: config.yaml
```

**Solution:** Ensure `config.yaml` exists in the project root directory.

### Environment Variable Not Set

If an environment variable is not set and has no default, it will be an empty string.

**Solution:** Set the environment variable or provide a default value in `config.yaml`:

```yaml
database:
  user: "${DB_USER:default_user}"
```

### Invalid Configuration

```
ValueError: Invalid risk profile: invalid_profile
```

**Solution:** Use valid values:
- Risk profiles: `conservative`, `moderate`, `aggressive`
- Trading styles: `scalping`, `day_trading`, `swing_trading`

## Security Considerations

1. **File Permissions**: Restrict access to `.env` file:
   ```bash
   chmod 600 .env
   ```

2. **Never Log Sensitive Data**: The configuration manager does not log passwords or API keys

3. **Encrypted Storage**: Consider encrypting sensitive configuration values for production

4. **Access Control**: Limit who can modify configuration files in production

## Related Documentation

- [MT5 Setup Guide](MT5_SETUP.md)
- [System Architecture](../README.md)
- [Robot Development Guide](ROBOT_DEVELOPMENT.md)
