"""
Backtesting module for the Multi-Robot Trading System

Provides backtesting capabilities including:
- Historical data loading
- Simulated execution
- Performance metrics calculation
- Backtest report generation
"""

from .engine import BacktestEngine
from .data_loader import HistoricalDataLoader
from .simulator import SimulatedExecution
from .metrics import PerformanceMetrics
from .report import BacktestReport

__all__ = ['BacktestEngine', 'HistoricalDataLoader', 'SimulatedExecution', 
           'PerformanceMetrics', 'BacktestReport']
