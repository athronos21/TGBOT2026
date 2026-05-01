"""
Backtest Report Generation

Generates comprehensive backtest reports including:
- Performance summary
- Trade log
- Equity curve
- Statistics
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import json
import os


@dataclass
class BacktestReport:
    """Backtest report data"""
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float
    total_profit: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_percent: float
    sharpe_ratio: float
    profit_loss_ratio: float
    average_trade_duration: float
    trades_per_day: float
    trades: List[Dict[str, Any]]
    equity_curve: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'initial_balance': self.initial_balance,
            'final_balance': self.final_balance,
            'total_profit': self.total_profit,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_percent': self.max_drawdown_percent,
            'sharpe_ratio': self.sharpe_ratio,
            'profit_loss_ratio': self.profit_loss_ratio,
            'average_trade_duration': self.average_trade_duration,
            'trades_per_day': self.trades_per_day,
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def save(self, filepath: str) -> None:
        """Save report to file."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(self.to_json())
        logging.info(f"Backtest report saved to {filepath}")


class ReportGenerator:
    """
    Generates comprehensive backtest reports.
    """
    
    def __init__(self):
        """Initialize the report generator."""
        self.logger = logging.getLogger(__name__)
        
    def generate_report(self, symbol: str, timeframe: str, start_date: datetime,
                       end_date: datetime, initial_balance: float,
                       final_balance: float, total_profit: float,
                       total_trades: int, winning_trades: int,
                       losing_trades: int, win_rate: float,
                       profit_factor: float, max_drawdown: float,
                       max_drawdown_percent: float, sharpe_ratio: float,
                       profit_loss_ratio: float, average_trade_duration: float,
                       trades_per_day: float, trades: List[Dict[str, Any]],
                       equity_curve: List[Dict[str, Any]]) -> BacktestReport:
        """
        Generate a backtest report.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            start_date: Backtest start date
            end_date: Backtest end date
            initial_balance: Initial account balance
            final_balance: Final account balance
            total_profit: Total profit/loss
            total_trades: Total number of trades
            winning_trades: Number of winning trades
            losing_trades: Number of losing trades
            win_rate: Win rate percentage
            profit_factor: Profit factor
            max_drawdown: Maximum drawdown
            max_drawdown_percent: Maximum drawdown percentage
            sharpe_ratio: Sharpe ratio
            profit_loss_ratio: Profit/loss ratio
            average_trade_duration: Average trade duration
            trades_per_day: Trades per day
            trades: List of trade details
            equity_curve: Equity curve data
            
        Returns:
            BacktestReport object
        """
        report = BacktestReport(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            final_balance=final_balance,
            total_profit=total_profit,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_percent=max_drawdown_percent,
            sharpe_ratio=sharpe_ratio,
            profit_loss_ratio=profit_loss_ratio,
            average_trade_duration=average_trade_duration,
            trades_per_day=trades_per_day,
            trades=trades,
            equity_curve=equity_curve
        )
        
        return report
        
    def generate_summary(self, report: BacktestReport) -> str:
        """
        Generate a summary string for the report.
        
        Args:
            report: BacktestReport object
            
        Returns:
            Summary string
        """
        lines = [
            "=" * 60,
            "BACKTEST REPORT SUMMARY",
            "=" * 60,
            f"Symbol: {report.symbol}",
            f"Timeframe: {report.timeframe}",
            f"Period: {report.start_date.strftime('%Y-%m-%d')} to {report.end_date.strftime('%Y-%m-%d')}",
            "",
            "ACCOUNT PERFORMANCE",
            "-" * 40,
            f"Initial Balance: ${report.initial_balance:,.2f}",
            f"Final Balance: ${report.final_balance:,.2f}",
            f"Total Profit: ${report.total_profit:,.2f}",
            f"Return: {(report.total_profit / report.initial_balance * 100):.2f}%",
            "",
            "TRADE STATISTICS",
            "-" * 40,
            f"Total Trades: {report.total_trades}",
            f"Winning Trades: {report.winning_trades}",
            f"Losing Trades: {report.losing_trades}",
            f"Win Rate: {report.win_rate:.2f}%",
            f"Profit Factor: {report.profit_factor:.2f}",
            "",
            "RISK METRICS",
            "-" * 40,
            f"Max Drawdown: ${report.max_drawdown:,.2f} ({report.max_drawdown_percent:.2f}%)",
            f"Sharpe Ratio: {report.sharpe_ratio:.2f}",
            f"Profit/Loss Ratio: {report.profit_loss_ratio:.2f}",
            "",
            "TRADE FREQUENCY",
            "-" * 40,
            f"Average Trade Duration: {report.average_trade_duration:.0f} seconds",
            f"Trades Per Day: {report.trades_per_day:.2f}",
            "=" * 60
        ]
        
        return "\n".join(lines)
