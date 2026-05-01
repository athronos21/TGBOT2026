"""
Volatility Scanner Bot - Data Collection Robot

Ingests completed OHLC candles and computes volatility metrics 
such as Average True Range (ATR) and Bollinger Bands. Emits 
alerts when large anomalies occur.
"""

import asyncio
from typing import Dict, List, Any, Optional
from collections import deque
import math

from ...core.robot import Robot, RobotInfo
from .price_bot import OHLCData

class VolatilityScannerBot(Robot):
    """
    Volatility Scanner Bot
    
    Subscribes to 'candle_update' to maintain rolling history windows
    for calculating Standard Deviation, Bollinger Bands, and ATR.
    """
    
    DEFAULT_ATR_PERIOD = 14
    DEFAULT_BB_PERIOD = 20
    DEFAULT_BB_STD_DEV = 2.0
    
    def __init__(self, robot_info: RobotInfo, config: Dict[str, Any], 
                 message_bus=None, mongo_manager=None):
        super().__init__(robot_info, config)
        
        self.message_bus = message_bus
        self.mongo = mongo_manager
        
        # Pull threshold configs
        self.atr_period = config.get('atr_period', self.DEFAULT_ATR_PERIOD)
        self.bb_period = config.get('bb_period', self.DEFAULT_BB_PERIOD)
        self.bb_std_dev = config.get('bb_std_dev', self.DEFAULT_BB_STD_DEV)
        
        self.max_history = max(self.atr_period, self.bb_period)
        
        # State: symbol -> timeframe -> deque[OHLCData]
        self._history: Dict[str, Dict[str, deque]] = {}
        
    async def initialize(self) -> bool:
        """Initialize the Volatility Scanner Bot."""
        self.logger.info(f"Initializing {self.robot_id}...")
        
        if self.message_bus:
            self.set_message_bus(self.message_bus)
            
        self.logger.info(f"{self.robot_id} initialized successfully")
        return True
        
    async def process(self, data: Any = None) -> Any:
        """Listen sequentially for finalized candles and process metrics."""
        try:
            event_data = await self.receive_message('candle_update', timeout=1.0)
            
            if event_data is not None:
                symbol = event_data['symbol']
                timeframe = event_data['timeframe']
                
                candle = OHLCData(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=event_data['timestamp'],  # We can just keep it as a string or instantiate it, we don't strictly use it for math
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
            self.logger.error(f"Error in volatility process loop: {e}")
            
        return None

    async def _process_candle(self, candle: OHLCData) -> None:
        """Process an incoming candle and recalculate volatility metrics."""
        sym = candle.symbol
        tf = candle.timeframe
        
        if sym not in self._history:
            self._history[sym] = {}
        if tf not in self._history[sym]:
            self._history[sym][tf] = deque(maxlen=self.max_history)
            
        history_buffer = self._history[sym][tf]
        history_buffer.append(candle)
        
        # Wait until we have enough history to calculate safely
        metrics = {}
        metrics_computed = False
        
        if len(history_buffer) >= self.atr_period:
            metrics['atr'] = self._calculate_atr(history_buffer)
            metrics_computed = True
            
        if len(history_buffer) >= self.bb_period:
            bb_upper, bb_mid, bb_lower = self._calculate_bollinger_bands(history_buffer)
            metrics['bb_upper'] = bb_upper
            metrics['bb_mid'] = bb_mid
            metrics['bb_lower'] = bb_lower
            metrics['bb_width'] = bb_upper - bb_lower
            metrics_computed = True
            
        if metrics_computed:
            await self._broadcast_metrics(candle, metrics)

    def _calculate_atr(self, history: deque) -> float:
        """Calculates Average True Range (ATR) over the stored period using Simple MA tracking."""
        data_list = list(history)
        
        # We need atr_period + 1 elements ideally, but if we only have atr_period, the first TR is just High - Low.
        start_idx = len(data_list) - self.atr_period
        trs = []
        
        for i in range(start_idx, len(data_list)):
            current = data_list[i]
            if i == 0:
                tr = current.high - current.low
            else:
                prev = data_list[i - 1]
                hl = current.high - current.low
                hc = abs(current.high - prev.close)
                lc = abs(current.low - prev.close)
                tr = max(hl, hc, lc)
            trs.append(tr)
            
        return sum(trs) / len(trs)

    def _calculate_bollinger_bands(self, history: deque):
        """Calculates Bollinger Bands: returns (upper, middle, lower)."""
        data_list = list(history)[-self.bb_period:]
        closes = [c.close for c in data_list]
        
        # Middle Band is Simple Moving Average (SMA)
        sma = sum(closes) / len(closes)
        
        # Standard Deviation
        variance = sum((c - sma) ** 2 for c in closes) / len(closes)
        std_dev = math.sqrt(variance)
        
        upper = sma + (self.bb_std_dev * std_dev)
        lower = sma - (self.bb_std_dev * std_dev)
        
        return upper, sma, lower

    async def _broadcast_metrics(self, candle: OHLCData, metrics: Dict[str, float]) -> None:
        """Publishes the tracked metrics and issues any immediate alerts."""
        payload = {
            'symbol': candle.symbol,
            'timeframe': candle.timeframe,
            'timestamp': str(candle.timestamp),
            'metrics': metrics
        }
        
        # Check alerts
        alerts = self._check_alerts(candle, metrics)
        if alerts:
            payload['alerts'] = alerts
            
        if self._message_bus:
            await self.send_message('volatility_update', payload)
            
            # High priority dispatch for alerts
            if alerts:
                await self.send_message('volatility_alert', payload)
                
        if alerts and self.mongo:
            self.mongo.insert_log({
                'level': 'WARNING',
                'component': self.robot_id,
                'message': f"Volatility Alert triggered for {candle.symbol} ({candle.timeframe}): {', '.join(alerts)}",
                'data': payload,
                'timestamp': str(candle.timestamp)
            })

    def _check_alerts(self, candle: OHLCData, metrics: Dict[str, float]) -> List[str]:
        """Generate high-priority string indicators if standard bounds are blown out."""
        alerts = []
        
        bb_upper = metrics.get('bb_upper')
        bb_lower = metrics.get('bb_lower')
        
        if bb_upper is not None and candle.close > bb_upper:
            alerts.append('PRICE_ABOVE_UPPER_BB')
        if bb_lower is not None and candle.close < bb_lower:
            alerts.append('PRICE_BELOW_LOWER_BB')
            
        return alerts

    async def cleanup(self) -> None:
        """Cleanup gracefully."""
        self.logger.info(f"Cleaning up {self.robot_id}...")
        self._history.clear()
