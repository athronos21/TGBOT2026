"""
Performance Metrics for Backtesting

Calculates performance metrics for backtest results.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import math


@dataclass
class TradeResult:
    """Trade result data"""
    symbol: str
    order_type: str
    volume: float
    open_price: float
    close_price: float
    profit: float
    commission: float
    swap: float
    slippage: float
    open_time: datetime
    close_time: datetime
    duration_seconds: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'order_type': self.order_type,
            'volume': self.volume,
            'open_price': self.open_price,
            'close_price': self.close_price,
            'profit': self.profit,
            'commission': self.commission,
            'swap': self.swap,
            'slippage': self.slippage,
            'open_time': self.open_time.isoformat(),
            'close_time': self.close_time.isoformat(),
            'duration_seconds': self.duration_seconds
        }


class PerformanceMetrics:
    """
    Calculates performance metrics for backtest results.
    
    Metrics include:
    - Total profit/loss
    - Win rate
    - Profit factor
    - Drawdown
    - Sharpe ratio
    - Trade statistics
    """
    
    def __init__(self):
        """Initialize the performance metrics calculator."""
        self.logger = logging.getLogger(__name__)
        self.trades: List[TradeResult] = []
        
    def add_trade(self, trade: Dict[str, Any]) -> None:
        """
        Add a trade to the metrics calculation.
        
        Args:
            trade: Trade result dictionary
        """
        open_time = trade.get('open_time')
        close_time = trade.get('close_time')
        
        if isinstance(open_time, str):
            open_time = datetime.fromisoformat(open_time)
        if isinstance(close_time, str):
            close_time = datetime.fromisoformat(close_time)
            
        duration = 0.0
        if open_time and close_time:
            duration = (close_time - open_time).total_seconds()
            
        trade_result = TradeResult(
            symbol=trade.get('symbol', 'UNKNOWN'),
            order_type=trade.get('order_type', 'UNKNOWN'),
            volume=trade.get('volume', 0.0),
            open_price=trade.get('open_price', 0.0),
            close_price=trade.get('close_price', 0.0),
            profit=trade.get('profit', 0.0),
            commission=trade.get('commission', 0.0),
            swap=trade.get('swap', 0.0),
            slippage=trade.get('slippage', 0.0),
            open_time=open_time,
            close_time=close_time,
            duration_seconds=duration
        )
        
        self.trades.append(trade_result)
        
    def calculate_total_profit(self) -> float:
        """Calculate total profit/loss."""
        return sum(trade.profit for trade in self.trades)
        
    def calculate_total_commission(self) -> float:
        """Calculate total commission."""
        return sum(trade.commission for trade in self.trades)
        
    def calculate_total_swap(self) -> float:
        """Calculate total swap."""
        return sum(trade.swap for trade in self.trades)
        
    def calculate_total_slippage(self) -> float:
        """Calculate total slippage."""
        return sum(trade.slippage for trade in self.trades)
        
    def calculate_win_rate(self) -> float:
        """Calculate win rate (percentage of profitable trades)."""
        if not self.trades:
            return 0.0
            
        winning_trades = sum(1 for trade in self.trades if trade.profit > 0)
        return (winning_trades / len(self.trades)) * 100
        
    def calculate_profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)."""
        if not self.trades:
            return 0.0
            
        gross_profit = sum(trade.profit for trade in self.trades if trade.profit > 0)
        gross_loss = abs(sum(trade.profit for trade in self.trades if trade.profit < 0))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
            
        return gross_profit / gross_loss
        
    def calculate_max_drawdown(self, initial_balance: float = 1000.0) -> Dict[str, Any]:
        """
        Calculate maximum drawdown.
        
        Args:
            initial_balance: Initial account balance
            
        Returns:
            Dictionary with max drawdown information
        """
        if not self.trades:
            return {
                'max_drawdown': 0.0,
                'max_drawdown_percent': 0.0,
                'drawdown_start': None,
                'drawdown_end': None
            }
            
        # Calculate equity curve
        equity = initial_balance
        peak_equity = initial_balance
        max_dd = 0.0
        max_dd_start = None
        max_dd_end = None
        
        for trade in self.trades:
            equity += trade.profit
            if equity > peak_equity:
                peak_equity = equity
            else:
                drawdown = peak_equity - equity
                if drawdown > max_dd:
                    max_dd = drawdown
                    max_dd_start = trade.open_time
                    max_dd_end = trade.close_time
                    
        max_dd_percent = (max_dd / peak_equity * 100) if peak_equity > 0 else 0.0
        
        return {
            'max_drawdown': max_dd,
            'max_drawdown_percent': max_dd_percent,
            'drawdown_start': max_dd_start,
            'drawdown_end': max_dd_end
        }
        
    def calculate_sharpe_ratio(self, initial_balance: float = 1000.0,
                              risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sharpe ratio.
        
        Args:
            initial_balance: Initial account balance
            risk_free_rate: Annual risk-free rate
            
        Returns:
            Sharpe ratio
        """
        if len(self.trades) < 2:
            return 0.0
            
        # Calculate returns
        equity = initial_balance
        returns = []
        
        for trade in self.trades:
            prev_equity = equity
            equity += trade.profit
            if prev_equity > 0:
                return_pct = (equity - prev_equity) / prev_equity
                returns.append(return_pct)
                
        if not returns:
            return 0.0
            
        # Calculate mean and std of returns
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_return = math.sqrt(variance)
        
        if std_return == 0:
            return 0.0
            
        # Annualize (assuming daily returns)
        annualized_return = mean_return * 252
        annualized_std = std_return * math.sqrt(252)
        
        sharpe = (annualized_return - risk_free_rate) / annualized_std
        return sharpe
        
    def calculate_average_profit(self) -> float:
        """Calculate average profit per trade."""
        if not self.trades:
            return 0.0
        return self.calculate_total_profit() / len(self.trades)
        
    def calculate_average_loss(self) -> float:
        """Calculate average loss per losing trade."""
        losing_trades = [t for t in self.trades if t.profit < 0]
        if not losing_trades:
            return 0.0
        return abs(sum(t.profit for t in losing_trades) / len(losing_trades))
        
    def calculate_profit_loss_ratio(self) -> float:
        """Calculate profit/loss ratio."""
        avg_profit = self.calculate_average_profit()
        avg_loss = self.calculate_average_loss()
        
        if avg_loss == 0:
            return float('inf') if avg_profit > 0 else 0.0
            
        return avg_profit / avg_loss
        
    def calculate_average_trade_duration(self) -> float:
        """Calculate average trade duration in seconds."""
        if not self.trades:
            return 0.0
        return sum(t.duration_seconds for t in self.trades) / len(self.trades)
        
    def calculate_trades_per_day(self) -> float:
        """Calculate average trades per day."""
        if not self.trades or len(self.trades) < 2:
            return 0.0
            
        # Get date range
        open_times = [t.open_time for t in self.trades if t.open_time]
        close_times = [t.close_time for t in self.trades if t.close_time]
        
        if not open_times or not close_times:
            return 0.0
            
        start_date = min(open_times)
        end_date = max(close_times)
        
        days = (end_date - start_date).days
        if days == 0:
            days = 1
            
        return len(self.trades) / days
        
    def get_buy_vs_sell_stats(self) -> Dict[str, Any]:
        """Get statistics separated by buy and sell trades."""
        buy_trades = [t for t in self.trades if t.order_type == 'BUY']
        sell_trades = [t for t in self.trades if t.order_type == 'SELL']
        
        return {
            'buy': {
                'count': len(buy_trades),
                'total_profit': sum(t.profit for t in buy_trades),
                'win_rate': (sum(1 for t in buy_trades if t.profit > 0) / len(buy_trades) * 100) if buy_trades else 0
            },
            'sell': {
                'count': len(sell_trades),
                'total_profit': sum(t.profit for t in sell_trades),
                'win_rate': (sum(1 for t in sell_trades if t.profit > 0) / len(sell_trades) * 100) if sell_trades else 0
            }
        }
        
    def get_all_metrics(self, initial_balance: float = 1000.0) -> Dict[str, Any]:
        """
        Get all performance metrics.
        
        Args:
            initial_balance: Initial account balance
            
        Returns:
            Dictionary with all metrics
        """
        total_profit = self.calculate_total_profit()
        max_dd = self.calculate_max_drawdown(initial_balance)
        
        return {
            'total_trades': len(self.trades),
            'total_profit': total_profit,
            'total_commission': self.calculate_total_commission(),
            'total_swap': self.calculate_total_swap(),
            'total_slippage': self.calculate_total_slippage(),
            'net_profit': total_profit - self.calculate_total_commission() - self.calculate_total_swap(),
            'win_rate': self.calculate_win_rate(),
            'profit_factor': self.calculate_profit_factor(),
            'max_drawdown': max_dd['max_drawdown'],
            'max_drawdown_percent': max_dd['max_drawdown_percent'],
            'sharpe_ratio': self.calculate_sharpe_ratio(initial_balance),
            'profit_loss_ratio': self.calculate_profit_loss_ratio(),
            'average_trade_duration': self.calculate_average_trade_duration(),
            'trades_per_day': self.calculate_trades_per_day(),
            'buy_vs_sell': self.get_buy_vs_sell_stats()
        }
