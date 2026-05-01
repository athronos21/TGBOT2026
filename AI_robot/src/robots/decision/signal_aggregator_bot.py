"""
Signal Aggregator Bot - Signal Aggregation and Generation

Aggregates signals from analysis bots and generates trade signals including:
- Analysis caching
- Signal generation logic
- Confluence checking
- Confidence scoring
- Entry zone calculation
- SL/TP calculation
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


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


@dataclass
class TradeSignal:
    """Trade signal data"""
    signal_id: str
    symbol: str
    signal_type: SignalType
    confidence: float
    entry_zone: Dict[str, float]
    stop_loss: float
    take_profit: float
    timestamp: datetime
    factors: Dict[str, Any] = None


class SignalAggregatorBot(Robot):
    """
    Aggregates signals from analysis bots and generates trade signals.
    
    Features:
    - Analysis caching
    - Signal generation from multiple sources
    - Confluence checking
    - Confidence scoring
    - Entry zone calculation
    - SL/TP calculation
    """
    
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.logger = logging.getLogger(__name__)
        self.symbols = config.get('symbols', ['XAUUSD'])
        self.required_analyses = ['structure_analysis', 'liquidity_analysis', 'order_block_analysis']
        self.analysis_cache: Dict[str, Dict] = {}
        self.signal_threshold = config.get('signal_threshold', 0.7)
        self.mt5 = None
        self.postgres = None
        self.mongodb = None
        
    async def initialize(self):
        """Initialize the Signal Aggregator Bot"""
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
        """Process analysis data and aggregate signals"""
        if data is None:
            return None
            
        analysis_type = data.get('analysis_type')
        if not analysis_type:
            return None
            
        symbol = data.get('symbol', 'XAUUSD')
        
        # Cache the analysis
        self.analysis_cache[symbol] = self.analysis_cache.get(symbol, {})
        self.analysis_cache[symbol][analysis_type] = data
        
        # Check if we have all required analyses
        if self.has_all_analyses(symbol):
            signal = await self.generate_signal(symbol)
            if signal:
                await self.send_message('trade_signal', signal)
                await self._store_signal(signal)
            self.analysis_cache[symbol].clear()
            return signal
            
        return None
        
    async def cleanup(self):
        """Cleanup resources"""
        if self.postgres:
            await self.postgres.disconnect()
        if self.mongodb:
            self.mongodb.disconnect()
        self.logger.info(f"{self.robot_id} cleaned up")
        
    def has_all_analyses(self, symbol: str) -> bool:
        """Check if all required analyses are available"""
        if symbol not in self.analysis_cache:
            return False
        return all(a in self.analysis_cache[symbol] for a in self.required_analyses)
        
    async def generate_signal(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Generate trade signal from aggregated analyses"""
        analyses = self.analysis_cache.get(symbol, {})
        
        structure = analyses.get('structure_analysis', {})
        liquidity = analyses.get('liquidity_analysis', {})
        order_block = analyses.get('order_block_analysis', {})
        
        # Determine signal direction
        signal_type = self._determine_signal_type(structure, liquidity, order_block)
        
        if signal_type == SignalType.NEUTRAL:
            return None
            
        # Calculate confidence
        confidence = self._calculate_confidence(structure, liquidity, order_block)
        
        # Check threshold
        if confidence < self.signal_threshold:
            return None
            
        # Calculate entry zone
        entry_zone = self._calculate_entry_zone(order_block)
        
        # Calculate SL/TP
        stop_loss, take_profit = self._calculate_sl_tp(structure, liquidity, entry_zone, signal_type)
        
        return {
            'signal_id': f"SIG_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'symbol': symbol,
            'signal_type': signal_type.value,
            'confidence': confidence,
            'entry_zone': entry_zone,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'timestamp': datetime.now().isoformat(),
            'factors': {
                'structure': structure.get('trend', 'neutral'),
                'liquidity_zones': len(liquidity.get('liquidity_zones', [])),
                'order_blocks': len(order_block.get('bullish_order_blocks', [])) + len(order_block.get('bearish_order_blocks', []))
            }
        }
        
    def _determine_signal_type(self, structure: Dict, liquidity: Dict, order_block: Dict) -> SignalType:
        """Determine signal direction from analyses"""
        # Get trend from structure
        trend = structure.get('trend', 'neutral')
        
        # Get liquidity zones
        liquidity_zones = liquidity.get('liquidity_zones', [])
        support_zones = [z for z in liquidity_zones if z.get('zone_type') == 'support']
        resistance_zones = [z for z in liquidity_zones if z.get('zone_type') == 'resistance']
        
        # Get order blocks
        bullish_obs = order_block.get('bullish_order_blocks', [])
        bearish_obs = order_block.get('bearish_order_blocks', [])
        
        # Determine signal
        if trend == 'bullish' and len(bullish_obs) > len(bearish_obs):
            return SignalType.BUY
        elif trend == 'bearish' and len(bearish_obs) > len(bullish_obs):
            return SignalType.SELL
        elif len(support_zones) > len(resistance_zones):
            return SignalType.BUY
        elif len(resistance_zones) > len(support_zones):
            return SignalType.SELL
        else:
            return SignalType.NEUTRAL
            
    def _calculate_confidence(self, structure: Dict, liquidity: Dict, order_block: Dict) -> float:
        """Calculate signal confidence (0-1)"""
        confidence = 0.5  # Base confidence
        
        # Structure confidence
        trend = structure.get('trend', 'neutral')
        trend_strength = structure.get('trend_strength', 0.5)
        if trend != 'neutral':
            confidence += trend_strength * 0.2
            
        # Liquidity confidence
        liquidity_zones = liquidity.get('liquidity_zones', [])
        if len(liquidity_zones) > 0:
            confidence += min(len(liquidity_zones) * 0.05, 0.15)
            
        # Order block confidence
        bullish_obs = order_block.get('bullish_order_blocks', [])
        bearish_obs = order_block.get('bearish_order_blocks', [])
        total_obs = len(bullish_obs) + len(bearish_obs)
        if total_obs > 0:
            ob_confidence = max(len(bullish_obs), len(bearish_obs)) / total_obs
            confidence += ob_confidence * 0.15
            
        # BOS/CHOCH confidence
        if structure.get('bos_detected'):
            confidence += 0.1
        if structure.get('choch_detected'):
            confidence += 0.1
            
        return min(confidence, 1.0)
        
    def _calculate_entry_zone(self, order_block: Dict) -> Dict[str, float]:
        """Calculate entry zone from order blocks"""
        bullish_obs = order_block.get('bullish_order_blocks', [])
        bearish_obs = order_block.get('bearish_order_blocks', [])
        
        if bullish_obs:
            ob = bullish_obs[-1]  # Most recent bullish OB
            return {
                'low': ob.get('price_low', 0),
                'high': ob.get('price_high', 0),
                'mid': (ob.get('price_low', 0) + ob.get('price_high', 0)) / 2
            }
        elif bearish_obs:
            ob = bearish_obs[-1]  # Most recent bearish OB
            return {
                'low': ob.get('price_low', 0),
                'high': ob.get('price_high', 0),
                'mid': (ob.get('price_low', 0) + ob.get('price_high', 0)) / 2
            }
        else:
            return {'low': 0, 'high': 0, 'mid': 0}
            
    def _calculate_sl_tp(self, structure: Dict, liquidity: Dict, entry_zone: Dict,
                         signal_type: SignalType) -> tuple:
        """Calculate stop loss and take profit levels"""
        entry_mid = entry_zone.get('mid', 0)
        
        # Get support/resistance levels from liquidity
        liquidity_zones = liquidity.get('liquidity_zones', [])
        support_levels = [z.get('price_low', 0) for z in liquidity_zones if z.get('zone_type') == 'support']
        resistance_levels = [z.get('price_high', 0) for z in liquidity_zones if z.get('zone_type') == 'resistance']
        
        # Calculate SL based on signal type
        if signal_type == SignalType.BUY:
            # SL below nearest support
            sl = min(support_levels) if support_levels else entry_mid * 0.99
            # TP at nearest resistance
            tp = max(resistance_levels) if resistance_levels else entry_mid * 1.02
        else:
            # SL above nearest resistance
            sl = max(resistance_levels) if resistance_levels else entry_mid * 1.01
            # TP at nearest support
            tp = min(support_levels) if support_levels else entry_mid * 0.98
            
        return sl, tp
        
    async def _store_signal(self, signal: Dict[str, Any]):
        """Store signal in database"""
        if not self.postgres or not self.mongodb:
            return
            
        try:
            signal_data = {
                'symbol': signal['symbol'],
                'signal_type': signal['signal_type'],
                'confidence': signal['confidence'],
                'strength': signal.get('confidence', 0.5),
                'factors': signal.get('factors', {}),
                'robot_id': self.robot_id,
                'timestamp': signal.get('timestamp'),
                'executed': False,
                'metadata': {
                    'entry_zone': signal.get('entry_zone'),
                    'stop_loss': signal.get('stop_loss'),
                    'take_profit': signal.get('take_profit')
                }
            }
            await self.postgres.insert_signal(signal_data)
            
            log_data = {
                'timestamp': datetime.now(),
                'level': 'INFO',
                'robot_id': self.robot_id,
                'message': f"Trade signal generated for {signal['symbol']}",
                'context': {
                    'signal_type': signal.get('signal_type'),
                    'confidence': signal.get('confidence'),
                    'entry_zone': signal.get('entry_zone')
                }
            }
            self.mongodb.insert_system_log(log_data)
            
        except Exception as e:
            self.logger.error(f"Failed to store signal: {e}")
