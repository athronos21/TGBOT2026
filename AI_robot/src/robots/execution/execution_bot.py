"""
Execution Bot - Trade Execution

Executes trades including:
- Order preparation
- Order execution with retries
- Slippage tracking
- Trade logging to database
- Execution notifications
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
class ExecutionResult:
    """Execution result data"""
    success: bool
    trade_id: Optional[str] = None
    execution_price: Optional[float] = None
    slippage: float = 0.0
    status: str = "PENDING"


class ExecutionBot(Robot):
    """
    Executes trades on MetaTrader 5.
    
    Features:
    - Order preparation
    - Order execution with retries
    - Slippage tracking
    - Trade logging to database
    - Execution notifications
    """
    
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.logger = logging.getLogger(__name__)
        self.max_retries = config.get('max_retries', 3)
        self.retry_delay = config.get('retry_delay', 1.0)
        self.mt5 = None
        self.postgres = None
        self.mongodb = None
        
    async def initialize(self):
        """Initialize the Execution Bot"""
        self.logger.info(f"Initializing {self.robot_id}...")
        
        from src.integrations.mt5_connection import MT5Connection
        self.mt5 = MT5Connection(self.config.get('mt5', {}))
        
        self.postgres = PostgreSQLManager(self.config.get('database', {}).get('postgresql', {}))
        self.mongodb = MongoDBManager(self.config.get('database', {}).get('mongodb', {}))
        
        await self.postgres.connect()
        self.mongodb.connect()
        
        # Create tables if not exist
        await self.postgres.create_trade_table()
        self.mongodb.create_system_logs_collection()
        self.mongodb.create_configurations_collection()
        
        self.logger.info(f"{self.robot_id} initialized successfully")
        
    async def process(self, data: Any) -> Any:
        """Process risk-approved signal and execute trade"""
        if data is None:
            return None
            
        signal = data.get('signal') or data
        
        if not signal.get('risk_approved'):
            self.logger.warning("Signal not risk-approved, skipping execution")
            return None
            
        # Prepare order
        order = self._prepare_order(signal)
        
        if not order:
            await self.send_message('execution_failed', {
                'signal_id': signal.get('signal_id'),
                'reason': 'Order preparation failed'
            })
            return None
            
        # Execute with retries
        result = await self._execute_order(order, signal)
        
        if result.success:
            await self.send_message('trade_executed', {
                'trade_id': result.trade_id,
                'signal_id': signal.get('signal_id'),
                'execution_price': result.execution_price,
                'slippage': result.slippage,
                'status': result.status
            })
            await self._store_trade(signal, result)
        else:
            await self.send_message('execution_failed', {
                'signal_id': signal.get('signal_id'),
                'reason': result.status
            })
            
        return result
        
    async def cleanup(self):
        """Cleanup resources"""
        if self.postgres:
            await self.postgres.disconnect()
        if self.mongodb:
            self.mongodb.disconnect()
        self.logger.info(f"{self.robot_id} cleaned up")
        
    def _prepare_order(self, signal: Dict) -> Optional[Dict[str, Any]]:
        """Prepare order from signal"""
        try:
            symbol = signal.get('symbol', 'XAUUSD')
            signal_type = signal.get('signal_type', 'BUY')
            lot_size = signal.get('lot_size', 0.01)
            entry_mid = signal.get('entry_zone', {}).get('mid', 0)
            stop_loss = signal.get('stop_loss', 0)
            take_profit = signal.get('take_profit', 0)
            
            if entry_mid == 0:
                self.logger.error("Invalid entry price")
                return None
                
            # Determine order type
            from src.integrations.mt5_connection import MT5Connection
            order_type = MT5Connection.ORDER_TYPE_BUY if signal_type == 'BUY' else MT5Connection.ORDER_TYPE_SELL
            
            return {
                'symbol': symbol,
                'type': order_type,
                'volume': lot_size,
                'price': entry_mid,
                'sl': stop_loss,
                'tp': take_profit,
                'comment': f"Signal:{signal.get('signal_id')}",
                'magic': 10032025
            }
        except Exception as e:
            self.logger.error(f"Order preparation failed: {e}")
            return None
            
    async def _execute_order(self, order: Dict, signal: Dict) -> ExecutionResult:
        """Execute order with retries"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                if not self.mt5.is_connected():
                    self.logger.warning("MT5 not connected, attempting to reconnect")
                    await self.mt5.connect()
                    
                result = await self.mt5.place_order(order)
                
                if result and hasattr(result, 'retcode'):
                    if result.retcode == 10009:  # TRADE_RETCODE_DONE
                        return ExecutionResult(
                            success=True,
                            trade_id=str(result.order),
                            execution_price=result.price,
                            slippage=abs(result.price - order['price']),
                            status="EXECUTED"
                        )
                    else:
                        last_error = f"Order failed: {result.comment}"
                else:
                    last_error = "Order result is None"
                    
            except Exception as e:
                last_error = str(e)
                
            if attempt < self.max_retries - 1:
                self.logger.warning(f"Execution attempt {attempt + 1} failed: {last_error}")
                await asyncio.sleep(self.retry_delay)
                
        return ExecutionResult(
            success=False,
            status=f"Max retries exceeded: {last_error}"
        )
        
    async def _store_trade(self, signal: Dict, result: ExecutionResult):
        """Store trade in database"""
        if not self.postgres or not self.mongodb:
            return
            
        try:
            trade_data = {
                'external_id': result.trade_id,
                'symbol': signal.get('symbol', 'XAUUSD'),
                'trade_type': signal.get('signal_type', 'BUY'),
                'entry_price': signal.get('entry_zone', {}).get('mid', 0),
                'current_price': result.execution_price,
                'lot_size': signal.get('lot_size', 0.01),
                'status': 'OPEN',
                'open_time': datetime.now().isoformat(),
                'robot_id': self.robot_id,
                'signal_id': signal.get('signal_id'),
                'metadata': {
                    'slippage': result.slippage,
                    'stop_loss': signal.get('stop_loss'),
                    'take_profit': signal.get('take_profit'),
                    'confidence': signal.get('confidence')
                }
            }
            await self.postgres.insert_trade(trade_data)
            
            # Log to MongoDB
            log_data = {
                'timestamp': datetime.now(),
                'level': 'INFO',
                'robot_id': self.robot_id,
                'message': f"Trade executed for {signal.get('symbol')}",
                'context': {
                    'trade_id': result.trade_id,
                    'signal_id': signal.get('signal_id'),
                    'execution_price': result.execution_price,
                    'slippage': result.slippage
                }
            }
            self.mongodb.insert_system_log(log_data)
            
        except Exception as e:
            self.logger.error(f"Failed to store trade: {e}")
