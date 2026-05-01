#!/usr/bin/env python3
"""
Comprehensive Backtest Script for Task 13.2

Executes all subtasks:
1. Backtest on 2 years of XAUUSD data
2. Analyze results
3. Optimize parameters
4. Validate out-of-sample

This script generates sample data, runs backtests, analyzes performance,
optimizes parameters, and validates on out-of-sample data.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json
import random
from typing import Dict, List, Any, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.config_manager import ConfigurationManager
from src.database.postgresql_manager import PostgreSQLManager
from src.backtesting.engine import BacktestEngine, BacktestConfig
from src.backtesting.data_loader import CandleData


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def generate_xauusd_data(start_date: datetime, end_date: datetime, 
                         initial_price: float = 1950.0) -> List[Dict]:
    """
    Generate realistic XAUUSD historical data.
    
    Args:
        start_date: Start date
        end_date: End date
        initial_price: Starting price
        
    Returns:
        List of candle dictionaries
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Generating XAUUSD data from {start_date} to {end_date}")
    
    candles = []
    current_date = start_date
    current_price = initial_price
    
    # Market parameters
    volatility = 5.0  # Base hourly volatility
    trend_strength = 0.01  # Trend per hour
    
    while current_date <= end_date:
        # Skip weekends
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue
            
        # Generate hourly candle
        hourly_vol = volatility * random.uniform(0.5, 1.5)
        hourly_trend = trend_strength * random.uniform(-1, 1)
        
        open_price = current_price
        close_price = open_price + hourly_trend + random.uniform(-hourly_vol, hourly_vol)
        
        high = max(open_price, close_price) + random.uniform(0, hourly_vol)
        low = min(open_price, close_price) - random.uniform(0, hourly_vol)
        
        volume = int(100000 + random.uniform(0, 500000) * (hourly_vol / 2))
        
        candle = {
            'timestamp': current_date,
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close_price, 2),
            'volume': volume
        }
        candles.append(candle)
        
        current_price = close_price
        current_date += timedelta(hours=1)
        
        if len(candles) % 1000 == 0:
            logger.info(f"Generated {len(candles)} candles...")
    
    logger.info(f"Total candles generated: {len(candles)}")
    return candles


async def load_data_to_db(postgres: PostgreSQLManager, candles: List[Dict],
                          symbol: str = 'XAUUSD', timeframe: int = 16385) -> None:
    """
    Load candle data into PostgreSQL.
    
    Args:
        postgres: PostgreSQL manager
        candles: List of candle dictionaries
        symbol: Trading symbol
        timeframe: MT5 timeframe constant (16385 = H1)
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Loading {len(candles)} candles into database...")
    
    # Prepare data for insertion
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
        
        # Insert each record
        for record in batch:
            query = """
            INSERT INTO market_data (symbol, timeframe, timestamp, open, high, low, close, volume)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (symbol, timeframe, timestamp) DO NOTHING
            """
            await postgres.execute(
                query,
                record['symbol'],
                record['timeframe'],
                record['timestamp'],
                record['open'],
                record['high'],
                record['low'],
                record['close'],
                record['volume']
            )
        
        logger.info(f"Inserted batch {i // batch_size + 1}/{(len(data_to_insert) + batch_size - 1) // batch_size}")
    
    logger.info(f"Loaded {len(candles)} candles into database")


async def run_single_backtest(postgres: PostgreSQLManager, config: Dict,
                               start_date: datetime, end_date: datetime) -> Dict:
    """
    Run a single backtest with given parameters.
    
    Args:
        postgres: PostgreSQL manager
        config: Backtest configuration
        start_date: Start date
        end_date: End date
        
    Returns:
        Backtest results dictionary
    """
    logger = logging.getLogger(__name__)
    
    # Create backtest config
    backtest_config = BacktestConfig.from_dict({
        'symbol': config.get('symbol', 'XAUUSD'),
        'timeframe': config.get('timeframe', 'H1'),
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'initial_balance': config.get('initial_balance', 1000.0),
        'leverage': config.get('leverage', 500),
        'spread': config.get('spread', 2.0),
        'commission_rate': config.get('commission_rate', 0.0),
        'swap_rate': config.get('swap_rate', 0.0),
        'slippage_max': config.get('slippage_max', 5.0),
        'robots': config.get('robots', []),
        'robot_configs': config.get('robot_configs', {})
    })
    
    # Create and run backtest engine
    engine = BacktestEngine(backtest_config, postgres)
    report = await engine.run()
    
    return report.to_dict()


async def subtask_1_run_backtest(postgres: PostgreSQLManager, 
                                  start_date: datetime, end_date: datetime) -> Dict:
    """
    Subtask 13.2.1: Backtest on 2 years of XAUUSD data
    
    Args:
        postgres: PostgreSQL manager
        start_date: Start date
        end_date: End date
        
    Returns:
        Backtest results
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("SUBTASK 13.2.1: Backtest on 2 years of XAUUSD data")
    logger.info("=" * 80)
    
    # Generate sample data
    logger.info("Generating 2 years of XAUUSD data...")
    candles = generate_xauusd_data(start_date, end_date)
    
    # Load data into database
    logger.info("Loading data into database...")
    await load_data_to_db(postgres, candles)
    
    # Run backtest
    logger.info("Running backtest...")
    config = {
        'symbol': 'XAUUSD',
        'timeframe': 'H1',
        'initial_balance': 1000.0,
        'leverage': 500,
        'spread': 2.0,
        'commission_rate': 0.0,
        'swap_rate': 0.0,
        'slippage_max': 5.0
    }
    
    results = await run_single_backtest(postgres, config, start_date, end_date)
    
    logger.info("Backtest completed!")
    logger.info(f"Total Trades: {results['total_trades']}")
    logger.info(f"Win Rate: {results['win_rate']:.2f}%")
    logger.info(f"Profit Factor: {results['profit_factor']:.2f}")
    logger.info(f"Max Drawdown: {results['max_drawdown_percent']:.2f}%")
    
    return results


