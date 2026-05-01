"""
Price Bot - Data Collection Robot

Fetches and processes price data from MetaTrader 5, including:
- Tick data (bid/ask prices)
- OHLC data (candlesticks)
- Data validation and publishing
- Database storage
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json

from ...core.robot import Robot, RobotInfo, RobotState
from ...integrations.mt5_connection import MT5Connection
from ...database.postgresql_manager import PostgreSQLManager
from ...database.mongodb_manager import MongoDBManager


@dataclass
class TickData:
    """Tick data structure"""
    symbol: str
    bid: float
    ask: float
    volume: int
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'bid': self.bid,
            'ask': self.ask,
            'volume': self.volume,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class OHLCData:
    """OHLC (Open-High-Low-Close) data structure"""
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }


class PriceBot(Robot):
    """
    Price Bot - Collects and processes market price data from MetaTrader 5.
    
    Features:
    - Real-time tick data fetching
    - OHLC (candlestick) data fetching
    - Multi-timeframe support
    - Data validation
    - Message bus publishing
    - Database storage
    """
    
    # Default configuration
    DEFAULT_TICK_INTERVAL = 1.0  # seconds between tick fetches
    DEFAULT_CANDLE_INTERVAL = 60.0  # seconds between candle fetches
    DEFAULT_TIMEFRAMES = ['M1', 'M5', 'M15', 'H1', 'H4', 'D1']
    DEFAULT_MAX_TICKS_PER_BATCH = 100
    
    def __init__(self, robot_info: RobotInfo, config: Dict[str, Any], 
                 message_bus=None, mt5_connection=None,
                 postgres_manager=None,
                 mongo_manager=None):
        """
        Initialize the Price Bot.
        
        Args:
            robot_info: Robot metadata
            config: Configuration dictionary
            message_bus: Message bus for publishing events
            mt5_connection: MT5 connection manager
            postgres_manager: PostgreSQL database manager
            mongo_manager: MongoDB database manager
        """
        super().__init__(robot_info, config)
        
        self.mt5 = mt5_connection
        self.postgres = postgres_manager
        self.mongo = mongo_manager
        
        # Configuration
        self.symbols = config.get('symbols', ['XAUUSD'])
        self.tick_interval = config.get('tick_interval', self.DEFAULT_TICK_INTERVAL)
        self.candle_interval = config.get('candle_interval', self.DEFAULT_CANDLE_INTERVAL)
        self.timeframes = config.get('timeframes', self.DEFAULT_TIMEFRAMES)
        self.max_ticks_per_batch = config.get('max_ticks_per_batch', self.DEFAULT_MAX_TICKS_PER_BATCH)
        
        # Data buffers
        self._tick_buffer: List[TickData] = []
        self._candle_buffer: List[OHLCData] = []
        
        # Timeframe mapping
        self._timeframe_map = {
            'M1': 1, 'M5': 5, 'M15': 15, 'H1': 60, 'H4': 240, 'D1': 1440
        }
        
        # Last fetch timestamps
        self._last_tick_fetch: Dict[str, datetime] = {}
        self._last_candle_fetch: Dict[str, Dict[str, datetime]] = {}
        
    async def initialize(self) -> bool:
        """
        Initialize the Price Bot.
        
        Returns:
            True if initialization successful
        """
        self.logger.info(f"Initializing {self.robot_id}...")
        
        # Initialize database tables
        await self._init_database()
        
        # Initialize MongoDB collections
        self._init_mongodb()
        
        # Initialize last fetch timestamps
        now = datetime.now()
        for symbol in self.symbols:
            self._last_tick_fetch[symbol] = now
            self._last_candle_fetch[symbol] = {}
            for tf in self.timeframes:
                self._last_candle_fetch[symbol][tf] = now
        
        self.logger.info(f"{self.robot_id} initialized successfully")
        return True
        
    async def _init_database(self) -> None:
        """Initialize database tables"""
        try:
            await self.postgres.create_market_data_table()
            self.logger.info("Market data table initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize market data table: {e}")
            raise
            
    def _init_mongodb(self) -> None:
        """Initialize MongoDB collections"""
        try:
            self.mongo.create_logs_collection()
            self.mongo.create_events_collection()
            self.logger.info("MongoDB collections initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize MongoDB collections: {e}")
            raise
            
    async def process(self, data: Any = None) -> Any:
        """
        Main processing loop - fetches and processes price data.
        
        Args:
            data: Optional input data
            
        Returns:
            Processed data
        """
        try:
            # Fetch tick data for all symbols
            for symbol in self.symbols:
                tick_data = await self._fetch_tick_data(symbol)
                if tick_data:
                    await self._process_tick_data(tick_data)
                    
            # Fetch OHLC data for all symbols and timeframes
            for symbol in self.symbols:
                for timeframe in self.timeframes:
                    ohlc_data = await self._fetch_ohlc_data(symbol, timeframe)
                    if ohlc_data:
                        await self._process_ohlc_data(ohlc_data)
                        
            # Flush buffers to database
            await self._flush_buffers()
            
        except Exception as e:
            self.logger.error(f"Error in process loop: {e}")
            await self.handle_error(e)
            
        return None
        
    async def _fetch_tick_data(self, symbol: str) -> Optional[TickData]:
        """
        Fetch tick data for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            TickData or None if failed
        """
        try:
            tick = await self.mt5.get_tick(symbol)
            if tick is None:
                self.logger.warning(f"Failed to get tick for {symbol}")
                return None
                
            tick_data = TickData(
                symbol=symbol,
                bid=tick.bid,
                ask=tick.ask,
                volume=tick.volume,
                timestamp=tick.time
            )
            
            self._last_tick_fetch[symbol] = datetime.now()
            return tick_data
            
        except Exception as e:
            self.logger.error(f"Error fetching tick data for {symbol}: {e}")
            return None
            
    async def _fetch_ohlc_data(self, symbol: str, timeframe: str) -> Optional[List[OHLCData]]:
        """
        Fetch OHLC data for a symbol and timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., 'M1', 'H1')
            
        Returns:
            List of OHLCData or None if failed
        """
        try:
            # Convert timeframe string to MT5 constant
            mt5_timeframe = self._get_mt5_timeframe(timeframe)
            if mt5_timeframe is None:
                self.logger.warning(f"Invalid timeframe: {timeframe}")
                return None
                
            # Get candles (last 100 bars)
            candles = await self.mt5.get_candles(symbol, mt5_timeframe, 100)
            if candles is None:
                self.logger.warning(f"Failed to get candles for {symbol} ({timeframe})")
                return None
                
            ohlc_data = []
            for candle in candles:
                ohlc = OHLCData(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=candle.time,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume
                )
                ohlc_data.append(ohlc)
                
            self._last_candle_fetch[symbol][timeframe] = datetime.now()
            return ohlc_data
            
        except Exception as e:
            self.logger.error(f"Error fetching OHLC data for {symbol} ({timeframe}): {e}")
            return None
            
    def _get_mt5_timeframe(self, timeframe: str) -> Optional[int]:
        """
        Convert timeframe string to MT5 constant.
        
        Args:
            timeframe: Timeframe string (e.g., 'M1', 'H1')
            
        Returns:
            MT5 timeframe constant or None if invalid
        """
        import MetaTrader5 as mt5
        
        timeframe_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1
        }
        return timeframe_map.get(timeframe)
        
    async def _process_tick_data(self, tick_data: TickData) -> None:
        """
        Process tick data - validate, buffer, and publish.
        
        Args:
            tick_data: Tick data to process
        """
        try:
            # Validate tick data
            if not self._validate_tick_data(tick_data):
                self.logger.warning(f"Invalid tick data for {tick_data.symbol}")
                return
                
            # Add to buffer
            self._tick_buffer.append(tick_data)
            
            # Publish to message bus
            await self.message_bus.publish(
                event='price_update',
                data=tick_data.to_dict(),
                sender=self.robot_id,
                priority='HIGH'
            )
            
            # Log to MongoDB
            self.mongo.insert_log({
                'level': 'INFO',
                'component': self.robot_id,
                'message': f"Tick data received: {tick_data.symbol}",
                'data': tick_data.to_dict(),
                'timestamp': datetime.now().isoformat()
            })
            
            # Check if buffer needs flushing
            if len(self._tick_buffer) >= self.max_ticks_per_batch:
                await self._flush_tick_buffer()
                
        except Exception as e:
            self.logger.error(f"Error processing tick data: {e}")
            
    async def _process_ohlc_data(self, ohlc_data: List[OHLCData]) -> None:
        """
        Process OHLC data - validate, buffer, and publish.
        
        Args:
            ohlc_data: List of OHLC data to process
        """
        try:
            # Validate OHLC data
            valid_data = [d for d in ohlc_data if self._validate_ohlc_data(d)]
            
            if not valid_data:
                self.logger.warning(f"No valid OHLC data for {ohlc_data[0].symbol} ({ohlc_data[0].timeframe})")
                return
                
            # Add to buffer
            self._candle_buffer.extend(valid_data)
            
            # Publish to message bus
            for ohlc in valid_data:
                await self.message_bus.publish(
                    event='candle_update',
                    data=ohlc.to_dict(),
                    sender=self.robot_id,
                    priority='NORMAL'
                )
                
            # Log to MongoDB
            self.mongo.insert_log({
                'level': 'INFO',
                'component': self.robot_id,
                'message': f"OHLC data received: {ohlc.symbol} ({ohlc.timeframe})",
                'data': ohlc.to_dict(),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Error processing OHLC data: {e}")
            
    def _validate_tick_data(self, tick_data: TickData) -> bool:
        """
        Validate tick data.
        
        Args:
            tick_data: Tick data to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        if not tick_data.symbol:
            return False
        if tick_data.bid <= 0 or tick_data.ask <= 0:
            return False
        if tick_data.bid >= tick_data.ask:
            return False
        if tick_data.volume < 0:
            return False
            
        return True
        
    def _validate_ohlc_data(self, ohlc_data: OHLCData) -> bool:
        """
        Validate OHLC data.
        
        Args:
            ohlc_data: OHLC data to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        if not ohlc_data.symbol:
            return False
        if not ohlc_data.timeframe:
            return False
            
        # Check price values
        if ohlc_data.open <= 0 or ohlc_data.high <= 0:
            return False
        if ohlc_data.low <= 0 or ohlc_data.close <= 0:
            return False
            
        # Check high/low relationship
        if ohlc_data.high < ohlc_data.low:
            return False
        if ohlc_data.open < ohlc_data.low or ohlc_data.open > ohlc_data.high:
            return False
        if ohlc_data.close < ohlc_data.low or ohlc_data.close > ohlc_data.high:
            return False
            
        # Check volume
        if ohlc_data.volume < 0:
            return False
            
        return True
        
    async def _flush_buffers(self) -> None:
        """Flush all buffers to database"""
        await self._flush_tick_buffer()
        await self._flush_ohlc_buffer()
        
    async def _flush_tick_buffer(self) -> None:
        """Flush tick buffer to database"""
        if not self._tick_buffer:
            return
            
        try:
            # Convert to list of dicts for database
            data = [tick.to_dict() for tick in self._tick_buffer]
            
            # Insert into PostgreSQL
            await self.postgres.insert_market_data(data)
            
            # Clear buffer
            self._tick_buffer.clear()
            
            self.logger.debug(f"Flushed {len(data)} tick records to database")
            
        except Exception as e:
            self.logger.error(f"Error flushing tick buffer: {e}")
            
    async def _flush_ohlc_buffer(self) -> None:
        """Flush OHLC buffer to database"""
        if not self._candle_buffer:
            return
            
        try:
            # Convert to list of dicts for database
            data = [ohlc.to_dict() for ohlc in self._candle_buffer]
            
            # Insert into PostgreSQL
            await self.postgres.insert_market_data(data)
            
            # Clear buffer
            self._candle_buffer.clear()
            
            self.logger.debug(f"Flushed {len(data)} OHLC records to database")
            
        except Exception as e:
            self.logger.error(f"Error flushing OHLC buffer: {e}")
            
    async def cleanup(self) -> bool:
        """
        Cleanup resources.
        
        Returns:
            True if cleanup successful
        """
        self.logger.info(f"Cleaning up {self.robot_id}...")
        
        # Flush any remaining data
        await self._flush_buffers()
        
        self.logger.info(f"{self.robot_id} cleanup complete")
        return True
