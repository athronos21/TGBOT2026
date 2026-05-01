"""
Liquidity Bot - Liquidity Analysis

Analyzes market liquidity including:
- Equal highs/lows detection
- Liquidity sweep detection
- Order cluster detection
- Liquidity zone marking
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


class LiquidityType(Enum):
    SUPPORT = "support"
    RESISTANCE = "resistance"
    SWEEP = "sweep"
    CLUSTER = "cluster"


@dataclass
class LiquidityZone:
    """Liquidity zone data"""
    symbol: str
    timeframe: str
    zone_type: LiquidityType
    price_low: float
    price_high: float
    volume: float
    timestamp: datetime
    strength: float = 0.0


class LiquidityBot(Robot):
    """
    Analyzes market liquidity and order clusters.
    
    Detects:
    - Equal highs/lows (support/resistance)
    - Liquidity sweeps
    - Order clusters
    - Liquidity zones
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
        """Initialize the Liquidity Bot"""
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
        """Process market data and analyze liquidity"""
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
            
        # Analyze liquidity
        liquidity = self._analyze_liquidity(candles, symbol, timeframe)
        
        # Publish results
        await self.send_message('liquidity_analysis', {
            'symbol': symbol,
            'timeframe': timeframe,
            'liquidity': liquidity,
            'timestamp': datetime.now().isoformat()
        })
        
        # Store in database
        await self._store_analysis(liquidity)
        
        return liquidity
        
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
        
    def _analyze_liquidity(self, candles: List, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Analyze liquidity from candles"""
        if len(candles) < 3:
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'error': 'Insufficient data'
            }
            
        highs = [candle[2] for candle in candles]
        lows = [candle[3] for candle in candles]
        volumes = [candle[5] for candle in candles] if len(candles[0]) > 5 else [1] * len(candles)
        
        # Detect equal highs/lows
        equal_highs = self._detect_equal_highs(highs)
        equal_lows = self._detect_equal_lows(lows)
        
        # Detect liquidity sweeps
        sweeps = self._detect_liquidity_sweeps(highs, lows)
        
        # Detect order clusters
        clusters = self._detect_order_clusters(highs, lows, volumes)
        
        # Mark liquidity zones
        zones = self._mark_liquidity_zones(equal_highs, equal_lows, sweeps, clusters)
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.now().isoformat(),
            'equal_highs': equal_highs,
            'equal_lows': equal_lows,
            'liquidity_sweeps': sweeps,
            'order_clusters': clusters,
            'liquidity_zones': zones
        }
        
    def _detect_equal_highs(self, highs: List[float]) -> List[Dict[str, Any]]:
        """Detect equal/higher highs (resistance levels)"""
        equal_highs = []
        for i in range(1, len(highs) - 1):
            # Check for equal highs within tolerance
            tolerance = (highs[i] - highs[i-1]) / highs[i-1] if highs[i-1] > 0 else 0.001
            if abs(tolerance) < 0.001:  # 0.1% tolerance
                equal_highs.append({
                    'index': i,
                    'price': highs[i],
                    'timestamp': datetime.now().isoformat()
                })
        return equal_highs
        
    def _detect_equal_lows(self, lows: List[float]) -> List[Dict[str, Any]]:
        """Detect equal/lower lows (support levels)"""
        equal_lows = []
        for i in range(1, len(lows) - 1):
            tolerance = (lows[i] - lows[i-1]) / lows[i-1] if lows[i-1] > 0 else 0.001
            if abs(tolerance) < 0.001:
                equal_lows.append({
                    'index': i,
                    'price': lows[i],
                    'timestamp': datetime.now().isoformat()
                })
        return equal_lows
        
    def _detect_liquidity_sweeps(self, highs: List[float], lows: List[float]) -> List[Dict[str, Any]]:
        """Detect liquidity sweeps (price moving beyond recent extremes)"""
        sweeps = []
        if len(highs) < 5:
            return sweeps
            
        recent_high = max(highs[-5:])
        recent_low = min(lows[-5:])
        
        # Check for sweep beyond recent high
        if highs[-1] > recent_high:
            sweeps.append({
                'type': 'bullish_sweep',
                'price': highs[-1],
                'timestamp': datetime.now().isoformat()
            })
            
        # Check for sweep beyond recent low
        if lows[-1] < recent_low:
            sweeps.append({
                'type': 'bearish_sweep',
                'price': lows[-1],
                'timestamp': datetime.now().isoformat()
            })
            
        return sweeps
        
    def _detect_order_clusters(self, highs: List[float], lows: List[float],
                                volumes: List[float]) -> List[Dict[str, Any]]:
        """Detect order clusters (areas with high volume)"""
        clusters = []
        if len(highs) < 10:
            return clusters
            
        # Calculate average volume
        avg_volume = sum(volumes) / len(volumes)
        
        # Find price levels with high volume
        price_volume_map = {}
        for i, (high, low, volume) in enumerate(zip(highs, lows, volumes)):
            if volume > avg_volume * 1.5:  # 50% above average
                mid_price = (high + low) / 2
                if mid_price not in price_volume_map:
                    price_volume_map[mid_price] = 0
                price_volume_map[mid_price] += volume
                
        # Convert to clusters
        for price, total_volume in price_volume_map.items():
            if total_volume > avg_volume * 3:  # 3x average
                clusters.append({
                    'price': price,
                    'total_volume': total_volume,
                    'timestamp': datetime.now().isoformat()
                })
                
        return clusters
        
    def _mark_liquidity_zones(self, equal_highs: List, equal_lows: List,
                               sweeps: List, clusters: List) -> List[Dict[str, Any]]:
        """Mark liquidity zones based on detected patterns"""
        zones = []
        
        # Mark support zones from equal lows
        for low in equal_lows:
            zones.append({
                'symbol': 'XAUUSD',
                'timeframe': 'H1',
                'zone_type': 'support',
                'price_low': low['price'] * 0.999,
                'price_high': low['price'] * 1.001,
                'volume': 0,
                'timestamp': low['timestamp'],
                'strength': 0.7
            })
            
        # Mark resistance zones from equal highs
        for high in equal_highs:
            zones.append({
                'symbol': 'XAUUSD',
                'timeframe': 'H1',
                'zone_type': 'resistance',
                'price_low': high['price'] * 0.999,
                'price_high': high['price'] * 1.001,
                'volume': 0,
                'timestamp': high['timestamp'],
                'strength': 0.7
            })
            
        # Mark sweep zones
        for sweep in sweeps:
            zones.append({
                'symbol': 'XAUUSD',
                'timeframe': 'H1',
                'zone_type': 'sweep',
                'price_low': sweep['price'] * 0.999,
                'price_high': sweep['price'] * 1.001,
                'volume': 0,
                'timestamp': sweep['timestamp'],
                'strength': 0.8
            })
            
        # Mark cluster zones
        for cluster in clusters:
            zones.append({
                'symbol': 'XAUUSD',
                'timeframe': 'H1',
                'zone_type': 'cluster',
                'price_low': cluster['price'] * 0.999,
                'price_high': cluster['price'] * 1.001,
                'volume': cluster['total_volume'],
                'timestamp': cluster['timestamp'],
                'strength': 0.9
            })
            
        return zones
        
    async def _store_analysis(self, liquidity: Dict[str, Any]):
        """Store analysis results in database"""
        if not self.postgres or not self.mongodb:
            return
            
        try:
            analysis_data = {
                'symbol': liquidity['symbol'],
                'analysis_type': 'liquidity',
                'result_data': liquidity,
                'confidence': 0.7,
                'timestamp': liquidity.get('timestamp'),
                'robot_id': self.robot_id
            }
            await self.postgres.insert_analysis_result(analysis_data)
            
            log_data = {
                'timestamp': datetime.now(),
                'level': 'INFO',
                'robot_id': self.robot_id,
                'message': f"Liquidity analysis completed for {liquidity['symbol']}",
                'context': {
                    'timeframe': liquidity.get('timeframe'),
                    'equal_highs': len(liquidity.get('equal_highs', [])),
                    'equal_lows': len(liquidity.get('equal_lows', [])),
                    'sweeps': len(liquidity.get('liquidity_sweeps', []))
                }
            }
            self.mongodb.insert_system_log(log_data)
            
        except Exception as e:
            self.logger.error(f"Failed to store analysis: {e}")
