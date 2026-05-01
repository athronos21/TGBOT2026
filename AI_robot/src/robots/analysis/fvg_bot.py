"""
Fair Value Gap (FVG) Bot - Analysis Robot

Tracks Smart Money Concepts (SMC) principles by observing incoming
multi-timeframe OHLC candles, searching for structurally significant
3-candle imbalances (FVGs). 

Dispatches events when FVGs are formed, and tracks their exact bounds 
until trailing price action successfully mitigates them.
"""

import asyncio
from typing import Dict, List, Any, Optional
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from ...core.robot import Robot, RobotInfo
from ..data_collection.price_bot import OHLCData

@dataclass
class FVG:
    id: str  # e.g., "XAUUSD_M5_{timestamp}"
    symbol: str
    timeframe: str
    fvg_type: str  # "BULLISH" or "BEARISH"
    top: float
    bottom: float
    created_at: datetime
    mitigated: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'fvg_type': self.fvg_type,
            'top': self.top,
            'bottom': self.bottom,
            'created_at': self.created_at.isoformat(),
            'mitigated': self.mitigated
        }

class FVGBot(Robot):
    """
    Fair Value Gap Analysis Bot
    
    Monitors a rolling 3-candle buffer to identify gaps where C1 and C3
    fail to overlap, signifying institutional volume displacement.
    """
    
    def __init__(self, robot_info: RobotInfo, config: Dict[str, Any], 
                 message_bus=None, mongo_manager=None):
        super().__init__(robot_info, config)
        
        self.message_bus = message_bus
        self.mongo = mongo_manager
        
        # We need a 3-candle history lock
        self._history: Dict[str, Dict[str, deque]] = {}
        
        # Track unmitigated setups dynamically
        self._active_fvgs: List[FVG] = []
        
    async def initialize(self) -> bool:
        """Initialize the FVG Analysis Bot."""
        self.logger.info(f"Initializing {self.robot_id}...")
        if self.message_bus:
            self.set_message_bus(self.message_bus)
        return True
        
    async def process(self, data: Any = None) -> Any:
        """Main loop eagerly awaits finalized candles."""
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
            self.logger.error(f"Error checking FVGs: {e}")
            
        return None

    async def _process_candle(self, candle: OHLCData) -> None:
        """Adds a candle to the history queue, sweeps old FVGs, configures new FVGs."""
        sym = candle.symbol
        tf = candle.timeframe
        
        # Track historical buffering locally
        if sym not in self._history:
            self._history[sym] = {}
        if tf not in self._history[sym]:
            self._history[sym][tf] = deque(maxlen=3)
            
        history = self._history[sym][tf]
        
        # Check active tracking for Mitigation FIRST using the new candle
        await self._check_mitigation(candle)
        
        # Apply the new candle array offset
        history.append(candle)
        
        # Evaluate FVG Generation
        if len(history) == 3:
            await self._detect_fvg(history, sym, tf)

    async def _detect_fvg(self, history: deque, symbol: str, timeframe: str) -> None:
        """
        Parses array indices:
        c1 (Oldest), c2 (Displacement), c3 (Newest forming the gap validation)
        """
        c1, c2, c3 = history[0], history[1], history[2]
        
        fvg: Optional[FVG] = None
        
        # Bullish FVG Check: C1 High must be strictly below C3 Low
        if c1.high < c3.low:
            fvg = FVG(
                id=f"{symbol}_{timeframe}_{int(c3.timestamp.timestamp())}_BULL",
                symbol=symbol,
                timeframe=timeframe,
                fvg_type="BULLISH",
                top=c3.low,
                bottom=c1.high,
                created_at=c3.timestamp
            )
            
        # Bearish FVG Check: C1 Low must be strictly above C3 High
        elif c1.low > c3.high:
            fvg = FVG(
                id=f"{symbol}_{timeframe}_{int(c3.timestamp.timestamp())}_BEAR",
                symbol=symbol,
                timeframe=timeframe,
                fvg_type="BEARISH",
                top=c1.low,
                bottom=c3.high,
                created_at=c3.timestamp
            )
            
        if fvg is not None:
            self._active_fvgs.append(fvg)
            await self._dispatch_event('fvg_formed', fvg)

    async def _check_mitigation(self, candle: OHLCData) -> None:
        """
        Evaluates incoming price thresholds against tracked unmitigated blocks.
        A block is considered mitigated if price completely closes the gap.
        """
        surviving_fvgs = []
        
        for fvg in self._active_fvgs:
            # We strictly evaluate matching symbols/timeframes to ensure scaling mapping
            if fvg.symbol != candle.symbol or fvg.timeframe != candle.timeframe:
                surviving_fvgs.append(fvg)
                continue
                
            mitigated = False
            
            # For a Bullish FVG (Top=C3.low, Bottom=C1.high), mitigation occurs down into the block.
            # We consider fully mitigated if the new candle Low sweeps below the FVG bottom.
            if fvg.fvg_type == "BULLISH":
                if candle.low <= fvg.bottom:
                    mitigated = True
                    
            # For a Bearish FVG, mitigation occurs up into the block.
            # We consider fully mitigated if the new candle High sweeps above the FVG top.
            elif fvg.fvg_type == "BEARISH":
                if candle.high >= fvg.top:
                    mitigated = True
                    
            if mitigated:
                fvg.mitigated = True
                await self._dispatch_event('fvg_mitigated', fvg)
            else:
                surviving_fvgs.append(fvg)
                
        self._active_fvgs = surviving_fvgs

    async def _dispatch_event(self, event_type: str, fvg: FVG) -> None:
        """Broadcasts FVG state changes to decision and logging tiers."""
        payload = fvg.to_dict()
        
        if self._message_bus:
            await self.send_message(event_type, payload)
            
        if self.mongo:
            # We log FVG events organically to track strategy analytics over time
            self.mongo.insert_log({
                'level': 'INFO',
                'component': self.robot_id,
                'message': f"{event_type.upper()}: {fvg.fvg_type} [{fvg.bottom} - {fvg.top}] on {fvg.symbol}({fvg.timeframe})",
                'data': payload,
                'timestamp': datetime.now().isoformat()
            })

    async def cleanup(self) -> None:
        """Cleanup gracefully."""
        self.logger.info(f"Cleaning up {self.robot_id}...")
        self._active_fvgs.clear()
        self._history.clear()
