"""
Backtest Engine for the Multi-Robot Trading System

Main backtesting engine that orchestrates:
- Historical data loading
- Simulated execution
- Performance metrics calculation
- Report generation
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

from .data_loader import HistoricalDataLoader, CandleData
from .simulator import SimulatedExecution, OrderType, OrderStatus
from .metrics import PerformanceMetrics
from .report import ReportGenerator, BacktestReport


@dataclass
class BacktestConfig:
    """Backtest configuration"""
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_balance: float
    leverage: int
    spread: float
    commission_rate: float
    swap_rate: float
    slippage_max: float
    robots: List[str]
    robot_configs: Dict[str, Dict]
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'BacktestConfig':
        """Create config from dictionary."""
        return cls(
            symbol=config.get('symbol', 'XAUUSD'),
            timeframe=config.get('timeframe', 'H1'),
            start_date=datetime.fromisoformat(config.get('start_date', '2023-01-01')),
            end_date=datetime.fromisoformat(config.get('end_date', '2024-01-01')),
            initial_balance=config.get('initial_balance', 1000.0),
            leverage=config.get('leverage', 500),
            spread=config.get('spread', 2.0),
            commission_rate=config.get('commission_rate', 0.0),
            swap_rate=config.get('swap_rate', 0.0),
            slippage_max=config.get('slippage_max', 5.0),
            robots=config.get('robots', []),
            robot_configs=config.get('robot_configs', {})
        )


class BacktestEngine:
    """
    Main backtesting engine for the trading system.
    
    Features:
    - Historical data loading
    - Simulated execution
    - Performance metrics calculation
    - Report generation
    """
    
    def __init__(self, config: BacktestConfig, postgres_manager=None):
        """
        Initialize the backtest engine.
        
        Args:
            config: Backtest configuration
            postgres_manager: PostgreSQL database manager (optional)
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.data_loader = HistoricalDataLoader(postgres_manager)
        self.simulator = SimulatedExecution(
            config={
                'spread': config.spread,
                'commission_rate': config.commission_rate,
                'swap_rate': config.swap_rate,
                'slippage_max': config.slippage_max,
                'leverage': config.leverage,
                'mt5': {}
            },
            initial_balance=config.initial_balance
        )
        self.metrics = PerformanceMetrics()
        self.report_generator = ReportGenerator()
        
        # Backtest state
        self.candles: List[CandleData] = []
        self.current_candle_index = 0
        self.equity_curve: List[Dict[str, Any]] = []
        
    async def initialize(self) -> None:
        """Initialize the backtest engine."""
        self.logger.info("Initializing backtest engine...")
        
        # Load historical data
        await self._load_historical_data()
        
        # Initialize simulator
        await self.simulator.initialize()
        
        self.logger.info("Backtest engine initialized")
        
    async def cleanup(self) -> None:
        """Cleanup the backtest engine."""
        await self.simulator.cleanup()
        self.logger.info("Backtest engine cleaned up")
        
    async def run(self) -> BacktestReport:
        """
        Run the backtest.
        
        Returns:
            BacktestReport object
        """
        self.logger.info(f"Starting backtest for {self.config.symbol} {self.config.timeframe}")
        self.logger.info(f"Period: {self.config.start_date} to {self.config.end_date}")
        
        # Initialize
        await self.initialize()
        
        try:
            # Run backtest
            await self._run_backtest()
            
            # Generate report
            report = self._generate_report()
            
            return report
            
        finally:
            await self.cleanup()
            
    async def _load_historical_data(self) -> None:
        """Load historical data from database."""
        self.candles = await self.data_loader.load_candles(
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            start_date=self.config.start_date,
            end_date=self.config.end_date
        )
        
        self.logger.info(f"Loaded {len(self.candles)} candles for backtesting")
        
    async def _run_backtest(self) -> None:
        """Run the backtest simulation."""
        self.logger.info(f"Running backtest with {len(self.candles)} candles...")
        
        # Process each candle
        for i, candle in enumerate(self.candles):
            self.current_candle_index = i
            
            # Update positions with current price
            current_prices = {self.config.symbol: candle.close}
            closed_positions = await self.simulator.update_positions(current_prices)
            
            # Process closed positions
            for position in closed_positions:
                self.metrics.add_trade(position)
                
            # Record equity
            account_info = self.simulator.get_account_info()
            self.equity_curve.append({
                'timestamp': candle.timestamp,
                'equity': account_info['equity'],
                'balance': account_info['balance'],
                'open_positions': account_info['open_positions']
            })
            
            # Call robot processing (if implemented)
            await self._process_robots(candle)
            
            # Progress logging
            if (i + 1) % 1000 == 0:
                self.logger.info(f"Processed {i + 1}/{len(self.candles)} candles")
                
        self.logger.info(f"Backtest completed. Total trades: {len(self.metrics.trades)}")
        
    async def _process_robots(self, candle: CandleData) -> None:
        """
        Process robots for a candle.
        
        Args:
            candle: Current candle data
        """
        # This is where robot logic would be called
        # For now, it's a placeholder for future implementation
        pass
        
    def _generate_report(self) -> BacktestReport:
        """
        Generate backtest report.
        
        Returns:
            BacktestReport object
        """
        # Get metrics
        metrics_data = self.metrics.get_all_metrics(self.config.initial_balance)
        
        # Calculate trade statistics
        winning_trades = sum(1 for t in self.metrics.trades if t.profit > 0)
        losing_trades = sum(1 for t in self.metrics.trades if t.profit < 0)
        
        # Get final balance
        account_info = self.simulator.get_account_info()
        
        # Generate report
        report = self.report_generator.generate_report(
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            initial_balance=self.config.initial_balance,
            final_balance=account_info['balance'],
            total_profit=metrics_data['total_profit'],
            total_trades=metrics_data['total_trades'],
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=metrics_data['win_rate'],
            profit_factor=metrics_data['profit_factor'],
            max_drawdown=metrics_data['max_drawdown'],
            max_drawdown_percent=metrics_data['max_drawdown_percent'],
            sharpe_ratio=metrics_data['sharpe_ratio'],
            profit_loss_ratio=metrics_data['profit_loss_ratio'],
            average_trade_duration=metrics_data['average_trade_duration'],
            trades_per_day=metrics_data['trades_per_day'],
            trades=[t.to_dict() for t in self.metrics.trades],
            equity_curve=self.equity_curve
        )
        
        return report
        
    def print_summary(self, report: BacktestReport) -> None:
        """
        Print backtest summary.
        
        Args:
            report: BacktestReport object
        """
        summary = self.report_generator.generate_summary(report)
        self.logger.info("\n" + summary)
        
    def save_report(self, report: BacktestReport, filepath: str) -> None:
        """
        Save backtest report to file.
        
        Args:
            report: BacktestReport object
            filepath: Output file path
        """
        report.save(filepath)
