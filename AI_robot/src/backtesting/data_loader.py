"""
Historical Data Loader for Backtesting

Loads historical market data from PostgreSQL for backtesting.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..database.postgresql_manager import PostgreSQLManager


@dataclass
class CandleData:
    """Candle data structure for backtesting"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }


class HistoricalDataLoader:
    """
    Loads historical market data for backtesting.
    
    Fetches data from PostgreSQL and formats it for backtesting.
    """
    
    def __init__(self, postgres_manager: PostgreSQLManager):
        """
        Initialize the data loader.
        
        Args:
            postgres_manager: PostgreSQL database manager
        """
        self.postgres = postgres_manager
        self.logger = logging.getLogger(__name__)
        
    async def load_candles(self, symbol: str, timeframe: str,
                          start_date: datetime, end_date: datetime) -> List[CandleData]:
        """
        Load candle data for a symbol and timeframe.
        
        Args:
            symbol: Trading symbol (e.g., 'XAUUSD')
            timeframe: Timeframe (e.g., 'M15', 'H1')
            start_date: Start date for data
            end_date: End date for data
            
        Returns:
            List of CandleData objects
        """
        self.logger.info(f"Loading candles for {symbol} {timeframe} from {start_date} to {end_date}")
        
        try:
            # Convert timeframe to MT5 constant for database query
            mt5_timeframe = self._timeframe_to_mt5(timeframe)
            
            # Query database
            query = """
            SELECT timestamp, open, high, low, close, volume
            FROM market_data
            WHERE symbol = $1 AND timeframe = $2
            AND timestamp >= $3 AND timestamp <= $4
            ORDER BY timestamp
            """
            
            rows = await self.postgres.fetch(
                query, symbol, mt5_timeframe, start_date, end_date
            )
            
            # Convert to CandleData objects
            candles = []
            for row in rows:
                candle = CandleData(
                    timestamp=row['timestamp'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume']) if row['volume'] else 0
                )
                candles.append(candle)
                
            self.logger.info(f"Loaded {len(candles)} candles for {symbol} {timeframe}")
            return candles
            
        except Exception as e:
            self.logger.error(f"Failed to load candles: {e}")
            raise
            
    async def load_ticks(self, symbol: str,
                        start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Load tick data for a symbol.
        
        Args:
            symbol: Trading symbol
            start_date: Start date for data
            end_date: End date for data
            
        Returns:
            List of tick data dictionaries
        """
        self.logger.info(f"Loading ticks for {symbol} from {start_date} to {end_date}")
        
        # Note: Tick data loading would require a separate table
        # For now, return empty list as tick data is not stored in PostgreSQL
        return []
        
    def _timeframe_to_mt5(self, timeframe: str) -> Optional[int]:
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
        
    async def get_available_data_range(self, symbol: str, timeframe: str) -> Dict[str, datetime]:
        """
        Get the available data range for a symbol and timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            Dictionary with 'start' and 'end' timestamps
        """
        try:
            mt5_timeframe = self._timeframe_to_mt5(timeframe)
            
            # Get earliest timestamp
            start_query = """
            SELECT MIN(timestamp) as start
            FROM market_data
            WHERE symbol = $1 AND timeframe = $2
            """
            start_row = await self.postgres.fetchrow(start_query, symbol, mt5_timeframe)
            
            # Get latest timestamp
            end_query = """
            SELECT MAX(timestamp) as end
            FROM market_data
            WHERE symbol = $1 AND timeframe = $2
            """
            end_row = await self.postgres.fetchrow(end_query, symbol, mt5_timeframe)
            
            return {
                'start': start_row['start'] if start_row['start'] else None,
                'end': end_row['end'] if end_row['end'] else None
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get data range: {e}")
            return {'start': None, 'end': None}
