"""
Structure Bot - Market Structure Analysis

Analyzes market structure including:
- Higher highs/lows detection
- BOS (Break of Structure) detection
- CHOCH (Change of Character) detection
- Trend determination
- Multi-timeframe analysis
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.core.robot import Robot, RobotInfo, RobotState
from src.core.message_bus import MessageBus
from src.database.postgresql_manager import PostgreSQLManager
from src.database.mongodb_manager import MongoDBManager


class Trend(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class StructureData:
    """Market structure data"""
    symbol: str
    timeframe: str
    timestamp: datetime
    higher_high: Optional[float] = None
    higher_low: Optional[float] = None
    lower_high: Optional[float] = None
    lower_low: Optional[float] = None
    bos_detected: bool = False
    choch_detected: bool = False
    trend: Trend = Trend.NEUTRAL
    trend_strength: float = 0.0


class StructureBot(Robot):
    """
    Analyzes market structure and trends.
    
    Detects:
    - Higher highs and higher lows (bullish structure)
    - Lower highs and lower lows (bearish structure)
    - Break of structure (BOS)
    - Change of character (CHOCH)
    - Trend direction and strength
    """
    
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.logger = logging.getLogger(__name__)
        self.symbols = config.get('symbols', ['XAUUSD'])
        self.timeframes = config.get('timeframes', ['M15', 'H1', 'H4'])
        self.lookback_periods = config.get('lookback_periods', 100)
        self.mt5 = None
        self.postgres = None
        self.mongodb = None
        
    async def initialize(self):
        """Initialize the Structure Bot"""
        self.logger.info(f"Initializing {self.robot_id}...")
        
        # Import MT5 connection
        from src.integrations.mt5_connection import MT5Connection
        self.mt5 = MT5Connection(self.config.get('mt5', {}))
        
        # Initialize database managers
        self.postgres = PostgreSQLManager(self.config.get('database', {}).get('postgresql', {}))
        self.mongodb = MongoDBManager(self.config.get('database', {}).get('mongodb', {}))
        
        # Connect to databases
        await self.postgres.connect()
        self.mongodb.connect()
        
        # Setup collections
        self.mongodb.create_system_logs_collection()
        self.mongodb.create_configurations_collection()
        
        self.logger.info(f"{self.robot_id} initialized successfully")
        
    async def process(self, data: Any) -> Any:
        """Process market data and analyze structure"""
        if data is None:
            return None
            
        symbol = data.get('symbol', 'XAUUSD')
        timeframe = data.get('timeframe', 'H1')
        
        # Get candles for analysis
        candles = await self.mt5.get_candles(
            symbol,
            self._timeframe_to_mt5(timeframe),
            self.lookback_periods
        )
        
        if candles is None:
            self.logger.error(f"Failed to get candles for {symbol} {timeframe}")
            return None
            
        # Analyze structure
        structure = self._analyze_structure(candles, symbol, timeframe)
        
        # Publish results
        await self.send_message('structure_analysis', {
            'symbol': symbol,
            'timeframe': timeframe,
            'structure': structure,
            'timestamp': datetime.now().isoformat()
        })
        
        # Store in database
        await self._store_analysis(structure)
        
        return structure
        
    async def cleanup(self):
        """Cleanup resources"""
        if self.postgres:
            await self.postgres.disconnect()
        if self.mongodb:
            self.mongodb.disconnect()
        self.logger.info(f"{self.robot_id} cleaned up")
        
    def _timeframe_to_mt5(self, timeframe: str) -> int:
        """Convert timeframe string to MT5 constant"""
        timeframe_map = {
            'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30,
            'H1': 63, 'H4': 64, 'D1': 65, 'W1': 66, 'MN1': 67
        }
        return timeframe_map.get(timeframe, 64)  # Default to H1
        
    def _analyze_structure(self, candles: List, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Analyze market structure from candles"""
        if len(candles) < 3:
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'error': 'Insufficient data'
            }
            
        highs = [candle[2] for candle in candles]  # High prices
        lows = [candle[3] for candle in candles]   # Low prices
        
        # Detect higher highs and higher lows
        hh = self._detect_higher_highs(highs)
        hl = self._detect_higher_lows(lows)
        
        # Detect lower highs and lower lows
        lh = self._detect_lower_highs(highs)
        ll = self._detect_lower_lows(lows)
        
        # Detect BOS and CHOCH
        bos = self._detect_bos(candles)
        choch = self._detect_choch(candles)
        
        # Determine trend
        trend = self._determine_trend(hh, hl, lh, ll, bos, choch)
        
        # Calculate trend strength
        trend_strength = self._calculate_trend_strength(hh, hl, lh, ll, candles)
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.now().isoformat(),
            'structure': {
                'higher_highs': hh,
                'higher_lows': hl,
                'lower_highs': lh,
                'lower_lows': ll
            },
            'bos_detected': bos is not None,
            'choch_detected': choch is not None,
            'trend': trend.value,
            'trend_strength': trend_strength,
            'bos_data': bos,
            'choch_data': choch
        }
        
    def _detect_higher_highs(self, highs: List[float]) -> List[Dict[str, Any]]:
        """Detect higher highs in price series"""
        hh = []
        for i in range(1, len(highs) - 1):
            if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                hh.append({
                    'index': i,
                    'price': highs[i],
                    'timestamp': datetime.now().isoformat()
                })
        return hh
        
    def _detect_higher_lows(self, lows: List[float]) -> List[Dict[str, Any]]:
        """Detect higher lows in price series"""
        hl = []
        for i in range(1, len(lows) - 1):
            if lows[i] > lows[i-1] and lows[i] < lows[i+1]:
                hl.append({
                    'index': i,
                    'price': lows[i],
                    'timestamp': datetime.now().isoformat()
                })
        return hl
        
    def _detect_lower_highs(self, highs: List[float]) -> List[Dict[str, Any]]:
        """Detect lower highs in price series"""
        lh = []
        for i in range(1, len(highs) - 1):
            if highs[i] < highs[i-1] and highs[i] > highs[i+1]:
                lh.append({
                    'index': i,
                    'price': highs[i],
                    'timestamp': datetime.now().isoformat()
                })
        return lh
        
    def _detect_lower_lows(self, lows: List[float]) -> List[Dict[str, Any]]:
        """Detect lower lows in price series"""
        ll = []
        for i in range(1, len(lows) - 1):
            if lows[i] < lows[i-1] and lows[i] > lows[i+1]:
                ll.append({
                    'index': i,
                    'price': lows[i],
                    'timestamp': datetime.now().isoformat()
                })
        return ll
        
    def _detect_bos(self, candles: List) -> Optional[Dict[str, Any]]:
        """Detect Break of Structure"""
        if len(candles) < 5:
            return None
            
        # Get recent price action
        recent_highs = [candle[2] for candle in candles[-5:]]
        recent_lows = [candle[3] for candle in candles[-5:]]
        
        # Check for BOS
        if recent_highs[-1] > max(recent_highs[:-1]):
            return {
                'type': 'bullish_bos',
                'price': recent_highs[-1],
                'timestamp': datetime.now().isoformat()
            }
        elif recent_lows[-1] < min(recent_lows[:-1]):
            return {
                'type': 'bearish_bos',
                'price': recent_lows[-1],
                'timestamp': datetime.now().isoformat()
            }
        return None
        
    def _detect_choch(self, candles: List) -> Optional[Dict[str, Any]]:
        """Detect Change of Character"""
        if len(candles) < 3:
            return None
            
        # Check for trend reversal
        close_prices = [candle[4] for candle in candles[-3:]]
        
        if close_prices[-1] < close_prices[0] < close_prices[1]:
            return {
                'type': 'bullish_choch',
                'price': close_prices[-1],
                'timestamp': datetime.now().isoformat()
            }
        elif close_prices[-1] > close_prices[0] > close_prices[1]:
            return {
                'type': 'bearish_choch',
                'price': close_prices[-1],
                'timestamp': datetime.now().isoformat()
            }
        return None
        
    def _determine_trend(self, hh: List, hl: List, lh: List, ll: List,
                         bos: Optional[Dict], choch: Optional[Dict]) -> Trend:
        """Determine overall trend"""
        if not hh and not hl and not lh and not ll:
            return Trend.NEUTRAL
            
        # Count structure points
        bullish_points = len(hh) + len(hl)
        bearish_points = len(lh) + len(ll)
        
        # Check for BOS/CHOCH
        if bos:
            if bos['type'] == 'bullish_bos':
                bullish_points += 2
            else:
                bearish_points += 2
                
        if choch:
            if choch['type'] == 'bullish_choch':
                bullish_points += 2
            else:
                bearish_points += 2
                
        # Determine trend
        if bullish_points > bearish_points:
            return Trend.BULLISH
        elif bearish_points > bullish_points:
            return Trend.BEARISH
        return Trend.NEUTRAL
        
    def _calculate_trend_strength(self, hh: List, hl: List, lh: List, ll: List,
                                   candles: List) -> float:
        """Calculate trend strength (0-1)"""
        total_points = len(hh) + len(hl) + len(lh) + len(ll)
        if total_points == 0:
            return 0.0
            
        # Calculate based on structure consistency
        bullish_ratio = (len(hh) + len(hl)) / total_points
        bearish_ratio = (len(lh) + len(ll)) / total_points
        
        # Consider recent price action
        if len(candles) >= 3:
            close_prices = [candle[4] for candle in candles[-3:]]
            if close_prices[-1] > close_prices[0]:
                bullish_ratio += 0.1
            else:
                bearish_ratio += 0.1
                
        return max(bullish_ratio, bearish_ratio)
        
    async def _store_analysis(self, structure: Dict[str, Any]):
        """Store analysis results in database"""
        if not self.postgres or not self.mongodb:
            return
            
        try:
            # Store in PostgreSQL
            analysis_data = {
                'symbol': structure['symbol'],
                'analysis_type': 'structure',
                'result_data': structure,
                'confidence': structure.get('trend_strength', 0.5),
                'timestamp': structure.get('timestamp'),
                'robot_id': self.robot_id
            }
            await self.postgres.insert_analysis_result(analysis_data)
            
            # Log to MongoDB
            log_data = {
                'timestamp': datetime.now(),
                'level': 'INFO',
                'robot_id': self.robot_id,
                'message': f"Structure analysis completed for {structure['symbol']}",
                'context': {
                    'timeframe': structure.get('timeframe'),
                    'trend': structure.get('trend'),
                    'bos_detected': structure.get('bos_detected', False),
                    'choch_detected': structure.get('choch_detected', False)
                }
            }
            self.mongodb.insert_system_log(log_data)
            
        except Exception as e:
            self.logger.error(f"Failed to store analysis: {e}")
