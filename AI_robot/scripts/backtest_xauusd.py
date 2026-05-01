#!/usr/bin/env python3
"""
Backtest Script for XAUUSD (Gold) - 2 Year Period

Runs a backtest using the Multi-Robot Trading System backtesting framework
on 2 years of historical XAUUSD data.

Usage:
    python scripts/backtest_xauusd.py [--config config.yaml] [--output docs/backtest_report.json]
"""

import asyncio
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.config_manager import ConfigurationManager
from src.database.postgresql_manager import PostgreSQLManager
from src.backtesting import BacktestEngine, BacktestConfig
from src.backtesting.data_loader import CandleData


def generate_sample_xauusd_data(start_date: datetime, end_date: datetime) -> list:
    """
    Generate sample XAUUSD historical data for backtesting.
    
    Creates realistic gold price data with trends, volatility, and patterns.
    Generates hourly candles for 2 years.
    
    Args:
        start_date: Start date for data
        end_date: End date for data
        
    Returns:
        List of candle data dictionaries
    """
    candles = []
    
    # XAUUSD typical parameters
    initial_price = 1950.0  # Starting price (gold in USD)
    volatility = 5.0  # Hourly volatility in dollars
    trend = 0.01  # Slight upward trend per hour
    
    current_date = start_date
    current_price = initial_price
    
    while current_date <= end_date:
        # Skip weekends
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue
            
        # Generate hourly OHLC data
        hourly_volatility = volatility * random.uniform(0.5, 1.5)
        hourly_trend = trend * random.uniform(-1, 1)
        
        open_price = current_price
        close_price = open_price + hourly_trend + random.uniform(-hourly_volatility, hourly_volatility)
        
        # Generate high and low
        high = max(open_price, close_price) + random.uniform(0, hourly_volatility)
        low = min(open_price, close_price) - random.uniform(0, hourly_volatility)
        
        # Generate volume (higher on volatile days)
        volume = int(100000 + random.uniform(0, 500000) * (hourly_volatility / 2))
        
        # Create candle
        candle = {
            'timestamp': current_date,
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close_price, 2),
            'volume': volume
        }
        candles.append(candle)
        
        # Update for next hour
        current_price = close_price
        current_date += timedelta(hours=1)
        
        # Progress indicator
        if len(candles) % 1000 == 0:
            print(f"Generated {len(candles)} candles...")
    
    print(f"Total candles generated: {len(candles)}")
    return candles


async def load_data_to_database(postgres: PostgreSQLManager, candles: list, 
                                 symbol: str = 'XAUUSD', timeframe: str = 'H1') -> None:
    """
    Load generated candle data into PostgreSQL database.
    
    Args:
        postgres: PostgreSQL manager
        candles: List of candle data dictionaries
        symbol: Trading symbol
        timeframe: Timeframe
    """
    logger = logging.getLogger(__name__)
    
    logger.info(f"Loading {len(candles)} candles into database...")
    
    # Convert to format expected by database
    data_to_insert = []
    for candle in candles:
        data_to_insert.append({
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': candle['timestamp'],
            'open': candle['open'],
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'volume': candle['volume']
        })
    
    # Insert in batches
    batch_size = 1000
    for i in range(0, len(data_to_insert), batch_size):
        batch = data_to_insert[i:i + batch_size]
        await postgres.insert_market_data(batch)
        logger.info(f"Inserted batch {i // batch_size + 1}/{(len(data_to_insert) + batch_size - 1) // batch_size}")
    
    logger.info(f"Loaded {len(candles)} candles into database")


async def run_backtest(config: ConfigurationManager, output_path: str,
                       start_date: datetime, end_date: datetime) -> None:
    """
    Run the XAUUSD backtest.
    
    Args:
        config: Configuration manager
        output_path: Path to save the backtest report
        start_date: Backtest start date
        end_date: Backtest end date
    """
    logger = logging.getLogger(__name__)
    
    # Get database config
    db_config = config.get('database.postgresql', {})
    
    # Create PostgreSQL manager
    postgres = PostgreSQLManager(db_config)
    await postgres.connect()
    
    try:
        # Generate sample data
        logger.info("Generating sample XAUUSD data...")
        candles = generate_sample_xauusd_data(start_date, end_date)
        
        # Load data into database
        logger.info("Loading data into database...")
        await load_data_to_database(postgres, candles)
        
        # Get backtest configuration
        backtest_config = {
            'symbol': 'XAUUSD',
            'timeframe': 'H1',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'initial_balance': 1000.0,
            'leverage': config.get('mt5.leverage', 500),
            'spread': 2.0,
            'commission_rate': 0.0,
            'swap_rate': 0.0,
            'slippage_max': 5.0,
            'robots': [],
            'robot_configs': {}
        }
        
        # Create backtest config
        config_obj = BacktestConfig.from_dict(backtest_config)
        
        logger.info(f"Starting XAUUSD backtest from {start_date} to {end_date}")
        logger.info(f"Initial balance: ${config_obj.initial_balance}")
        
        # Create backtest engine
        engine = BacktestEngine(config_obj, postgres)
        
        # Run backtest
        report = await engine.run()
        
        # Print summary
        engine.print_summary(report)
        
        # Save report
        report.save(output_path)
        
        logger.info(f"Backtest report saved to {output_path}")
        
        # Print key metrics
        metrics = report.to_dict()
        print("\n" + "=" * 60)
        print("KEY METRICS")
        print("=" * 60)
        print(f"Win Rate: {metrics['win_rate']:.2f}%")
        print(f"Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"Max Drawdown: ${metrics['max_drawdown']:,.2f} ({metrics['max_drawdown_percent']:.2f}%)")
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"Total Trades: {metrics['total_trades']}")
        print(f"Winning Trades: {metrics['winning_trades']}")
        print(f"Losing Trades: {metrics['losing_trades']}")
        print("=" * 60)
        
        return report
        
    finally:
        await postgres.disconnect()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='XAUUSD Backtest Script')
    parser.add_argument('--config', '-c', default='config.yaml',
                        help='Path to configuration file')
    parser.add_argument('--output', '-o', default='docs/backtest_report.json',
                        help='Output path for backtest report')
    parser.add_argument('--start', '-s', default='2022-01-01',
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', '-e', default='2023-12-31',
                        help='End date (YYYY-MM-DD)')
    parser.add_argument('--log-level', '-l', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level')
                        
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config_path = Path(args.config)
        if config_path.exists():
            config = ConfigurationManager(str(config_path))
        else:
            logger.warning(f"Config file not found: {args.config}, using defaults")
            config = ConfigurationManager.__new__(ConfigurationManager)
            config._config = {}
        
        # Create output directory
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Parse dates
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
        
        # Run backtest
        asyncio.run(run_backtest(config, str(output_path), start_date, end_date))
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
