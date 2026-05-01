"""
Performance Monitor Bot - Performance Monitoring

Monitors performance including:
- Metrics calculation
- Win rate tracking
- Profit factor tracking
- Drawdown tracking
- Daily/weekly/monthly summaries
- Metrics storage to database
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

from src.core.robot import Robot, RobotInfo, RobotState
from src.core.message_bus import MessageBus
from src.database.postgresql_manager import PostgreSQLManager
from src.database.mongodb_manager import MongoDBManager


@dataclass
class PerformanceMetrics:
    """Performance metrics data"""
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    net_profit: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0


class PerformanceMonitorBot(Robot):
    """
    Monitors trading performance and calculates metrics.
    
    Features:
    - Metrics calculation
    - Win rate tracking
    - Profit factor tracking
    - Drawdown tracking
    - Daily/weekly/monthly summaries
    - Metrics storage to database
    """
    
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.logger = logging.getLogger(__name__)
        self.update_interval = config.get('update_interval', 3600)  # 1 hour
        self.mt5 = None
        self.postgres = None
        self.mongodb = None
        self._trades: List[Dict] = []
        self._daily_trades: Dict[str, List] = defaultdict(list)
        
    async def initialize(self):
        """Initialize the Performance Monitor Bot"""
        self.logger.info(f"Initializing {self.robot_id}...")
        
        self.postgres = PostgreSQLManager(self.config.get('database', {}).get('postgresql', {}))
        self.mongodb = MongoDBManager(self.config.get('database', {}).get('mongodb', {}))
        
        await self.postgres.connect()
        self.mongodb.connect()
        
        # Create tables if not exist
        await self.postgres.create_performance_metrics_table()
        self.mongodb.create_system_logs_collection()
        self.mongodb.create_configurations_collection()
        
        self.logger.info(f"{self.robot_id} initialized successfully")
        
    async def process(self, data: Any) -> Any:
        """Process trade data and update metrics"""
        if data is None:
            return None
            
        trade = data.get('trade') or data
        
        if not trade.get('trade_id') and not trade.get('external_id'):
            return None
            
        # Record trade
        self._record_trade(trade)
        
        # Calculate metrics
        metrics = self._calculate_metrics()
        
        # Store metrics
        await self._store_metrics(metrics)
        
        # Generate summary
        summary = self._generate_summary(metrics)
        
        await self.send_message('performance_update', {
            'metrics': summary,
            'timestamp': datetime.now().isoformat()
        })
        
        return summary
        
    async def cleanup(self):
        """Cleanup resources"""
        if self.postgres:
            await self.postgres.disconnect()
        if self.mongodb:
            self.mongodb.disconnect()
        self.logger.info(f"{self.robot_id} cleaned up")
        
    def _record_trade(self, trade: Dict):
        """Record a trade for metrics calculation"""
        self._trades.append(trade)
        
        # Group by day
        trade_date = trade.get('open_time', datetime.now().isoformat())[:10]
        self._daily_trades[trade_date].append(trade)
        
    def _calculate_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics"""
        if not self._trades:
            return PerformanceMetrics()
            
        # Calculate basic metrics
        total_trades = len(self._trades)
        winning_trades = sum(1 for t in self._trades if t.get('profit_loss', 0) > 0)
        losing_trades = sum(1 for t in self._trades if t.get('profit_loss', 0) < 0)
        
        total_profit = sum(t.get('profit_loss', 0) for t in self._trades if t.get('profit_loss', 0) > 0)
        total_loss = abs(sum(t.get('profit_loss', 0) for t in self._trades if t.get('profit_loss', 0) < 0))
        net_profit = total_profit - total_loss
        
        # Calculate win rate
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        # Calculate profit factor
        profit_factor = total_profit / total_loss if total_loss > 0 else 0.0
        
        # Calculate drawdown
        max_drawdown = self._calculate_drawdown()
        
        # Calculate Sharpe ratio (simplified)
        returns = [t.get('profit_loss', 0) for t in self._trades]
        if len(returns) > 1:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            std_dev = variance ** 0.5
            sharpe_ratio = mean_return / std_dev if std_dev > 0 else 0.0
        else:
            sharpe_ratio = 0.0
            
        return PerformanceMetrics(
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_profit=total_profit,
            total_loss=total_loss,
            net_profit=net_profit,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio
        )
        
    def _calculate_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        if not self._trades:
            return 0.0
            
        # Sort trades by time
        sorted_trades = sorted(self._trades, key=lambda t: t.get('open_time', ''))
        
        # Calculate equity curve
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        
        for trade in sorted_trades:
            equity += trade.get('profit_loss', 0)
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
                
        return max_dd
        
    def _generate_summary(self, metrics: PerformanceMetrics) -> Dict[str, Any]:
        """Generate performance summary"""
        return {
            'win_rate': metrics.win_rate,
            'profit_factor': metrics.profit_factor,
            'total_trades': metrics.total_trades,
            'winning_trades': metrics.winning_trades,
            'losing_trades': metrics.losing_trades,
            'total_profit': metrics.total_profit,
            'total_loss': metrics.total_loss,
            'net_profit': metrics.net_profit,
            'max_drawdown': metrics.max_drawdown,
            'sharpe_ratio': metrics.sharpe_ratio,
            'timestamp': datetime.now().isoformat()
        }
        
    async def _store_metrics(self, metrics: PerformanceMetrics):
        """Store metrics in database"""
        if not self.postgres or not self.mongodb:
            return
            
        try:
            # Store in PostgreSQL
            metric_data = {
                'robot_id': self.robot_id,
                'metric_name': 'performance_summary',
                'metric_value': metrics.net_profit,
                'metric_type': 'currency',
                'timestamp': datetime.now().isoformat(),
                'period_start': (datetime.now() - timedelta(days=30)).isoformat(),
                'period_end': datetime.now().isoformat(),
                'metadata': {
                    'win_rate': metrics.win_rate,
                    'profit_factor': metrics.profit_factor,
                    'total_trades': metrics.total_trades,
                    'max_drawdown': metrics.max_drawdown,
                    'sharpe_ratio': metrics.sharpe_ratio
                }
            }
            await self.postgres.insert_performance_metric(metric_data)
            
            # Log to MongoDB
            log_data = {
                'timestamp': datetime.now(),
                'level': 'INFO',
                'robot_id': self.robot_id,
                'message': f"Performance metrics updated",
                'context': {
                    'win_rate': metrics.win_rate,
                    'profit_factor': metrics.profit_factor,
                    'net_profit': metrics.net_profit,
                    'max_drawdown': metrics.max_drawdown
                }
            }
            self.mongodb.insert_system_log(log_data)
            
        except Exception as e:
            self.logger.error(f"Failed to store metrics: {e}")
            
    async def get_daily_summary(self, date: str = None) -> Dict[str, Any]:
        """Get daily performance summary"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
            
        trades = self._daily_trades.get(date, [])
        
        if not trades:
            return {'date': date, 'trades': 0, 'profit': 0}
            
        profit = sum(t.get('profit_loss', 0) for t in trades)
        wins = sum(1 for t in trades if t.get('profit_loss', 0) > 0)
        losses = sum(1 for t in trades if t.get('profit_loss', 0) < 0)
        
        return {
            'date': date,
            'trades': len(trades),
            'wins': wins,
            'losses': losses,
            'profit': profit
        }
        
    async def get_weekly_summary(self) -> Dict[str, Any]:
        """Get weekly performance summary"""
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        
        weekly_trades = []
        for date, trades in self._daily_trades.items():
            trade_date = datetime.strptime(date, '%Y-%m-%d')
            if trade_date >= week_start:
                weekly_trades.extend(trades)
                
        if not weekly_trades:
            return {'week_start': week_start.strftime('%Y-%m-%d'), 'trades': 0, 'profit': 0}
            
        profit = sum(t.get('profit_loss', 0) for t in weekly_trades)
        wins = sum(1 for t in weekly_trades if t.get('profit_loss', 0) > 0)
        
        return {
            'week_start': week_start.strftime('%Y-%m-%d'),
            'trades': len(weekly_trades),
            'wins': wins,
            'profit': profit
        }
        
    async def get_monthly_summary(self) -> Dict[str, Any]:
        """Get monthly performance summary"""
        today = datetime.now()
        month_start = today.replace(day=1)
        
        monthly_trades = []
        for date, trades in self._daily_trades.items():
            trade_date = datetime.strptime(date, '%Y-%m-%d')
            if trade_date >= month_start:
                monthly_trades.extend(trades)
                
        if not monthly_trades:
            return {'month_start': month_start.strftime('%Y-%m-%d'), 'trades': 0, 'profit': 0}
            
        profit = sum(t.get('profit_loss', 0) for t in monthly_trades)
        wins = sum(1 for t in monthly_trades if t.get('profit_loss', 0) > 0)
        
        return {
            'month_start': month_start.strftime('%Y-%m-%d'),
            'trades': len(monthly_trades),
            'wins': wins,
            'profit': profit
        }