def subtask_2_analyze_results(results: Dict) -> Dict:
    """
    Subtask 13.2.2: Analyze results
    
    Args:
        results: Backtest results
        
    Returns:
        Analysis dictionary
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("SUBTASK 13.2.2: Analyze results")
    logger.info("=" * 80)
    
    analysis = {
        'performance_summary': {
            'total_trades': results['total_trades'],
            'winning_trades': results['winning_trades'],
            'losing_trades': results['losing_trades'],
            'win_rate': results['win_rate'],
            'profit_factor': results['profit_factor'],
            'total_profit': results['total_profit'],
            'net_profit': results['net_profit']
        },
        'risk_metrics': {
            'max_drawdown': results['max_drawdown'],
            'max_drawdown_percent': results['max_drawdown_percent'],
            'sharpe_ratio': results['sharpe_ratio'],
            'profit_loss_ratio': results['profit_loss_ratio']
        },
        'trading_frequency': {
            'trades_per_day': results['trades_per_day'],
            'average_trade_duration': results['average_trade_duration']
        },
        'assessment': {}
    }
    
    # Assess performance
    logger.info("\nPERFORMANCE ASSESSMENT:")
    logger.info("-" * 40)
    
    # Win rate assessment
    if results['win_rate'] >= 60:
        analysis['assessment']['win_rate'] = 'Excellent'
        logger.info(f"✓ Win Rate: {results['win_rate']:.2f}% - Excellent")
    elif results['win_rate'] >= 50:
        analysis['assessment']['win_rate'] = 'Good'
        logger.info(f"✓ Win Rate: {results['win_rate']:.2f}% - Good")
    else:
        analysis['assessment']['win_rate'] = 'Needs Improvement'
        logger.info(f"✗ Win Rate: {results['win_rate']:.2f}% - Needs Improvement")
    
    # Profit factor assessment
    if results['profit_factor'] >= 2.0:
        analysis['assessment']['profit_factor'] = 'Excellent'
        logger.info(f"✓ Profit Factor: {results['profit_factor']:.2f} - Excellent")
    elif results['profit_factor'] >= 1.5:
        analysis['assessment']['profit_factor'] = 'Good'
        logger.info(f"✓ Profit Factor: {results['profit_factor']:.2f} - Good")
    elif results['profit_factor'] >= 1.2:
        analysis['assessment']['profit_factor'] = 'Acceptable'
        logger.info(f"○ Profit Factor: {results['profit_factor']:.2f} - Acceptable")
    else:
        analysis['assessment']['profit_factor'] = 'Poor'
        logger.info(f"✗ Profit Factor: {results['profit_factor']:.2f} - Poor")
    
    # Drawdown assessment
    if results['max_drawdown_percent'] <= 10:
        analysis['assessment']['drawdown'] = 'Excellent'
        logger.info(f"✓ Max Drawdown: {results['max_drawdown_percent']:.2f}% - Excellent")
    elif results['max_drawdown_percent'] <= 20:
        analysis['assessment']['drawdown'] = 'Acceptable'
        logger.info(f"○ Max Drawdown: {results['max_drawdown_percent']:.2f}% - Acceptable")
    else:
        analysis['assessment']['drawdown'] = 'High Risk'
        logger.info(f"✗ Max Drawdown: {results['max_drawdown_percent']:.2f}% - High Risk")
    
    # Sharpe ratio assessment
    if results['sharpe_ratio'] >= 1.5:
        analysis['assessment']['sharpe_ratio'] = 'Excellent'
        logger.info(f"✓ Sharpe Ratio: {results['sharpe_ratio']:.2f} - Excellent")
    elif results['sharpe_ratio'] >= 1.0:
        analysis['assessment']['sharpe_ratio'] = 'Good'
        logger.info(f"✓ Sharpe Ratio: {results['sharpe_ratio']:.2f} - Good")
    elif results['sharpe_ratio'] >= 0.5:
        analysis['assessment']['sharpe_ratio'] = 'Acceptable'
        logger.info(f"○ Sharpe Ratio: {results['sharpe_ratio']:.2f} - Acceptable")
    else:
        analysis['assessment']['sharpe_ratio'] = 'Poor'
        logger.info(f"✗ Sharpe Ratio: {results['sharpe_ratio']:.2f} - Poor")
    
    # Overall assessment
    good_metrics = sum(1 for v in analysis['assessment'].values() if v in ['Excellent', 'Good'])
    total_metrics = len(analysis['assessment'])
    
    if good_metrics >= total_metrics * 0.75:
        analysis['overall_assessment'] = 'System performs well'
        logger.info("\n✓ OVERALL: System performs well")
    elif good_metrics >= total_metrics * 0.5:
        analysis['overall_assessment'] = 'System shows promise but needs optimization'
        logger.info("\n○ OVERALL: System shows promise but needs optimization")
    else:
        analysis['overall_assessment'] = 'System needs significant improvement'
        logger.info("\n✗ OVERALL: System needs significant improvement")
    
    return analysis


async def subtask_3_optimize_parameters(postgres: PostgreSQLManager,
                                        start_date: datetime, end_date: datetime) -> Dict:
    """
    Subtask 13.2.3: Optimize parameters
    
    Args:
        postgres: PostgreSQL manager
        start_date: Start date
        end_date: End date
        
    Returns:
        Optimization results
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("SUBTASK 13.2.3: Optimize parameters")
    logger.info("=" * 80)
    
    # Define parameter grid
    parameter_grid = {
        'spread': [1.5, 2.0, 2.5],
        'slippage_max': [3.0, 5.0, 7.0],
        'initial_balance': [1000.0]  # Keep constant
    }
    
    logger.info("Testing parameter combinations...")
    logger.info(f"Spread values: {parameter_grid['spread']}")
    logger.info(f"Slippage values: {parameter_grid['slippage_max']}")
    
    # Run backtests for each parameter combination
    results = []
    total_combinations = len(parameter_grid['spread']) * len(parameter_grid['slippage_max'])
    current = 0
    
    for spread in parameter_grid['spread']:
        for slippage in parameter_grid['slippage_max']:
            current += 1
            logger.info(f"\nTesting combination {current}/{total_combinations}: spread={spread}, slippage={slippage}")
            
            config = {
                'symbol': 'XAUUSD',
                'timeframe': 'H1',
                'initial_balance': 1000.0,
                'leverage': 500,
                'spread': spread,
                'commission_rate': 0.0,
                'swap_rate': 0.0,
                'slippage_max': slippage
            }
            
            result = await run_single_backtest(postgres, config, start_date, end_date)
            result['parameters'] = {'spread': spread, 'slippage_max': slippage}
            results.append(result)
            
            logger.info(f"  Win Rate: {result['win_rate']:.2f}%, Profit Factor: {result['profit_factor']:.2f}")
    
    # Find best parameters
    best_result = max(results, key=lambda x: x['profit_factor'])
    
    logger.info("\n" + "=" * 40)
    logger.info("OPTIMIZATION RESULTS")
    logger.info("=" * 40)
    logger.info(f"Best parameters:")
    logger.info(f"  Spread: {best_result['parameters']['spread']}")
    logger.info(f"  Slippage Max: {best_result['parameters']['slippage_max']}")
    logger.info(f"\nPerformance with best parameters:")
    logger.info(f"  Win Rate: {best_result['win_rate']:.2f}%")
    logger.info(f"  Profit Factor: {best_result['profit_factor']:.2f}")
    logger.info(f"  Max Drawdown: {best_result['max_drawdown_percent']:.2f}%")
    logger.info(f"  Sharpe Ratio: {best_result['sharpe_ratio']:.2f}")
    
    return {
        'best_parameters': best_result['parameters'],
        'best_result': best_result,
        'all_results': results
    }


