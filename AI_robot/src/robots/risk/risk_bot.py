"""
Risk Bot - Risk Management

Manages risk including:
- Position size calculation
- Risk validation
- Account balance checking
- Daily loss limit checking
- Max drawdown checking
- Risk profile support
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum

from src.core.robot import Robot, RobotInfo, RobotState
from src.core.message_bus import MessageBus
from src.database.postgresql_manager import PostgreSQLManager
from src.database.mongodb_manager import MongoDBManager


class RiskProfile(Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass
class RiskResult:
    """Risk check result"""
    is_valid: bool
    reason: str
    risk_amount: float = 0.0
    lot_size: float = 0.0


class RiskBot(Robot):
    """
    Manages risk for all trades.
    
    Features:
    - Position size calculation
    - Risk validation
    - Account balance checking
    - Daily loss limit checking
    - Max drawdown checking
    - Risk profile support
    """
    
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.logger = logging.getLogger(__name__)
        self.risk_profile = config.get('risk_profile', 'moderate')
        self.mt5 = None
        self.postgres = None
        self.mongodb = None
        self._account_info = None
        self._daily_pnl = 0.0
        self._max_drawdown = 0.0
        self._daily_trades = 0
        self._daily_losses = 0
        
    async def initialize(self):
        """Initialize the Risk Bot"""
        self.logger.info(f"Initializing {self.robot_id}...")
        
        from src.integrations.mt5_connection import MT5Connection
        self.mt5 = MT5Connection(self.config.get('mt5', {}))
        
        self.postgres = PostgreSQLManager(self.config.get('database', {}).get('postgresql', {}))
        self.mongodb = MongoDBManager(self.config.get('database', {}).get('mongodb', {}))
        
        await self.postgres.connect()
        self.mongodb.connect()
        
        self.mongodb.create_system_logs_collection()
        self.mongodb.create_configurations_collection()
        
        # Load risk profile
        self._load_risk_profile()
        
        self.logger.info(f"{self.robot_id} initialized successfully")
        
    async def process(self, data: Any) -> Any:
        """Process signal and validate risk"""
        if data is None:
            return None
            
        signal = data.get('signal') or data
        
        # Validate risk
        result = self.validate_risk(signal)
        
        if not result.is_valid:
            await self.send_message('risk_rejected', {
                'signal_id': signal.get('signal_id'),
                'reason': result.reason
            })
            return None
            
        # Calculate position size
        result = self.calculate_position_size(signal, result.risk_amount)
        
        # Update account info
        await self._update_account_info()
        
        # Validate against account limits
        if not self.validate_account_limits(result.lot_size):
            await self.send_message('risk_rejected', {
                'signal_id': signal.get('signal_id'),
                'reason': 'Account limits exceeded'
            })
            return None
            
        risk_approved_signal = {
            **signal,
            'lot_size': result.lot_size,
            'risk_amount': result.risk_amount,
            'risk_approved': True
        }
        
        await self.send_message('risk_approved', risk_approved_signal)
        return risk_approved_signal
        
    async def cleanup(self):
        """Cleanup resources"""
        if self.postgres:
            await self.postgres.disconnect()
        if self.mongodb:
            self.mongodb.disconnect()
        self.logger.info(f"{self.robot_id} cleaned up")
        
    def _load_risk_profile(self):
        """Load risk profile from config"""
        profiles = {
            'conservative': {
                'risk_per_trade': 0.5,  # 0.5% of account
                'max_daily_loss': 2.0,  # 2% max daily loss
                'max_drawdown': 8.0,    # 8% max drawdown
                'max_trades_per_day': 5
            },
            'moderate': {
                'risk_per_trade': 1.0,
                'max_daily_loss': 3.0,
                'max_drawdown': 10.0,
                'max_trades_per_day': 10
            },
            'aggressive': {
                'risk_per_trade': 2.0,
                'max_daily_loss': 5.0,
                'max_drawdown': 15.0,
                'max_trades_per_day': 15
            }
        }
        self.risk_limits = profiles.get(self.risk_profile, profiles['moderate'])
        
    async def _update_account_info(self):
        """Update account information from MT5"""
        if self.mt5 and self.mt5.is_connected():
            account_info = await self.mt5.get_account_info()
            if account_info:
                self._account_info = {
                    'balance': account_info.balance,
                    'equity': account_info.equity,
                    'margin': account_info.margin,
                    'free_margin': account_info.margin_free,
                    'margin_level': account_info.margin_level
                }
                
    def validate_risk(self, signal: Dict) -> RiskResult:
        """Validate risk for a signal"""
        if not self._account_info:
            return RiskResult(False, "Account info not available")
            
        account_balance = self._account_info.get('balance', 0)
        
        # Get risk per trade from profile
        risk_per_trade = self.risk_limits['risk_per_trade'] / 100
        risk_amount = account_balance * risk_per_trade
        
        # Check daily loss limit
        if self._daily_losses >= self.risk_limits['max_daily_loss']:
            return RiskResult(False, "Daily loss limit reached")
            
        # Check max drawdown
        if self._max_drawdown >= self.risk_limits['max_drawdown']:
            return RiskResult(False, "Max drawdown limit reached")
            
        # Check daily trade limit
        if self._daily_trades >= self.risk_limits['max_trades_per_day']:
            return RiskResult(False, "Daily trade limit reached")
            
        return RiskResult(True, "Risk valid", risk_amount)
        
    def calculate_position_size(self, signal: Dict, risk_amount: float) -> RiskResult:
        """Calculate position size based on risk"""
        entry_mid = signal.get('entry_zone', {}).get('mid', 0)
        stop_loss = signal.get('stop_loss', 0)
        
        if entry_mid == 0 or stop_loss == 0:
            return RiskResult(False, "Invalid entry or stop loss")
            
        # Calculate pip distance
        pip_distance = abs(entry_mid - stop_loss)
        
        # Calculate lot size (simplified - 1 lot = $10 per pip for XAUUSD)
        # Adjust based on symbol
        symbol = signal.get('symbol', 'XAUUSD')
        pip_value = 10.0 if symbol == 'XAUUSD' else 1.0
        
        # Lot size = risk_amount / (pip_distance * pip_value)
        lot_size = risk_amount / (pip_distance * pip_value)
        
        # Apply minimum lot size
        min_lot = 0.01
        lot_size = max(lot_size, min_lot)
        
        return RiskResult(True, "Position size calculated", risk_amount, lot_size)
        
    def validate_account_limits(self, lot_size: float) -> bool:
        """Validate position size against account limits"""
        if not self._account_info:
            return False
            
        account_balance = self._account_info.get('balance', 0)
        margin_required = lot_size * 100  # Simplified margin calculation
        
        # Check margin
        if margin_required > self._account_info.get('free_margin', 0):
            return False
            
        # Check margin level
        if self._account_info.get('margin_level', 0) < 100:
            return False
            
        return True
        
    def record_trade(self, signal: Dict, result: str):
        """Record trade result for risk tracking"""
        self._daily_trades += 1
        
        if result == 'loss':
            self._daily_losses += 1
            
        # Update daily PnL
        pnl = signal.get('profit_loss', 0)
        self._daily_pnl += pnl
        
        # Update max drawdown
        if self._daily_pnl < 0 and abs(self._daily_pnl) > self._max_drawdown:
            self._max_drawdown = abs(self._daily_pnl)
            
    async def get_risk_status(self) -> Dict[str, Any]:
        """Get current risk status"""
        return {
            'account_balance': self._account_info.get('balance', 0) if self._account_info else 0,
            'daily_pnl': self._daily_pnl,
            'daily_trades': self._daily_trades,
            'daily_losses': self._daily_losses,
            'max_drawdown': self._max_drawdown,
            'risk_profile': self.risk_profile,
            'risk_limits': self.risk_limits
        }
        
    async def _store_risk_status(self):
        """Store risk status in database"""
        if not self.postgres or not self.mongodb:
            return
            
        try:
            status = await self.get_risk_status()
            
            # Store in PostgreSQL
            metric_data = {
                'robot_id': self.robot_id,
                'metric_name': 'risk_status',
                'metric_value': status['account_balance'],
                'metric_type': 'currency',
                'timestamp': datetime.now().isoformat(),
                'metadata': status
            }
            await self.postgres.insert_performance_metric(metric_data)
            
            # Log to MongoDB
            log_data = {
                'timestamp': datetime.now(),
                'level': 'INFO',
                'robot_id': self.robot_id,
                'message': f"Risk status updated",
                'context': status
            }
            self.mongodb.insert_system_log(log_data)
            
        except Exception as e:
            self.logger.error(f"Failed to store risk status: {e}")
