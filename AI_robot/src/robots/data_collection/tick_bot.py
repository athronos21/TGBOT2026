"""
Tick Bot - Data Collection Robot

High-frequency robot focusing exclusively on fetching, buffering
and streaming raw tick-level data from MetaTrader 5.
"""

import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from ...core.robot import Robot, RobotInfo
from ...integrations.mt5_connection import MT5Connection
from ...database.postgresql_manager import PostgreSQLManager
from ...database.mongodb_manager import MongoDBManager


@dataclass
class TickData:
    """Tick data structure for high-frequency streaming"""
    symbol: str
    bid: float
    ask: float
    volume: int
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'bid': self.bid,
            'ask': self.ask,
            'volume': self.volume,
            'timestamp': self.timestamp.isoformat()
        }


class TickBot(Robot):
    """
    Tick Bot - Streams raw tick-level data continuously.
    
    Features:
    - Dedicated tick stream for specific symbols
    - Fast continuous polling to simulate streaming
    - High-volume tick buffering and batch insertion
    """
    
    DEFAULT_TICK_INTERVAL = 0.1  # seconds
    DEFAULT_MAX_TICKS_PER_BATCH = 500
    
    def __init__(self, robot_info: RobotInfo, config: Dict[str, Any], 
                 message_bus=None, mt5_connection=None,
                 postgres_manager=None,
                 mongo_manager=None):
        super().__init__(robot_info, config)
        
        self.mt5 = mt5_connection
        self.postgres = postgres_manager
        self.mongo = mongo_manager
        
        self.symbols = config.get('symbols', ['XAUUSD'])
        self.tick_interval = config.get('tick_interval', self.DEFAULT_TICK_INTERVAL)
        self.max_ticks_per_batch = config.get('max_ticks_per_batch', self.DEFAULT_MAX_TICKS_PER_BATCH)
        
        self._tick_buffer: List[TickData] = []
        self._last_tick_time: Dict[str, Optional[datetime]] = {s: None for s in self.symbols}
        
    async def initialize(self) -> bool:
        """Initialize the Tick Bot."""
        self.logger.info(f"Initializing {self.robot_id}...")
        
        if self.postgres:
            try:
                await self.postgres.create_market_data_table()
            except Exception as e:
                self.logger.error(f"Failed to initialize market data table: {e}")
                raise
                
        if self.mongo:
            try:
                self.mongo.create_logs_collection()
                self.mongo.create_events_collection()
            except Exception as e:
                self.logger.error(f"Failed to initialize MongoDB collections: {e}")
                raise
                
        self.logger.info(f"{self.robot_id} initialized successfully")
        return True
        
    async def process(self, data: Any = None) -> Any:
        """
        Main processing loop - continuously fetches ticks via fast polling.
        """
        try:
            for symbol in self.symbols:
                tick_data = await self._fetch_tick_data(symbol)
                
                # Check for duplicate consecutive ticks by timestamp to simulate streams
                if tick_data:
                    last_time = self._last_tick_time.get(symbol)
                    if last_time is None or tick_data.timestamp > last_time:
                        self._last_tick_time[symbol] = tick_data.timestamp
                        await self._process_tick_data(tick_data)
            
            # Flush buffers periodically if they haven't triggered the size threshold
            if len(self._tick_buffer) > 0 and len(self._tick_buffer) >= (self.max_ticks_per_batch / 2):
                await self._flush_tick_buffer()
                
            # Short sleep to pace the tick polling
            await asyncio.sleep(self.tick_interval)
            
        except Exception as e:
            self.logger.error(f"Error in process loop: {e}")
            
        return None
        
    async def _fetch_tick_data(self, symbol: str) -> Optional[TickData]:
        """Fetch the latest tick."""
        try:
            tick = await self.mt5.get_tick(symbol)
            if tick is None:
                return None
            return TickData(
                symbol=symbol,
                bid=tick.bid,
                ask=tick.ask,
                volume=tick.volume,
                timestamp=tick.time
            )
        except Exception as e:
            self.logger.error(f"Error fetching tick data for {symbol}: {e}")
            return None
            
    async def _process_tick_data(self, tick_data: TickData) -> None:
        """Process and buffer the incoming tick."""
        if not self._validate_tick_data(tick_data):
            return
            
        self._tick_buffer.append(tick_data)
        
        if self.message_bus:
            await self.message_bus.publish(
                event='tick_stream',
                data=tick_data.to_dict(),
                sender=self.robot_id,
                priority='HIGH'
            )
            
        if len(self._tick_buffer) >= self.max_ticks_per_batch:
            await self._flush_tick_buffer()
            
    def _validate_tick_data(self, tick_data: TickData) -> bool:
        if not tick_data.symbol: return False
        if tick_data.bid <= 0 or tick_data.ask <= 0: return False
        if tick_data.bid >= tick_data.ask: return False
        if tick_data.volume < 0: return False
        return True
        
    async def _flush_tick_buffer(self) -> None:
        """Flush the high-speed tick buffer to PostgreSQL."""
        if not self._tick_buffer: return
        
        try:
            data = [t.to_dict() for t in self._tick_buffer]
            # Assumes Postgres schema accepts tick precision in market_data or tick_data
            if self.postgres:
                await self.postgres.insert_market_data(data)
            
            self._tick_buffer.clear()
            self.logger.debug(f"Flushed {len(data)} tick records")
        except Exception as e:
            self.logger.error(f"Error flushing tick buffer: {e}")
            
    async def cleanup(self) -> bool:
        """Cleanup logic."""
        self.logger.info(f"Cleaning up {self.robot_id}...")
        await self._flush_tick_buffer()
        return True