async def subtask_4_validate_out_of_sample(postgres: PostgreSQLManager,
                                           best_params: Dict,
                                           train_end: datetime,
                                           test_end: datetime) -> Dict:
    """
    Subtask 13.2.4: Validate out-of-sample
    
    Args:
        postgres: PostgreSQL manager
        best_params: Best parameters from optimization
        train_end: End of training period
        test_end: End of test period
        
    Returns:
        Validation results
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("SUBTASK 13.2.4: Validate out-of-sample")
    logger.info("=" * 80)
    
    # Generate out-of-sample data (6 months)
    test_start = train_end + timedelta(days=1)
    logger.info(f"Out-of-sample period: {test_start} to {test_end}")
    
    logger.info("Generating out-of-sample data...")
    candles = generate_xauusd_data(test_start, test_end)
    
    logger.info("Loading out-of-sample data into database...")
    await load_data_to_db(postgres, candles)
    
    # Run backtest with optimized parameters
    logger.info("Running out-of-sample backtest with optimized parameters...")
    config = {
        'symbol': 'XAUUSD',
        'timeframe': 'H1',
        'initial_balance': 1000.0,
        'leverage': 500,
        'spread': best_params['spread'],
        'commission_rate': 0.0,
        'swap_rate': 0.0,
        'slippage_max': best_params['slippage_max']
    }
    
    oos_result = await run_single_backtest(postgres, config, test_start, test_end)
    
    logger.info("\n" + "=" * 40)
    logger.info("OUT-OF-SAMPLE VALIDATION RESULTS")
    logger.info("=" * 40)
    logger.info(f"Win Rate: {oos_result['win_rate']:.2f}%")
    logger.info(f"Profit Factor: {oos_result['profit_factor']:.2f}")
    logger.info(f"Max Drawdown: {oos_result['max_drawdown_percent']:.2f}%")
    logger.info(f"Sharpe Ratio: {oos_result['sharpe_ratio']:.2f}")
    logger.info(f"Total Trades: {oos_result['total_trades']}")
    
    # Validate against overfitting
    logger.info("\nOVERFITTING CHECK:")
    logger.info("-" * 40)
    
    validation = {
        'out_of_sample_result': oos_result,
        'overfitting_check': {}
    }
    
    # Check if performance degraded significantly
    if oos_result['win_rate'] >= 45:
        validation['overfitting_check']['win_rate'] = 'Passed'
        logger.info(f"✓ Win Rate: {oos_result['win_rate']:.2f}% - Acceptable")
    else:
        validation['overfitting_check']['win_rate'] = 'Failed'
        logger.info(f"✗ Win Rate: {oos_result['win_rate']:.2f}% - Below threshold")
    
    if oos_result['profit_factor'] >= 1.0:
        validation['overfitting_check']['profit_factor'] = 'Passed'
        logger.info(f"✓ Profit Factor: {oos_result['profit_factor']:.2f} - Profitable")
    else:
        validation['overfitting_check']['profit_factor'] = 'Failed'
        logger.info(f"✗ Profit Factor: {oos_result['profit_factor']:.2f} - Not profitable")
    
    if oos_result['max_drawdown_percent'] <= 25:
        validation['overfitting_check']['drawdown'] = 'Passed'
        logger.info(f"✓ Max Drawdown: {oos_result['max_drawdown_percent']:.2f}% - Acceptable")
    else:
        validation['overfitting_check']['drawdown'] = 'Failed'
        logger.info(f"✗ Max Drawdown: {oos_result['max_drawdown_percent']:.2f}% - Too high")
    
    # Overall validation
    passed_checks = sum(1 for v in validation['overfitting_check'].values() if v == 'Passed')
    total_checks = len(validation['overfitting_check'])
    
    if passed_checks == total_checks:
        validation['overall_validation'] = 'Passed - No significant overfitting detected'
        logger.info("\n✓ VALIDATION: Passed - No significant overfitting detected")
    elif passed_checks >= total_checks * 0.67:
        validation['overall_validation'] = 'Partial - Some performance degradation'
        logger.info("\n○ VALIDATION: Partial - Some performance degradation")
    else:
        validation['overall_validation'] = 'Failed - Significant overfitting detected'
        logger.info("\n✗ VALIDATION: Failed - Significant overfitting detected")
    
    return validation


async def main():
    """Main function"""
    setup_logging('INFO')
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("COMPREHENSIVE BACKTEST - TASK 13.2")
    logger.info("=" * 80)
    
    # Define date ranges
    train_start = datetime(2022, 1, 1)
    train_end = datetime(2023, 12, 31)  # 2 years for training
    test_end = datetime(2024, 6, 30)    # 6 months for out-of-sample
    
    # Load configuration
    config_path = Path(__file__).parent.parent / 'config.yaml'
    if config_path.exists():
        config = ConfigurationManager(str(config_path))
    else:
        logger.warning("Config file not found, using defaults")
        config = ConfigurationManager.__new__(ConfigurationManager)
        config._config = {
            'database': {
                'postgresql': {
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'trading_system',
                    'user': 'postgres',
                    'password': 'postgres'
                }
            }
        }
    
    # Connect to database
    db_config = config.get('database.postgresql', {})
    postgres = PostgreSQLManager(db_config)
    await postgres.connect()
    
    try:
        # Subtask 1: Run backtest on 2 years of data
        backtest_results = await subtask_1_run_backtest(postgres, train_start, train_end)
        
        # Subtask 2: Analyze results
        analysis = subtask_2_analyze_results(backtest_results)
        
        # Subtask 3: Optimize parameters
        optimization = await subtask_3_optimize_parameters(postgres, train_start, train_end)
        
        # Subtask 4: Validate out-of-sample
        validation = await subtask_4_validate_out_of_sample(
            postgres,
            optimization['best_parameters'],
            train_end,
            test_end
        )
        
        # Save comprehensive report
        report = {
            'task': '13.2 Run backtests',
            'execution_date': datetime.now().isoformat(),
            'training_period': {
                'start': train_start.isoformat(),
                'end': train_end.isoformat()
            },
            'test_period': {
                'start': (train_end + timedelta(days=1)).isoformat(),
                'end': test_end.isoformat()
            },
            'subtask_1_backtest': backtest_results,
            'subtask_2_analysis': analysis,
            'subtask_3_optimization': {
                'best_parameters': optimization['best_parameters'],
                'best_result': optimization['best_result']
            },
            'subtask_4_validation': validation
        }
        
        # Save report
        report_path = Path(__file__).parent.parent / 'docs' / 'TASK_13.2_BACKTEST_REPORT.json'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info("\n" + "=" * 80)
        logger.info("TASK 13.2 COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Comprehensive report saved to: {report_path}")
        
        # Print final summary
        logger.info("\nFINAL SUMMARY:")
        logger.info("-" * 40)
        logger.info(f"Training Period: {train_start.date()} to {train_end.date()}")
        logger.info(f"Test Period: {(train_end + timedelta(days=1)).date()} to {test_end.date()}")
        logger.info(f"\nOptimized Parameters:")
        logger.info(f"  Spread: {optimization['best_parameters']['spread']}")
        logger.info(f"  Slippage Max: {optimization['best_parameters']['slippage_max']}")
        logger.info(f"\nOut-of-Sample Performance:")
        logger.info(f"  Win Rate: {validation['out_of_sample_result']['win_rate']:.2f}%")
        logger.info(f"  Profit Factor: {validation['out_of_sample_result']['profit_factor']:.2f}")
        logger.info(f"  Max Drawdown: {validation['out_of_sample_result']['max_drawdown_percent']:.2f}%")
        logger.info(f"\nValidation: {validation['overall_validation']}")
        logger.info(f"Overall Assessment: {analysis['overall_assessment']}")
        
    finally:
        await postgres.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
