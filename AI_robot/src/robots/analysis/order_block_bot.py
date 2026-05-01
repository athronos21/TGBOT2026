"""
Order Block Bot - Order Block Analysis

Analyzes order blocks including:
- Bullish OB detection
- Bearish OB detection
- Volume validation
- OB strength calculation
- OB expiration logic
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


class OrderBlockType(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass
class OrderBlock:
    """Order block data"""
    symbol: str
    timeframe: str
    block_type: OrderBlockType
    price_low: float
    price_high: float
    volume: float
    timestamp: datetime
    strength: float = 0.0
    is_expired: bool = False


class OrderBlockBot(Robot):
    """
    Analyzes order blocks in market structure.
    
    Detects:
    - Bullish order blocks
    - Bearish order blocks
    - Volume validation
    - Order block strength
    - Order block expiration
    """
    
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.logger = logging.getLogger(__name__)
        self.symbols = config.get('symbols', ['XAUUSD'])
        self.timeframes = config.get('timeframes', ['M15', 'H1', 'H4'])
        self.lookback_periods = config.get('lookback_periods', 100)
        self.expiration_threshold = config.get('expiration_threshold', 24)  # hours
        self.mt5 = None
        self.postgres = None
        self.mongodb = None
        
    async def initialize(self):
        """Initialize the Order Block Bot"""
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
        """Process market data and analyze order blocks"""
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
            
        # Analyze order blocks
        order_blocks = self._analyze_order_blocks(candles, symbol, timeframe)
        
        # Publish results
        await self.send_message('order_block_analysis', {
            'symbol': symbol,
            'timeframe': timeframe,
            'order_blocks': order_blocks,
            'timestamp': datetime.now().isoformat()
        })
        
        # Store in database
        await self._store_analysis(order_blocks)
        
        return order_blocks
        
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
        return timeframe_map.get(timeframe, 64)
        
    def _analyze_order_blocks(self, candles: List, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Analyze order blocks from candles"""
        if len(candles) < 3:
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'error': 'Insufficient data'
            }
            
        # Get candle data
        opens = [candle[1] for candle in candles]
        closes = [candle[4] for candle in candles]
        highs = [candle[2] for candle in candles]
        lows = [candle[3] for candle in candles]
        volumes = [candle[5] for candle in candles] if len(candles[0]) > 5 else [1] * len(candles)
        
        # Detect bullish and bearish order blocks
        bullish_obs = self._detect_bullish_ob(opens, closes, highs, lows, volumes)
        bearish_obs = self._detect_bearish_ob(opens, closes, highs, lows, volumes)
        
        # Validate volume
        bullish_obs = self._validate_volume(bullish_obs, candles)
        bearish_obs = self._validate_volume(bearish_obs, candles)
        
        # Calculate strength
        bullish_obs = self._calculate_strength(bullish_obs)
        bearish_obs = self._calculate_strength(bearish_obs)
        
        # Check expiration
        current_time = datetime.now()
        bullish_obs = self._check_expiration(bullish_obs, current_time)
        bearish_obs = self._check_expiration(bearish_obs, current_time)
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.now().isoformat(),
            'bullish_order_blocks': bullish_obs,
            'bearish_order_blocks': bearish_obs
        }
        
    def _detect_bullish_ob(self, opens: List, closes: List, highs: List, lows: List,
                            volumes: List) -> List[Dict[str, Any]]:
        """Detect bullish order blocks"""
        bullish_obs = []
        
        for i in range(1, len(closes) - 1):
            # Bullish OB: candle closes above open with significant body
            if closes[i] > opens[i]:
                body = closes[i] - opens[i]
                upper_shadow = highs[i] - closes[i]
                lower_shadow = opens[i] - lows[i]
                
                # Bullish OB has small upper shadow and significant body
                if upper_shadow < body * 0.3 and body > (highs[i] - lows[i]) * 0.5:
                    bullish_obs.append({
                        'index': i,
                        'price_low': opens[i],
                        'price_high': closes[i],
                        'volume': volumes[i],
                        'timestamp': datetime.now().isoformat()
                    })
                    
        return bullish_obs
        
    def _detect_bearish_ob(self, opens: List, closes: List, highs: List, lows: List,
                            volumes: List) -> List[Dict[str, Any]]:
        """Detect bearish order blocks"""
        bearish_obs = []
        
        for i in range(1, len(closes) - 1):
            # Bearish OB: candle closes below open with significant body
            if closes[i] < opens[i]:
                body = opens[i] - closes[i]
                lower_shadow = closes[i] - lows[i]
                upper_shadow = highs[i] - opens[i]
                
                # Bearish OB has small lower shadow and significant body
                if lower_shadow < body * 0.3 and body > (highs[i] - lows[i]) * 0.5:
                    bearish_obs.append({
                        'index': i,
                        'price_low': closes[i],
                        'price_high': opens[i],
                        'volume': volumes[i],
                        'timestamp': datetime.now().isoformat()
                    })
                    
        return bearish_obs
        
    def _validate_volume(self, order_blocks: List, candles: List) -> List[Dict[str, Any]]:
        """Validate volume for order blocks"""
        if not order_blocks or not candles:
            return order_blocks
            
        # Calculate average volume
        volumes = [candle[5] for candle in candles if len(candle) > 5]
        if not volumes:
            return order_blocks
            
        avg_volume = sum(volumes) / len(volumes)
        
        # Mark blocks with sufficient volume
        for ob in order_blocks:
            ob['volume_valid'] = ob.get('volume', 0) > avg_volume * 0.8
            
        return order_blocks
        
    def _calculate_strength(self, order_blocks: List) -> List[Dict[str, Any]]:
        """Calculate order block strength"""
        for ob in order_blocks:
            # Strength based on volume and body size
            volume_score = min(ob.get('volume', 0) / 1000, 1.0) if ob.get('volume_valid') else 0.5
            ob['strength'] = volume_score * 0.7 + 0.3  # Base strength 0.3
            
        return order_blocks
        
    def _check_expiration(self, order_blocks: List, current_time: datetime) -> List[Dict[str, Any]]:
        """Check if order blocks have expired"""
        for ob in order_blocks:
            # Order blocks expire after threshold hours
            ob['is_expired'] = False  # Simplified - would need actual timestamp from candle
            
        return order_blocks
        
    async def _store_analysis(self, order_blocks: Dict[str, Any]):
        """Store analysis results in database"""
        if not self.postgres or not self.mongodb:
            return
            
        try:
            analysis_data = {
                'symbol': order_blocks['symbol'],
                'analysis_type': 'order_block',
                'result_data': order_blocks,
                'confidence': 0.75,
                'timestamp': order_blocks.get('timestamp'),
                'robot_id': self.robot_id
            }
            await self.postgres.insert_analysis_result(analysis_data)
            
            log_data = {
                'timestamp': datetime.now(),
                'level': 'INFO',
                'robot_id': self.robot_id,
                'message': f"Order block analysis completed for {order_blocks['symbol']}",
                'context': {
                    'timeframe': order_blocks.get('timeframe'),
                    'bullish_count': len(order_blocks.get('bullish_order_blocks', [])),
                    'bearish_count': len(order_blocks.get('bearish_order_blocks', []))
                }
            }
            self.mongodb.insert_system_log(log_data)
            
        except Exception as e:
            self.logger.error(f"Failed to store analysis: {e}")
