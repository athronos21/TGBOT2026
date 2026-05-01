"""
MetaTrader 5 Connection Manager

This module provides a robust connection manager for MetaTrader 5 with:
- Connection/disconnection handling
- Auto-reconnect logic with exponential backoff
- Connection health checks
- Error handling and logging
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import MetaTrader5 as mt5


@dataclass
class MT5ConnectionInfo:
    """Information about MT5 connection status"""
    connected: bool
    server: str
    account: Optional[int] = None
    connected_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    reconnect_count: int = 0
    last_error: Optional[str] = None


class MT5Connection:
    """
    Manages MetaTrader 5 connection with auto-reconnect and health checks.
    
    Features:
    - Automatic reconnection on connection loss
    - Exponential backoff for reconnection attempts
    - Connection health monitoring
    - Graceful shutdown handling
    """
    
    # Configuration defaults
    DEFAULT_RECONNECT_DELAY = 1.0  # Initial delay in seconds
    DEFAULT_MAX_RECONNECT_DELAY = 60.0  # Maximum delay in seconds
    DEFAULT_RECONNECT_BACKOFF = 2.0  # Backoff multiplier
    DEFAULT_HEALTH_CHECK_INTERVAL = 30.0  # Health check interval in seconds
    DEFAULT_SHUTDOWN_TIMEOUT = 5.0  # Shutdown timeout in seconds
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the MT5 connection manager.
        
        Args:
            config: Configuration dictionary with MT5 settings:
                - server: MT5 server name
                - account: Account number
                - password: Account password
                - path: (optional) MT5 terminal path
                - reconnect_delay: (optional) Initial reconnect delay
                - max_reconnect_delay: (optional) Maximum reconnect delay
                - reconnect_backoff: (optional) Backoff multiplier
                - health_check_interval: (optional) Health check interval
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Connection configuration
        self.server = config.get('server', '')
        self.account = config.get('account_number')
        self.password = config.get('password', '')
        self.path = config.get('path')  # MT5 terminal path (optional)
        
        # Reconnection configuration
        self.reconnect_delay = config.get('reconnect_delay', self.DEFAULT_RECONNECT_DELAY)
        self.max_reconnect_delay = config.get('max_reconnect_delay', self.DEFAULT_MAX_RECONNECT_DELAY)
        self.reconnect_backoff = config.get('reconnect_backoff', self.DEFAULT_RECONNECT_BACKOFF)
        
        # Health check configuration
        self.health_check_interval = config.get('health_check_interval', self.DEFAULT_HEALTH_CHECK_INTERVAL)
        
        # Connection state
        self._connection_info: Optional[MT5ConnectionInfo] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._connected_event = asyncio.Event()
        self._reconnect_count = 0
        self._current_reconnect_delay = self.reconnect_delay
        self._running = False
        
        # Statistics
        self._stats = {
            'total_connections': 0,
            'total_disconnections': 0,
            'total_reconnects': 0,
            'total_errors': 0,
            'last_error': None,
            'uptime_seconds': 0,
            'last_connect_time': None,
            'last_disconnect_time': None
        }
        
    async def connect(self) -> bool:
        """
        Establish connection to MetaTrader 5.
        
        Returns:
            True if connection successful, False otherwise
        """
        if self._connection_info and self._connection_info.connected:
            self.logger.warning("Already connected to MT5")
            return True
            
        try:
            self.logger.info(f"Connecting to MT5 server: {self.server}")
            
            # Initialize MT5
            if not mt5.initialize(path=self.path):
                error_msg = f"Failed to initialize MT5: {mt5.last_error()}"
                self.logger.error(error_msg)
                self._stats['last_error'] = error_msg
                self._stats['total_errors'] += 1
                return False
                
            # Attempt to login
            if self.account and self.password:
                authorized = mt5.login(
                    login=int(self.account),
                    password=self.password,
                    server=self.server
                )
                if not authorized:
                    error_msg = f"Failed to login to MT5: {mt5.last_error()}"
                    self.logger.error(error_msg)
                    self._stats['last_error'] = error_msg
                    self._stats['total_errors'] += 1
                    mt5.shutdown()
                    return False
                    
            self._connection_info = MT5ConnectionInfo(
                connected=True,
                server=self.server,
                account=self.account,
                connected_at=datetime.now(),
                last_heartbeat=datetime.now(),
                reconnect_count=self._reconnect_count
            )
            
            self._stats['total_connections'] += 1
            self._stats['last_connect_time'] = datetime.now()
            self._stats['uptime_seconds'] = 0
            self._stats['last_error'] = None
            
            self._connected_event.set()
            self.logger.info(f"Successfully connected to MT5 (Account: {self.account})")
            
            return True
            
        except Exception as e:
            error_msg = f"Unexpected error during MT5 connection: {str(e)}"
            self.logger.error(error_msg)
            self._stats['last_error'] = error_msg
            self._stats['total_errors'] += 1
            return False
            
    async def disconnect(self) -> bool:
        """
        Disconnect from MetaTrader 5 gracefully.
        
        Returns:
            True if disconnection successful, False otherwise
        """
        if not self._connection_info or not self._connection_info.connected:
            self.logger.warning("Not connected to MT5")
            return True
            
        try:
            self.logger.info("Disconnecting from MT5...")
            
            # Stop health check and reconnect tasks
            await self._stop_background_tasks()
            
            # Shutdown MT5
            mt5.shutdown()
            
            # Update connection info
            self._connection_info.connected = False
            self._connection_info.last_error = "Disconnected by user"
            self._connection_info.last_heartbeat = datetime.now()
            
            self._stats['total_disconnections'] += 1
            self._stats['last_disconnect_time'] = datetime.now()
            self._stats['uptime_seconds'] = 0
            
            self._connected_event.clear()
            self.logger.info("Disconnected from MT5")
            
            return True
            
        except Exception as e:
            error_msg = f"Error during MT5 disconnection: {str(e)}"
            self.logger.error(error_msg)
            self._stats['last_error'] = error_msg
            self._stats['total_errors'] += 1
            return False
            
    async def start(self) -> bool:
        """
        Start the connection manager with auto-reconnect and health checks.
        
        Returns:
            True if started successfully
        """
        if self._running:
            self.logger.warning("Connection manager already running")
            return True
            
        self._running = True
        self._shutdown_event.clear()
        
        # Initial connection
        if not await self.connect():
            self.logger.warning("Initial connection failed, starting reconnection loop")
            
        # Start background tasks
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        self.logger.info("MT5 connection manager started")
        return True
        
    async def stop(self) -> bool:
        """
        Stop the connection manager gracefully.
        
        Returns:
            True if stopped successfully
        """
        if not self._running:
            self.logger.warning("Connection manager not running")
            return True
            
        self._running = False
        self._shutdown_event.set()
        
        # Wait for background tasks to finish
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
                
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
                
        # Disconnect from MT5
        await self.disconnect()
        
        self.logger.info("MT5 connection manager stopped")
        return True
        
    async def _stop_background_tasks(self) -> None:
        """Stop background tasks without disconnecting"""
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None
            
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            
    async def _reconnect_loop(self) -> None:
        """Background task for automatic reconnection"""
        while self._running and not self._shutdown_event.is_set():
            try:
                # Wait until not connected
                if self._connection_info and self._connection_info.connected:
                    await asyncio.sleep(1)
                    continue
                    
                # Wait for reconnection delay
                await asyncio.sleep(self._current_reconnect_delay)
                
                # Attempt reconnection
                if await self.connect():
                    self._reconnect_count += 1
                    self._stats['total_reconnects'] += 1
                    self._current_reconnect_delay = self.reconnect_delay  # Reset delay
                    self.logger.info(f"Reconnected to MT5 (attempt #{self._reconnect_count})")
                else:
                    # Exponential backoff
                    self._current_reconnect_delay = min(
                        self._current_reconnect_delay * self.reconnect_backoff,
                        self.max_reconnect_delay
                    )
                    self.logger.warning(
                        f"Reconnection failed, retrying in {self._current_reconnect_delay:.1f}s"
                    )
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in reconnect loop: {e}")
                await asyncio.sleep(self._current_reconnect_delay)
                
    async def _health_check_loop(self) -> None:
        """Background task for connection health monitoring"""
        while self._running and not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.health_check_interval)
                
                if not self._connection_info or not self._connection_info.connected:
                    continue
                    
                # Check connection health
                if not await self.check_health():
                    self.logger.warning("Health check failed, disconnecting to trigger reconnection")
                    await self.disconnect()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
                
    async def check_health(self) -> bool:
        """
        Check if the MT5 connection is healthy.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        if not self._connection_info or not self._connection_info.connected:
            return False
            
        try:
            # Update heartbeat
            self._connection_info.last_heartbeat = datetime.now()
            
            # Check if MT5 is still responsive
            if not mt5.terminal_info():
                self.logger.warning("MT5 terminal info check failed")
                return False
                
            # Check if we can get account info
            account_info = mt5.account_info()
            if account_info is None:
                self.logger.warning("Failed to get account info")
                return False
                
            # Update stats
            self._stats['uptime_seconds'] += self.health_check_interval
            
            return True
            
        except Exception as e:
            error_msg = f"Health check failed: {str(e)}"
            self.logger.error(error_msg)
            self._stats['last_error'] = error_msg
            self._stats['total_errors'] += 1
            return False
            
    async def get_tick(self, symbol: str) -> Optional[Any]:
        """
        Get the latest tick data for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'XAUUSD')
            
        Returns:
            Tick data object or None if failed
        """
        if not self.is_connected():
            self.logger.error(f"Cannot get tick: Not connected to MT5")
            return None
            
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                self.logger.error(f"Failed to get tick for {symbol}")
                return None
            return tick
        except Exception as e:
            self.logger.error(f"Error getting tick for {symbol}: {e}")
            return None
            
    async def get_candles(self, symbol: str, timeframe: int, count: int = 100) -> Optional[Any]:
        """
        Get historical candle data for a symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., mt5.TIMEFRAME_M1, mt5.TIMEFRAME_H1)
            count: Number of candles to retrieve
            
        Returns:
            Array of candle data or None if failed
        """
        if not self.is_connected():
            self.logger.error(f"Cannot get candles: Not connected to MT5")
            return None
            
        try:
            candles = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if candles is None:
                self.logger.error(f"Failed to get candles for {symbol}")
                return None
            return candles
        except Exception as e:
            self.logger.error(f"Error getting candles for {symbol}: {e}")
            return None
            
    async def get_account_info(self) -> Optional[Any]:
        """
        Get account information.
        
        Returns:
            Account info object or None if failed
        """
        if not self.is_connected():
            self.logger.error("Cannot get account info: Not connected to MT5")
            return None
            
        try:
            account_info = mt5.account_info()
            if account_info is None:
                self.logger.error("Failed to get account info")
                return None
            return account_info
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return None
            
    async def get_open_positions(self) -> Optional[List[Any]]:
        """
        Get all open positions.
        
        Returns:
            List of position objects or None if failed
        """
        if not self.is_connected():
            self.logger.error("Cannot get positions: Not connected to MT5")
            return None
            
        try:
            positions = mt5.positions_get()
            if positions is None:
                self.logger.error("Failed to get positions")
                return None
            return list(positions)
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return None
            
    async def place_order(self, order: Dict[str, Any]) -> Optional[Any]:
        """
        Place a trade order on MT5.
        
        Args:
            order: Order dictionary with keys:
                - symbol: Trading symbol
                - type: Order type (mt5.ORDER_TYPE_BUY or mt5.ORDER_TYPE_SELL)
                - volume: Lot size
                - price: Entry price
                - sl: Stop loss price (optional)
                - tp: Take profit price (optional)
                - comment: Order comment (optional)
                
        Returns:
            Trade result object or None if failed
        """
        if not self.is_connected():
            self.logger.error("Cannot place order: Not connected to MT5")
            return None
            
        try:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": order['symbol'],
                "volume": order['volume'],
                "type": order['type'],
                "price": order['price'],
                "deviation": 10,
                "magic": 10032025,
                "comment": order.get('comment', 'AI Robot'),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Add optional parameters
            if 'sl' in order:
                request['sl'] = order['sl']
            if 'tp' in order:
                request['tp'] = order['tp']
                
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                self.logger.error(f"Order failed: {result.retcode} - {result.comment}")
                return None
                
            return result
            
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return None
            
    async def close_position(self, position: Any, price: Optional[float] = None) -> Optional[Any]:
        """
        Close a position.
        
        Args:
            position: Position object to close
            price: Close price (optional, uses current market price if not provided)
            
        Returns:
            Trade result object or None if failed
        """
        if not self.is_connected():
            self.logger.error("Cannot close position: Not connected to MT5")
            return None
            
        try:
            # Get current price if not provided
            if price is None:
                tick = mt5.symbol_info_tick(position.symbol)
                if tick is None:
                    self.logger.error(f"Failed to get tick for {position.symbol}")
                    return None
                    
                # Use bid for buy positions, ask for sell positions
                if position.type == mt5.POSITION_TYPE_BUY:
                    price = tick.bid
                else:
                    price = tick.ask
                    
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "position": position.ticket,
                "price": price,
                "deviation": 10,
                "magic": 10032025,
                "comment": "AI Robot Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                self.logger.error(f"Close order failed: {result.retcode} - {result.comment}")
                return None
                
            return result
            
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return None
            
    def is_connected(self) -> bool:
        """
        Check if connected to MT5.
        
        Returns:
            True if connected, False otherwise
        """
        if self._connection_info is None:
            return False
        return self._connection_info.connected
        
    def get_connection_info(self) -> Optional[MT5ConnectionInfo]:
        """
        Get current connection information.
        
        Returns:
            Connection info object or None if not initialized
        """
        return self._connection_info
        
    def get_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics.
        
        Returns:
            Dictionary with connection statistics
        """
        return self._stats.copy()
        
    async def wait_for_connection(self, timeout: Optional[float] = None) -> bool:
        """
        Wait until connected to MT5.
        
        Args:
            timeout: Maximum time to wait in seconds (None for infinite)
            
        Returns:
            True if connected, False if timeout
        """
        try:
            await asyncio.wait_for(
                self._connected_event.wait(),
                timeout=timeout
            )
            return True
        except asyncio.TimeoutError:
            return False
