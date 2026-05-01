#!/usr/bin/env python3
"""
Backtest Runner for Multi-Robot Trading System

Runs backtests on historical data and generates reports.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.config_manager import ConfigurationManager
from src.database.postgresql_manager import PostgreSQLManager
from src.backtesting.engine import BacktestEngine, BacktestConfig
from src.backtesting.simulator import SimulatedExecution


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def run_backtest(config: ConfigurationManager, start_date: datetime, 
                       end_date: datetime, initial_balance: float = 1000.0) -> None:
    """
    Run a backtest.
    
    Args:
        config: Configuration manager
        start_date: Backtest start date
        end_date: Backtest end date
        initial_balance: Initial account balance
    """
    logger = logging.getLogger(__name__)
    
    # Get database config
    db_config = config.get('database.postgresql', {})
    
    # Create PostgreSQL manager
    postgres = PostgreSQLManager(db_config)
    await postgres.connect()
    
    try:
        # Create backtest config
        backtest_config = BacktestConfig(
            symbol='XAUUSD',
            timeframe='H1',
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            leverage=config.get('mt5.leverage', 500),
            spread=2.0,  # pips
            commission_rate=0.0,
            swap_rate=0.0,
            slippage_max=5.0,
            robots=[],
            robot_configs={}
        )
        
        logger.info(f"Starting backtest for XAUUSD H1")
        logger.info(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        logger.info(f"Initial balance: ${initial_balance:,.2f}")
        
        # Create and run backtest engine
        engine = BacktestEngine(backtest_config, postgres)
        report = await engine.run()
        
        # Print summary
        engine.print_summary(report)
        
        # Save report
        report_path = Path(__file__).parent.parent.parent / 'docs' / 'backtest_report.json'
        report.save(str(report_path))
        logger.info(f"Report saved to {report_path}")
        
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
        
    finally:
        await postgres.disconnect()


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run backtest on historical data')
    parser.add_argument('--config', '-c', default='config.yaml',
                        help='Path to configuration file')
    parser.add_argument('--start', '-s', default='2023-01-01',
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', '-e', default='2024-12-31',
                        help='End date (YYYY-MM-DD)')
    parser.add_argument('--balance', '-b', type=float, default=1000.0,
                        help='Initial balance')
    parser.add_argument('--log-level', '-l', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config_path = Path(args.config)
        if not config_path.exists():
            # Try relative to script
            config_path = Path(__file__).parent.parent / args.config
        config = ConfigurationManager(str(config_path))
        
        # Parse dates
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
        
        # Run backtest
        asyncio.run(run_backtest(config, start_date, end_date, args.balance))
        
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
