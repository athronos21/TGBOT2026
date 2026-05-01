"""
Multi-Timeframe Aggregator Bot - Data Collection Robot

Subscribes to the live tick stream from TickBot and synthesizes 
multi-timeframe OHLC candles on the fly, propagating finalized 
candles to the rest of the system components and saving them.
"""

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from ...core.robot import Robot, RobotInfo
from .price_bot import OHLCData
from .tick_bot import TickData


class MTFAggregatorBot(Robot):
    """
    Multi-Timeframe Aggregator Bot
    
    Listens to 'tick_stream' events to generate OHLC candles dynamically
    for standard timeframes (M1, M5, M15, H1, H4).
    """
    
    DEFAULT_TIMEFRAMES = ["M1", "M5", "M15", "H1", "H4"]
    
    TIMEFRAME_MINUTES = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "M30": 30,
        "H1": 60,
        "H4": 240,
        "D1": 1440
    }
    
    def __init__(self, robot_info: RobotInfo, config: Dict[str, Any], 
                 message_bus=None, postgres_manager=None, mongo_manager=None):
        super().__init__(robot_info, config)
        
        self.message_bus = message_bus
        self.postgres = postgres_manager
        self.mongo = mongo_manager
        
        self.symbols = config.get('symbols', ['XAUUSD'])
        self.timeframes = config.get('timeframes', self.DEFAULT_TIMEFRAMES)
        
        # symbol -> timeframe -> active OHLCData
        self._active_candles: Dict[str, Dict[str, Optional[OHLCData]]] = {
            s: {tf: None for tf in self.timeframes} for s in self.symbols
        }
        
    async def initialize(self) -> bool:
        """Initialize the MTF Aggregator."""
        self.logger.info(f"Initializing {self.robot_id}...")
        
        if self.message_bus:
            self.set_message_bus(self.message_bus)
            
        if self.postgres:
            try:
                await self.postgres.create_market_data_table()
            except Exception as e:
                self.logger.error(f"Failed to initialize market data table: {e}")
                raise
                
        self.logger.info(f"{self.robot_id} initialized successfully")
        return True
        
    async def process(self, data: Any = None) -> Any:
        """
        Main processing loop - continuously listens for tick events to synthesize candles.
        """
        try:
            # Await tick_stream messages (timeout helps prevent thread lock if idle)
            event_data = await self.receive_message('tick_stream', timeout=1.0)
            
            if event_data is not None:
                tick = TickData(
                    symbol=event_data['symbol'],
                    bid=event_data['bid'],
                    ask=event_data['ask'],
                    volume=event_data['volume'],
                    timestamp=datetime.fromisoformat(event_data['timestamp'])
                )
                
                await self._process_tick(tick)
                
        except asyncio.TimeoutError:
            pass  # Normal when no ticks are streaming
        except Exception as e:
            self.logger.error(f"Error in MTF process loop: {e}")
            
        return None
        
    async def _process_tick(self, tick: TickData) -> None:
        """Distribute the tick to all configured timeframes for the symbol."""
        if tick.symbol not in self.symbols:
            return
            
        # Standardize "Price" (usually we map OHLC by bid price or mid price in custom streams)
        price = tick.bid
        
        for tf in self.timeframes:
            await self._update_candle(tick.symbol, tf, tick.timestamp, price, tick.volume)
            
    async def _update_candle(self, symbol: str, timeframe: str, dt: datetime, price: float, volume: int) -> None:
        """
        Updates the active candle. If the tick's timestamp passes the candle's timeframe boundary,
        finalize the current candle, dispatch it, and start a new one.
        """
        period_start = self._get_period_start(dt, timeframe)
        
        active = self._active_candles[symbol].get(timeframe)
        
        # New candle scenario: no active candle, or the period completely shifted
        if active is None or active.timestamp < period_start:
            # If an old candle exists, finalize and dispatch it
            if active is not None:
                await self._finalize_candle(active)
                
            # Create the fresh candle starting at the exact boundary
            self._active_candles[symbol][timeframe] = OHLCData(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=period_start,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume
            )
        else:
            # Valid continuous intra-candle update
            active.high = max(active.high, price)
            active.low = min(active.low, price)
            active.close = price
            active.volume += volume
            
    def _validate_candle(self, ohlc: OHLCData) -> bool:
        """Ensures candle integrity meets requirements before broadcasting."""
        if ohlc.open <= 0 or ohlc.high <= 0 or ohlc.low <= 0 or ohlc.close <= 0: return False
        if ohlc.high < ohlc.low: return False
        if ohlc.open > ohlc.high or ohlc.open < ohlc.low: return False
        if ohlc.close > ohlc.high or ohlc.close < ohlc.low: return False
        if ohlc.volume < 0: return False
        return True
        
    async def _finalize_candle(self, ohlc: OHLCData) -> None:
        """Validates and pushes a finalized candle to Postgres and the message bus."""
        if not self._validate_candle(ohlc):
            self.logger.warning(f"Invalid candle rolled over for {ohlc.symbol} {ohlc.timeframe}")
            return
            
        data_dict = ohlc.to_dict()
        
        # Dispatch to system via bus
        if self._message_bus:
            await self.send_message('candle_update', data_dict)
            
        # Log to MongoDB
        if self.mongo:
            self.mongo.insert_log({
                'level': 'INFO',
                'component': self.robot_id,
                'message': f"Finalized {ohlc.timeframe} Candle: {ohlc.symbol}",
                'data': data_dict,
                'timestamp': datetime.now().isoformat()
            })
            
        # Store securely to active Database
        if self.postgres:
            try:
                await self.postgres.insert_market_data([data_dict])
            except Exception as e:
                self.logger.error(f"Failed storing {ohlc.timeframe} candle into Postgres: {e}")
                
    def _get_period_start(self, dt: datetime, timeframe: str) -> datetime:
        """
        Derive the exact UTC start time bracket for a given timestamp mapping to a timeframe.
        """
        mins_val = self.TIMEFRAME_MINUTES.get(timeframe, 1)
        
        # Calculate total minutes since start of day to bucket accurately
        total_minutes = dt.hour * 60 + dt.minute
        bucket_mins = (total_minutes // mins_val) * mins_val
        
        new_hour = bucket_mins // 60
        new_minute = bucket_mins % 60
        
        return dt.replace(hour=new_hour, minute=new_minute, second=0, microsecond=0)
        
    async def cleanup(self) -> None:
        """Force finalize all currently accumulating candles on shutdown."""
        self.logger.info(f"Cleaning up {self.robot_id}...")
        for sym_data in self._active_candles.values():
            for candle in sym_data.values():
                if candle is not None:
                    await self._finalize_candle(candle)
