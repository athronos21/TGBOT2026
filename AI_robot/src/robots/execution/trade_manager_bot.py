"""
Trade Manager Bot - Trade Management

Manages open trades including:
- Break-even logic
- Trailing stop logic
- Partial close logic
- Position monitoring
- Trade update notifications
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from src.core.robot import Robot, RobotInfo, RobotState
from src.core.message_bus import MessageBus
from src.database.postgresql_manager import PostgreSQLManager
from src.database.mongodb_manager import MongoDBManager


@dataclass
class TradeUpdate:
    """Trade update data"""
    trade_id: str
    current_price: float
    profit_loss: float
    update_type: str
    timestamp: datetime


class TradeManagerBot(Robot):
    """
    Manages open trades and applies trading rules.
    
    Features:
    - Break-even logic
    - Trailing stop logic
    - Partial close logic
    - Position monitoring
    - Trade update notifications
    """
    
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.logger = logging.getLogger(__name__)
        self.monitor_interval = config.get('monitor_interval', 60)  # seconds
        self.mt5 = None
        self.postgres = None
        self.mongodb = None
        self._open_trades: Dict[str, Dict] = {}
        
    async def initialize(self):
        """Initialize the Trade Manager Bot"""
        self.logger.info(f"Initializing {self.robot_id}...")
        
        from src.integrations.mt5_connection import MT5Connection
        self.mt5 = MT5Connection(self.config.get('mt5', {}))
        
        self.postgres = PostgreSQLManager(self.config.get('database', {}).get('postgresql', {}))
        self.mongodb = MongoDBManager(self.config.get('database', {}).get('mongodb', {}))
        
        await self.postgres.connect()
        self.mongodb.connect()
        
        self.mongodb.create_system_logs_collection()
        self.mongodb.create_configurations_collection()
        
        self.logger.info(f"{self.robot_id} initialized successfully")
        
    async def process(self, data: Any) -> Any:
        """Process trade data and manage positions"""
        if data is None:
            return None
            
        trade_id = data.get('trade_id') or data.get('external_id')
        
        if not trade_id:
            return None
            
        # Get current position info
        positions = await self.mt5.get_open_positions()
        if not positions:
            return None
            
        # Find our position
        position = None
        for p in positions:
            if str(p.ticket) == trade_id:
                position = p
                break
                
        if not position:
            return None
            
        # Get current price
        tick = await self.mt5.get_tick(position.symbol)
        if not tick:
            return None
            
        # Calculate profit
        if position.type == 0:  # POSITION_TYPE_BUY
            current_price = tick.bid
            profit = (tick.bid - position.price_open) * position.volume * 100000
        else:
            current_price = tick.ask
            profit = (position.price_open - tick.ask) * position.volume * 100000
            
        # Apply trading rules
        update = self._apply_trading_rules(position, current_price, profit)
        
        if update:
            await self.send_message('trade_update', {
                'trade_id': trade_id,
                'current_price': current_price,
                'profit_loss': profit,
                'update_type': update.update_type,
                'timestamp': datetime.now().isoformat()
            })
            await self._update_trade_in_db(trade_id, current_price, profit)
            
        return update
        
    async def cleanup(self):
        """Cleanup resources"""
        if self.postgres:
            await self.postgres.disconnect()
        if self.mongodb:
            self.mongodb.disconnect()
        self.logger.info(f"{self.robot_id} cleaned up")
        
    def _apply_trading_rules(self, position: Any, current_price: float,
                             profit: float) -> Optional[TradeUpdate]:
        """Apply trading rules to position"""
        update = None
        
        # Break-even logic
        if profit > 0:
            update = self._check_break_even(position, current_price, profit)
            
        # Trailing stop logic
        if not update:
            update = self._check_trailing_stop(position, current_price, profit)
            
        # Partial close logic
        if not update:
            update = self._check_partial_close(position, current_price, profit)
            
        return update
        
    def _check_break_even(self, position: Any, current_price: float,
                          profit: float) -> Optional[TradeUpdate]:
        """Check if break-even should be applied"""
        # Move SL to break-even when profit > 0
        if position.sl == 0 and profit > 0:
            # Move SL to entry price
            new_sl = position.price_open
            result = self._modify_position(position, new_sl, position.tp)
            if result:
                return TradeUpdate(
                    trade_id=str(position.ticket),
                    current_price=current_price,
                    profit_loss=profit,
                    update_type='break_even',
                    timestamp=datetime.now()
                )
        return None
        
    def _check_trailing_stop(self, position: Any, current_price: float,
                             profit: float) -> Optional[TradeUpdate]:
        """Check if trailing stop should be applied"""
        trailing_distance = 50  # pips
        
        if position.type == 0:  # BUY
            # Trailing stop for buy positions
            if current_price - position.sl > trailing_distance * 0.0001:
                new_sl = current_price - trailing_distance * 0.0001
                result = self._modify_position(position, new_sl, position.tp)
                if result:
                    return TradeUpdate(
                        trade_id=str(position.ticket),
                        current_price=current_price,
                        profit_loss=profit,
                        update_type='trailing_stop',
                        timestamp=datetime.now()
                    )
        else:  # SELL
            # Trailing stop for sell positions
            if position.sl - current_price > trailing_distance * 0.0001:
                new_sl = current_price + trailing_distance * 0.0001
                result = self._modify_position(position, new_sl, position.tp)
                if result:
                    return TradeUpdate(
                        trade_id=str(position.ticket),
                        current_price=current_price,
                        profit_loss=profit,
                        update_type='trailing_stop',
                        timestamp=datetime.now()
                    )
        return None
        
    def _check_partial_close(self, position: Any, current_price: float,
                             profit: float) -> Optional[TradeUpdate]:
        """Check if partial close should be applied"""
        # Close 50% when profit > 2x risk
        risk = abs(position.price_open - position.sl) * position.volume * 100000
        if profit > 2 * risk and position.volume > 0.01:
            # Close half the position
            half_volume = position.volume / 2
            result = self._close_position(position, half_volume)
            if result:
                return TradeUpdate(
                    trade_id=str(position.ticket),
                    current_price=current_price,
                    profit_loss=profit,
                    update_type='partial_close',
                    timestamp=datetime.now()
                )
        return None
        
    async def _modify_position(self, position: Any, new_sl: float,
                               new_tp: float) -> bool:
        """Modify position SL/TP"""
        try:
            request = {
                "action": 5,  # TRADE_ACTION_SLTP
                "position": position.ticket,
                "sl": new_sl,
                "tp": new_tp,
                "magic": 10032025,
                "comment": "Trade Manager"
            }
            result = await asyncio.to_thread(self.mt5._mt5.order_send, request)
            return result and hasattr(result, 'retcode') and result.retcode == 10009
        except Exception as e:
            self.logger.error(f"Failed to modify position: {e}")
            return False
            
    async def _close_position(self, position: Any, volume: float) -> bool:
        """Close position partially or fully"""
        try:
            tick = await self.mt5.get_tick(position.symbol)
            if not tick:
                return False
                
            # Determine close price
            close_price = tick.bid if position.type == 0 else tick.ask
            
            request = {
                "action": 1,  # TRADE_ACTION_DEAL
                "symbol": position.symbol,
                "volume": volume,
                "type": 1 if position.type == 0 else 0,  # Opposite order type
                "position": position.ticket,
                "price": close_price,
                "magic": 10032025,
                "comment": "Trade Manager Close"
            }
            result = await asyncio.to_thread(self.mt5._mt5.order_send, request)
            return result and hasattr(result, 'retcode') and result.retcode == 10009
        except Exception as e:
            self.logger.error(f"Failed to close position: {e}")
            return False
            
    async def _update_trade_in_db(self, trade_id: str, current_price: float,
                                   profit: float):
        """Update trade in database"""
        if not self.postgres or not self.mongodb:
            return
            
        try:
            trade_data = {
                'current_price': current_price,
                'profit_loss': profit
            }
            await self.postgres.update_trade(int(trade_id), trade_data)
            
            # Log to MongoDB
            log_data = {
                'timestamp': datetime.now(),
                'level': 'INFO',
                'robot_id': self.robot_id,
                'message': f"Trade updated for {trade_id}",
                'context': {
                    'current_price': current_price,
                    'profit_loss': profit
                }
            }
            self.mongodb.insert_system_log(log_data)
            
        except Exception as e:
            self.logger.error(f"Failed to update trade: {e}")
