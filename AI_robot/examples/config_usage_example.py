"""
Configuration Manager Usage Example

This script demonstrates how to use the ConfigurationManager
for the Multi-Robot Trading System.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.config_manager import ConfigurationManager


def main():
    """Demonstrate ConfigurationManager usage."""
    
    print("=" * 70)
    print("Configuration Manager Usage Example")
    print("=" * 70)
    
    # Set some environment variables for demonstration
    os.environ['DB_USER'] = 'demo_user'
    os.environ['DB_PASSWORD'] = 'demo_password'
    os.environ['TELEGRAM_BOT_TOKEN'] = 'demo_token_123456'
    os.environ['TELEGRAM_CHAT_ID'] = '123456789'
    
    # Initialize configuration manager
    config = ConfigurationManager('config.yaml')
    
    print("\n1. Basic Configuration Access")
    print("-" * 70)
    print(f"System Name: {config.get('system.name')}")
    print(f"System Version: {config.get('system.version')}")
    print(f"Environment: {config.get('system.environment')}")
    
    print("\n2. Database Configuration (with env var substitution)")
    print("-" * 70)
    print(f"PostgreSQL Host: {config.get('database.postgresql.host')}")
    print(f"PostgreSQL Port: {config.get('database.postgresql.port')}")
    print(f"PostgreSQL User: {config.get('database.postgresql.user')}")
    print(f"PostgreSQL Password: {'*' * len(config.get('database.postgresql.password', ''))}")
    
    print("\n3. Trading Configuration")
    print("-" * 70)
    print(f"Trading Style: {config.get('trading.style')}")
    trading_config = config.get_trading_config()
    print(f"Trading Config: {trading_config}")
    
    print("\n4. Risk Configuration")
    print("-" * 70)
    print(f"Risk Profile: {config.get('risk.profile')}")
    risk_config = config.get_risk_config()
    print(f"Risk per Trade: {risk_config.get('risk_per_trade')}%")
    print(f"Max Daily Loss: {risk_config.get('max_daily_loss')}%")
    print(f"Max Drawdown: {risk_config.get('max_drawdown')}%")
    
    print("\n5. Robot Configuration")
    print("-" * 70)
    enabled_robots = config.get('robots.enabled', [])
    print(f"Enabled Robots ({len(enabled_robots)}):")
    for robot in enabled_robots:
        print(f"  - {robot}: {'✓' if config.is_robot_enabled(robot) else '✗'}")
    
    print("\n6. Dynamic Configuration Updates")
    print("-" * 70)
    print(f"Current Risk Profile: {config.get('risk.profile')}")
    
    # Change risk profile
    config.set('risk.profile', 'aggressive')
    print(f"Updated Risk Profile: {config.get('risk.profile')}")
    
    # Get new risk config
    new_risk_config = config.get_risk_config()
    print(f"New Risk per Trade: {new_risk_config.get('risk_per_trade')}%")
    
    print("\n7. Configuration Watcher Example")
    print("-" * 70)
    
    def on_risk_change(key, value):
        print(f"  [WATCHER] Risk profile changed: {key} = {value}")
    
    config.watch('risk.profile', on_risk_change)
    config.set('risk.profile', 'conservative')
    
    print("\n8. Multiple Updates")
    print("-" * 70)
    updates = {
        'trading.style': 'scalping',
        'risk.profile': 'moderate',
        'execution.max_simultaneous_trades': 5
    }
    print(f"Applying updates: {updates}")
    config.update(updates)
    
    print(f"Trading Style: {config.get('trading.style')}")
    print(f"Risk Profile: {config.get('risk.profile')}")
    print(f"Max Simultaneous Trades: {config.get('execution.max_simultaneous_trades')}")
    
    print("\n9. Configuration Validation")
    print("-" * 70)
    try:
        config.validate()
        print("✓ Configuration is valid")
    except ValueError as e:
        print(f"✗ Configuration validation failed: {e}")
    
    print("\n10. Getting Robot-Specific Configuration")
    print("-" * 70)
    price_bot_config = config.get_robot_config('price_bot')
    print(f"Price Bot Config: {price_bot_config}")
    
    structure_bot_config = config.get_robot_config('structure_bot')
    print(f"Structure Bot Config: {structure_bot_config}")
    
    print("\n" + "=" * 70)
    print("Configuration Manager Demo Complete!")
    print("=" * 70)
    
    # Cleanup environment variables
    del os.environ['DB_USER']
    del os.environ['DB_PASSWORD']
    del os.environ['TELEGRAM_BOT_TOKEN']
    del os.environ['TELEGRAM_CHAT_ID']


if __name__ == '__main__':
    main()
