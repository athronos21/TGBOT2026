"""
PostgreSQL Database Manager

Manages PostgreSQL connections and operations for structured data.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager

try:
    import asyncpg
    from asyncpg import Connection, Pool
except ImportError:
    asyncpg = None
    Pool = None
    Connection = None


class PostgreSQLManager:
    """
    Manages PostgreSQL database connections and operations.
    
    Provides async methods for:
    - Connection pool management
    - Trade records
    - Market data
    - Signals
    - Performance metrics
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PostgreSQL manager.
        
        Args:
            config: Database configuration
        """
        if asyncpg is None:
            raise ImportError("asyncpg is not installed. Run: pip install asyncpg")
            
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.pool: Optional[Pool] = None
        self._host = config.get('host', 'localhost')
        self._port = config.get('port', 5432)
        self._database = config.get('database', 'trading_system')
        self._user = config.get('user', 'postgres')
        self._password = config.get('password', '')
        self._pool_size = config.get('pool_size', 10)
        self._max_overflow = config.get('max_overflow', 20)
        
    async def connect(self) -> None:
        """Create connection pool"""
        self.logger.info(f"Connecting to PostgreSQL: {self._host}:{self._port}/{self._database}")
        
        try:
            self.pool = await asyncpg.create_pool(
                host=self._host,
                port=self._port,
                database=self._database,
                user=self._user,
                password=self._password,
                min_size=self._pool_size,
                max_size=self._pool_size + self._max_overflow
            )
            self.logger.info("PostgreSQL connection pool created")
        except Exception as e:
            self.logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
            
    async def disconnect(self) -> None:
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            self.logger.info("PostgreSQL connection pool closed")
            
    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool"""
        if not self.pool:
            raise RuntimeError("Not connected to database")
            
        conn: Connection = await self.pool.acquire()
        try:
            yield conn
        finally:
            await self.pool.release(conn)
            
    async def execute(self, query: str, *args) -> str:
        """
        Execute a query that doesn't return data.
        
        Args:
            query: SQL query
            *args: Query parameters
            
        Returns:
            Status message
        """
        async with self.get_connection() as conn:
            result = await conn.execute(query, *args)
            return result
            
    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """
        Execute a query and return rows.
        
        Args:
            query: SQL query
            *args: Query parameters
            
        Returns:
            List of row dictionaries
        """
        async with self.get_connection() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
            
    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """
        Execute a query and return a single row.
        
        Args:
            query: SQL query
            *args: Query parameters
            
        Returns:
            Row dictionary or None
        """
        async with self.get_connection() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
            
    # Trade operations
    async def create_trade_table(self) -> None:
        """Create trades table if not exists"""
        query = """
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            external_id VARCHAR(64) UNIQUE NOT NULL,
            symbol VARCHAR(16) NOT NULL,
            trade_type VARCHAR(8) NOT NULL CHECK (trade_type IN ('BUY', 'SELL')),
            entry_price DECIMAL(12, 5) NOT NULL,
            current_price DECIMAL(12, 5),
            exit_price DECIMAL(12, 5),
            lot_size DECIMAL(10, 2) NOT NULL,
            profit_loss DECIMAL(12, 2),
            status VARCHAR(16) NOT NULL DEFAULT 'OPEN'
                CHECK (status IN ('OPEN', 'CLOSED', 'PENDING', 'CANCELLED')),
            open_time TIMESTAMP NOT NULL DEFAULT NOW(),
            close_time TIMESTAMP,
            robot_id VARCHAR(64),
            signal_id INTEGER,
            metadata JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """
        await self.execute(query)
        
    async def insert_trade(self, trade_data: Dict[str, Any]) -> int:
        """
        Insert a new trade record.
        
        Args:
            trade_data: Trade information
            
        Returns:
            Trade ID
        """
        query = """
        INSERT INTO trades (
            external_id, symbol, trade_type, entry_price, current_price,
            lot_size, status, open_time, robot_id, signal_id, metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING id
        """
        result = await self.fetchrow(
            query,
            trade_data['external_id'],
            trade_data['symbol'],
            trade_data['trade_type'],
            trade_data['entry_price'],
            trade_data.get('current_price'),
            trade_data['lot_size'],
            trade_data.get('status', 'OPEN'),
            trade_data.get('open_time'),
            trade_data.get('robot_id'),
            trade_data.get('signal_id'),
            trade_data.get('metadata', {})
        )
        return result['id'] if result else None
        
    async def update_trade(self, trade_id: int, trade_data: Dict[str, Any]) -> bool:
        """
        Update an existing trade.
        
        Args:
            trade_id: Trade ID
            trade_data: Fields to update
            
        Returns:
            True if updated
        """
        if not trade_data:
            return False
            
        set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(trade_data.keys()))
        query = f"""
        UPDATE trades SET {set_clause}, updated_at = NOW()
        WHERE id = $1
        """
        result = await self.execute(query, trade_id, *trade_data.values())
        return result == "UPDATE 1"
        
    async def get_open_trades(self, symbol: str = None) -> List[Dict[str, Any]]:
        """
        Get all open trades.
        
        Args:
            symbol: Filter by symbol (optional)
            
        Returns:
            List of open trades
        """
        if symbol:
            query = """
            SELECT * FROM trades WHERE status = 'OPEN' AND symbol = $1
            ORDER BY open_time DESC
            """
            return await self.fetch(query, symbol)
        else:
            query = """
            SELECT * FROM trades WHERE status = 'OPEN'
            ORDER BY open_time DESC
            """
            return await self.fetch(query)
            
    async def get_trade_by_external_id(self, external_id: str) -> Optional[Dict[str, Any]]:
        """
        Get trade by external ID (MT5 position ID).
        
        Args:
            external_id: External position ID
            
        Returns:
            Trade record or None
        """
        query = "SELECT * FROM trades WHERE external_id = $1"
        return await self.fetchrow(query, external_id)
        
    # Signal operations
    async def create_signals_table(self) -> None:
        """Create signals table if not exists"""
        query = """
        CREATE TABLE IF NOT EXISTS signals (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(16) NOT NULL,
            signal_type VARCHAR(16) NOT NULL CHECK (signal_type IN ('BUY', 'SELL', 'NEUTRAL')),
            confidence DECIMAL(5, 4) NOT NULL,
            strength DECIMAL(5, 4),
            factors JSONB,
            robot_id VARCHAR(64),
            timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
            executed BOOLEAN DEFAULT FALSE,
            trade_id INTEGER REFERENCES trades(id),
            metadata JSONB
        )
        """
        await self.execute(query)
        
    async def insert_signal(self, signal_data: Dict[str, Any]) -> int:
        """
        Insert a new signal record.
        
        Args:
            signal_data: Signal information
            
        Returns:
            Signal ID
        """
        query = """
        INSERT INTO signals (
            symbol, signal_type, confidence, strength, factors,
            robot_id, timestamp, executed, trade_id, metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id
        """
        result = await self.fetchrow(
            query,
            signal_data['symbol'],
            signal_data['signal_type'],
            signal_data['confidence'],
            signal_data.get('strength'),
            signal_data.get('factors', {}),
            signal_data.get('robot_id'),
            signal_data.get('timestamp'),
            signal_data.get('executed', False),
            signal_data.get('trade_id'),
            signal_data.get('metadata', {})
        )
        return result['id'] if result else None
        
    # Market data operations
    async def create_market_data_table(self) -> None:
        """Create market data table if not exists"""
        query = """
        CREATE TABLE IF NOT EXISTS market_data (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(16) NOT NULL,
            timeframe VARCHAR(8) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            open DECIMAL(12, 5) NOT NULL,
            high DECIMAL(12, 5) NOT NULL,
            low DECIMAL(12, 5) NOT NULL,
            close DECIMAL(12, 5) NOT NULL,
            volume BIGINT,
            UNIQUE(symbol, timeframe, timestamp)
        )
        """
        await self.execute(query)
        
    async def insert_market_data(self, data: List[Dict[str, Any]]) -> int:
        """
        Insert market data records.
        
        Args:
            data: List of market data records
            
        Returns:
            Number of records inserted
        """
        if not data:
            return 0
            
        async with self.get_connection() as conn:
            async with conn.transaction():
                for record in data:
                    await conn.execute("""
                        INSERT INTO market_data (
                            symbol, timeframe, timestamp, open, high, low, close, volume
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (symbol, timeframe, timestamp) DO NOTHING
                    """, record['symbol'], record['timeframe'], record['timestamp'],
                        record['open'], record['high'], record['low'], record['close'],
                        record.get('volume'))
                        
        return len(data)
        
    async def get_market_data(self, symbol: str, timeframe: str,
                              start: str, end: str) -> List[Dict[str, Any]]:
        """
        Get market data for a symbol and timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., 'M15', 'H1')
            start: Start timestamp
            end: End timestamp
            
        Returns:
            List of market data records
        """
        query = """
        SELECT * FROM market_data
        WHERE symbol = $1 AND timeframe = $2
        AND timestamp >= $3 AND timestamp <= $4
        ORDER BY timestamp
        """
        return await self.fetch(query, symbol, timeframe, start, end)

    async def get_market_data(self, symbol: str, timeframe: str,
                              start: str, end: str) -> List[Dict[str, Any]]:
        """
        Get market data for a symbol and timeframe.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., 'M15', 'H1')
            start: Start timestamp
            end: End timestamp

        Returns:
            List of market data records
        """
        query = """
        SELECT * FROM market_data
        WHERE symbol = $1 AND timeframe = $2
        AND timestamp >= $3 AND timestamp <= $4
        ORDER BY timestamp
        """
        return await self.fetch(query, symbol, timeframe, start, end)

    # Analysis results operations
    async def create_analysis_results_table(self) -> None:
        """Create analysis_results table if not exists"""
        query = """
        CREATE TABLE IF NOT EXISTS analysis_results (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(16) NOT NULL,
            analysis_type VARCHAR(32) NOT NULL,
            result_data JSONB NOT NULL,
            confidence DECIMAL(5, 4),
            timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
            robot_id VARCHAR(64),
            metadata JSONB
        )
        """
        await self.execute(query)

    async def insert_analysis_result(self, result_data: Dict[str, Any]) -> int:
        """
        Insert an analysis result.

        Args:
            result_data: Analysis result information

        Returns:
            Result ID
        """
        query = """
        INSERT INTO analysis_results (
            symbol, analysis_type, result_data, confidence,
            timestamp, robot_id, metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """
        result = await self.fetchrow(
            query,
            result_data['symbol'],
            result_data['analysis_type'],
            result_data['result_data'],
            result_data.get('confidence'),
            result_data.get('timestamp'),
            result_data.get('robot_id'),
            result_data.get('metadata', {})
        )
        return result['id'] if result else None

    # Performance metrics operations
    async def create_performance_metrics_table(self) -> None:
        """Create performance_metrics table if not exists"""
        query = """
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id SERIAL PRIMARY KEY,
            robot_id VARCHAR(64) NOT NULL,
            metric_name VARCHAR(64) NOT NULL,
            metric_value DECIMAL(15, 6) NOT NULL,
            metric_type VARCHAR(16) NOT NULL
                CHECK (metric_type IN ('ratio', 'count', 'percentage', 'currency')),
            timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
            period_start TIMESTAMP,
            period_end TIMESTAMP,
            metadata JSONB
        )
        """
        await self.execute(query)

    async def insert_performance_metric(self, metric_data: Dict[str, Any]) -> int:
        """
        Insert a performance metric.

        Args:
            metric_data: Performance metric information

        Returns:
            Metric ID
        """
        query = """
        INSERT INTO performance_metrics (
            robot_id, metric_name, metric_value, metric_type,
            timestamp, period_start, period_end, metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """
        result = await self.fetchrow(
            query,
            metric_data['robot_id'],
            metric_data['metric_name'],
            metric_data['metric_value'],
            metric_data['metric_type'],
            metric_data.get('timestamp'),
            metric_data.get('period_start'),
            metric_data.get('period_end'),
            metric_data.get('metadata', {})
        )
        return result['id'] if result else None

    # Robot health operations
    async def create_robot_health_table(self) -> None:
        """Create robot_health table if not exists"""
        query = """
        CREATE TABLE IF NOT EXISTS robot_health (
            id SERIAL PRIMARY KEY,
            robot_id VARCHAR(64) NOT NULL,
            status VARCHAR(16) NOT NULL
                CHECK (status IN ('healthy', 'degraded', 'unhealthy', 'unknown')),
            cpu_usage DECIMAL(5, 2),
            memory_usage DECIMAL(5, 2),
            last_heartbeat TIMESTAMP NOT NULL DEFAULT NOW(),
            error_count INTEGER DEFAULT 0,
            uptime_seconds BIGINT,
            metadata JSONB,
            UNIQUE(robot_id, timestamp)
        )
        """
        await self.execute(query)

    async def insert_robot_health(self, health_data: Dict[str, Any]) -> int:
        """
        Insert robot health data.

        Args:
            health_data: Health information

        Returns:
            Health record ID
        """
        query = """
        INSERT INTO robot_health (
            robot_id, status, cpu_usage, memory_usage,
            last_heartbeat, error_count, uptime_seconds, metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """
        result = await self.fetchrow(
            query,
            health_data['robot_id'],
            health_data['status'],
            health_data.get('cpu_usage'),
            health_data.get('memory_usage'),
            health_data.get('last_heartbeat'),
            health_data.get('error_count', 0),
            health_data.get('uptime_seconds'),
            health_data.get('metadata', {})
        )
        return result['id'] if result else None

    # Index creation methods
    async def create_market_data_indexes(self) -> None:
        """Create indexes for market_data table"""
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time
            ON market_data (symbol, timeframe, timestamp DESC)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_data_timestamp
            ON market_data (timestamp DESC)
        """)

    async def create_trades_indexes(self) -> None:
        """Create indexes for trades table"""
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_account
            ON trades (robot_id)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_symbol
            ON trades (symbol)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_status
            ON trades (status)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_entry_time
            ON trades (open_time DESC)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_signal
            ON trades (signal_id)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_symbol_status
            ON trades (symbol, status)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_symbol_time
            ON trades (symbol, open_time DESC)
        """)

    async def create_signals_indexes(self) -> None:
        """Create indexes for signals table"""
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_signals_symbol
            ON signals (symbol)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_signals_executed
            ON signals (executed)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_signals_created
            ON signals (timestamp DESC)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_signals_robot
            ON signals (robot_id)
        """)

    async def create_analysis_results_indexes(self) -> None:
        """Create indexes for analysis_results table"""
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_symbol_time
            ON analysis_results (symbol, timestamp DESC)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_type
            ON analysis_results (analysis_type)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_robot
            ON analysis_results (robot_id)
        """)

    async def create_performance_metrics_indexes(self) -> None:
        """Create indexes for performance_metrics table"""
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_robot
            ON performance_metrics (robot_id)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_name
            ON performance_metrics (metric_name)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
            ON performance_metrics (timestamp DESC)
        """)

    async def create_robot_health_indexes(self) -> None:
        """Create indexes for robot_health table"""
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_robot_health_id
            ON robot_health (robot_id)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_robot_health_status
            ON robot_health (status)
        """)
        await self.execute("""
            CREATE INDEX IF NOT EXISTS idx_robot_health_heartbeat
            ON robot_health (last_heartbeat DESC)
        """)

    async def create_all_indexes(self) -> None:
        """Create all database indexes"""
        await self.create_market_data_indexes()
        await self.create_trades_indexes()
        await self.create_signals_indexes()
        await self.create_analysis_results_indexes()
        await self.create_performance_metrics_indexes()
        await self.create_robot_health_indexes()
        self.logger.info("All database indexes created")
