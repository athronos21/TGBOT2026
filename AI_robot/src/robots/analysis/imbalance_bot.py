"""
Imbalance Bot - Analysis Robot

Tracks trend imbalances by monitoring standard candle body sizes 
and volume metrics over a rolling period. Identifies extreme
expansion candles representing aggressive directional momentum.
"""

import asyncio
from typing import Dict, List, Any, Optional
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from ...core.robot import Robot, RobotInfo
from ..data_collection.price_bot import OHLCData

@dataclass
class Imbalance:
    id: str
    symbol: str
    timeframe: str
    imbalance_type: str  # "BULLISH" or "BEARISH"
    start_price: float
    end_price: float
    volume: int
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'imbalance_type': self.imbalance_type,
            'start_price': self.start_price,
            'end_price': self.end_price,
            'volume': self.volume,
            'timestamp': self.timestamp.isoformat()
        }

class ImbalanceBot(Robot):
    """
    Imbalance Analysis Bot
    
    Evaluates incoming price ticks against local rolling historical averages
    to pinpoint massive structural momentum spikes.
    """
    
    DEFAULT_HISTORY_PERIOD = 20
    DEFAULT_SIZE_MULTIPLIER = 2.0
    DEFAULT_VOL_MULTIPLIER = 1.5
    
    def __init__(self, robot_info: RobotInfo, config: Dict[str, Any], 
                 message_bus=None, mongo_manager=None):
        super().__init__(robot_info, config)
        
        self.message_bus = message_bus
        self.mongo = mongo_manager
        
        self.history_period = config.get('history_period', self.DEFAULT_HISTORY_PERIOD)
        self.size_multiplier = config.get('size_multiplier', self.DEFAULT_SIZE_MULTIPLIER)
        self.vol_multiplier = config.get('vol_multiplier', self.DEFAULT_VOL_MULTIPLIER)
        
        # State: symbol -> timeframe -> deque[OHLCData]
        self._history: Dict[str, Dict[str, deque]] = {}
        
    async def initialize(self) -> bool:
        """Initialize the Imbalance Bot."""
        self.logger.info(f"Initializing {self.robot_id}...")
        if self.message_bus:
            self.set_message_bus(self.message_bus)
        return True
        
    async def process(self, data: Any = None) -> Any:
        """Main loop listens for finalized multi-timeframe candles."""
        try:
            event_data = await self.receive_message('candle_update', timeout=1.0)
            
            if event_data:
                candle = OHLCData(
                    symbol=event_data['symbol'],
                    timeframe=event_data['timeframe'],
                    timestamp=datetime.fromisoformat(event_data['timestamp']),
                    open=event_data['open'],
                    high=event_data['high'],
                    low=event_data['low'],
                    close=event_data['close'],
                    volume=event_data['volume']
                )
                
                await self._process_candle(candle)
                
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            self.logger.error(f"Error checking Imbalances: {e}")
            
        return None

    async def _process_candle(self, candle: OHLCData) -> None:
        """Appends to history buffer and checks threshold."""
        sym = candle.symbol
        tf = candle.timeframe
        
        if sym not in self._history:
            self._history[sym] = {}
        if tf not in self._history[sym]:
            self._history[sym][tf] = deque(maxlen=self.history_period)
            
        history = self._history[sym][tf]
        
        # Determine Imbalance before adding the fresh anomaly into the average!
        if len(history) >= (self.history_period // 2): 
            # Allow evaluation when we have at least half the history filled
            await self._detect_imbalance(history, candle)
            
        history.append(candle)

    async def _detect_imbalance(self, history: deque, candle: OHLCData) -> None:
        """MATH logic determining if recent jump dwarfs the moving average profile."""
        
        # Current Candle Stats
        c_body = abs(candle.open - candle.close)
        c_vol = candle.volume
        
        # Averages
        avg_body = sum(abs(c.open - c.close) for c in history) / len(history)
        avg_vol = sum(c.volume for c in history) / len(history)
        
        # Avoid dividing by zeroes in dead markets
        if avg_body == 0 or avg_vol == 0:
            return
            
        is_size_anomalous = c_body >= (avg_body * self.size_multiplier)
        is_vol_anomalous = c_vol >= (avg_vol * self.vol_multiplier)
        
        if is_size_anomalous and is_vol_anomalous:
            direction = "BULLISH" if candle.close > candle.open else "BEARISH"
            
            imbalance = Imbalance(
                id=f"{candle.symbol}_{candle.timeframe}_{int(candle.timestamp.timestamp())}_{direction}",
                symbol=candle.symbol,
                timeframe=candle.timeframe,
                imbalance_type=direction,
                start_price=candle.open,
                end_price=candle.close,
                volume=c_vol,
                timestamp=candle.timestamp
            )
            
            await self._dispatch_event(imbalance)

    async def _dispatch_event(self, imbalance: Imbalance) -> None:
        """Pushes anomaly payload out via the message bus."""
        payload = imbalance.to_dict()
        
        if self._message_bus:
            await self.send_message('imbalance_detected', payload)
            
        if self.mongo:
            self.mongo.insert_log({
                'level': 'WARNING',  # Imbalances count as significant structural shifts
                'component': self.robot_id,
                'message': f"{imbalance.imbalance_type} Imbalance Detected: {imbalance.symbol}({imbalance.timeframe}) over {imbalance.start_price}-{imbalance.end_price}",
                'data': payload,
                'timestamp': datetime.now().isoformat()
            })

    async def cleanup(self) -> None:
        """Cleanup gracefully."""
        self.logger.info(f"Cleaning up {self.robot_id}...")
        self._history.clear()
