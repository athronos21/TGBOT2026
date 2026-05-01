"""
Simulated Execution for Backtesting

Simulates trade execution during backtesting, including:
- Order placement
- Position management
- SL/TP handling
- Slippage simulation
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from ..integrations.mt5_connection import MT5Connection


class OrderType(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


@dataclass
class Order:
    """Order data structure"""
    order_id: str
    symbol: str
    order_type: OrderType
    volume: float
    price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    open_time: Optional[datetime] = None
    close_time: Optional[datetime] = None
    profit: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    slippage: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'order_type': self.order_type.value,
            'volume': self.volume,
            'price': self.price,
            'sl': self.sl,
            'tp': self.tp,
            'status': self.status.value,
            'open_time': self.open_time.isoformat() if self.open_time else None,
            'close_time': self.close_time.isoformat() if self.close_time else None,
            'profit': self.profit,
            'commission': self.commission,
            'swap': self.swap,
            'slippage': self.slippage
        }


@dataclass
class Position:
    """Position data structure"""
    position_id: str
    symbol: str
    order_type: OrderType
    volume: float
    open_price: float
    current_price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    open_time: datetime = field(default_factory=datetime.now)
    profit: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'order_type': self.order_type.value,
            'volume': self.volume,
            'open_price': self.open_price,
            'current_price': self.current_price,
            'sl': self.sl,
            'tp': self.tp,
            'open_time': self.open_time.isoformat(),
            'profit': self.profit,
            'commission': self.commission,
            'swap': self.swap
        }


class SimulatedExecution:
    """
    Simulates trade execution during backtesting.
    
    Provides realistic simulation of:
    - Order placement
    - Position management
    - SL/TP execution
    - Slippage
    - Commission and swap
    """
    
    def __init__(self, config: Dict[str, Any], initial_balance: float = 1000.0):
        """
        Initialize the simulated execution.
        
        Args:
            config: Execution configuration
            initial_balance: Initial account balance
        """
        self.config = config
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.logger = logging.getLogger(__name__)
        
        # Order and position tracking
        self.orders: Dict[str, Order] = {}
        self.positions: Dict[str, Position] = {}
        self.closed_trades: List[Dict[str, Any]] = []
        
        # Configuration
        self.spread = config.get('spread', 2.0)  # pips
        self.commission_rate = config.get('commission_rate', 0.0)  # per lot
        self.swap_rate = config.get('swap_rate', 0.0)  # per lot per night
        self.slippage_max = config.get('slippage_max', 5.0)  # pips
        
        # MT5 connection (for simulation)
        self.mt5 = None
        
    async def initialize(self) -> None:
        """Initialize simulated execution"""
        self.logger.info("Initializing simulated execution...")
        
        # Initialize MT5 connection if available
        try:
            self.mt5 = MT5Connection(self.config.get('mt5', {}))
            await self.mt5.connect()
        except Exception as e:
            self.logger.warning(f"MT5 connection not available: {e}")
            
        self.logger.info(f"Simulated execution initialized with balance: ${self.current_balance:.2f}")
        
    async def cleanup(self) -> None:
        """Cleanup simulated execution"""
        if self.mt5:
            await self.mt5.disconnect()
        self.logger.info("Simulated execution cleaned up")
        
    async def place_order(self, symbol: str, order_type: OrderType, volume: float,
                         price: float, sl: Optional[float] = None,
                         tp: Optional[float] = None) -> Optional[Order]:
        """
        Place a new order.
        
        Args:
            symbol: Trading symbol
            order_type: Order type (BUY/SELL)
            volume: Order volume (lots)
            price: Order price
            sl: Stop loss price (optional)
            tp: Take profit price (optional)
            
        Returns:
            Order object or None if failed
        """
        # Check margin
        margin_required = self._calculate_margin(symbol, order_type, volume, price)
        if margin_required > self.current_balance:
            self.logger.warning(f"Insufficient margin for order: {margin_required:.2f} > {self.current_balance:.2f}")
            return None
            
        # Create order
        order_id = f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        order = Order(
            order_id=order_id,
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            price=price,
            sl=sl,
            tp=tp,
            status=OrderStatus.PENDING
        )
        
        # Deduct margin
        self.current_balance -= margin_required
        order.margin = margin_required
        
        # Open order immediately (simplified simulation)
        order.status = OrderStatus.OPEN
        order.open_time = datetime.now()
        
        # Add to orders
        self.orders[order_id] = order
        
        # Create position
        position_id = f"POS_{order_id}"
        position = Position(
            position_id=position_id,
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            open_price=price,
            sl=sl,
            tp=tp,
            open_time=order.open_time
        )
        
        self.positions[position_id] = position
        
        self.logger.info(f"Placed {order_type.value} order: {order_id} ({volume} lots @ {price})")
        
        return order
        
    async def close_position(self, position_id: str, close_price: float) -> Optional[Dict[str, Any]]:
        """
        Close a position.
        
        Args:
            position_id: Position ID
            close_price: Close price
            
        Returns:
            Trade result dictionary or None if failed
        """
        if position_id not in self.positions:
            self.logger.warning(f"Position not found: {position_id}")
            return None
            
        position = self.positions[position_id]
        
        # Calculate profit/loss
        if position.order_type == OrderType.BUY:
            profit = (close_price - position.open_price) * position.volume * 100000
        else:
            profit = (position.open_price - close_price) * position.volume * 100000
            
        # Calculate commission and swap
        commission = position.volume * self.commission_rate
        swap = position.volume * self.swap_rate
        
        # Calculate slippage
        slippage = abs(close_price - position.open_price) * position.volume * 0.01
        
        # Update position
        position.current_price = close_price
        position.profit = profit
        position.commission = commission
        position.swap = swap
        position.close_time = datetime.now()
        
        # Update balance
        self.current_balance += profit - commission - swap
        
        # Remove position
        del self.positions[position_id]
        
        # Update order
        if position_id in self.orders:
            order = self.orders[position_id]
            order.status = OrderStatus.CLOSED
            order.close_time = position.close_time
            order.profit = profit
            order.commission = commission
            order.swap = swap
            order.slippage = slippage
            
        # Record closed trade
        trade_result = {
            'position_id': position_id,
            'symbol': position.symbol,
            'order_type': position.order_type.value,
            'volume': position.volume,
            'open_price': position.open_price,
            'close_price': close_price,
            'profit': profit,
            'commission': commission,
            'swap': swap,
            'slippage': slippage,
            'open_time': position.open_time,
            'close_time': position.close_time
        }
        self.closed_trades.append(trade_result)
        
        self.logger.info(f"Closed position: {position_id} (P&L: ${profit:.2f})")
        
        return trade_result
        
    async def modify_position(self, position_id: str, new_sl: Optional[float] = None,
                             new_tp: Optional[float] = None) -> bool:
        """
        Modify a position's SL/TP.
        
        Args:
            position_id: Position ID
            new_sl: New stop loss price (optional)
            new_tp: New take profit price (optional)
            
        Returns:
            True if successful
        """
        if position_id not in self.positions:
            self.logger.warning(f"Position not found: {position_id}")
            return False
            
        position = self.positions[position_id]
        
        if new_sl is not None:
            position.sl = new_sl
        if new_tp is not None:
            position.tp = new_tp
            
        self.logger.info(f"Modified position: {position_id} (SL: {new_sl}, TP: {new_tp})")
        
        return True
        
    async def update_positions(self, current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Update all open positions with current prices.
        
        Args:
            current_prices: Dictionary of symbol -> current price
            
        Returns:
            List of closed positions (due to SL/TP hit)
        """
        closed_positions = []
        
        for position_id, position in list(self.positions.items()):
            if position.symbol not in current_prices:
                continue
                
            current_price = current_prices[position.symbol]
            position.current_price = current_price
            
            # Check SL
            if position.sl is not None:
                if position.order_type == OrderType.BUY and current_price <= position.sl:
                    result = await self.close_position(position_id, position.sl)
                    if result:
                        closed_positions.append(result)
                elif position.order_type == OrderType.SELL and current_price >= position.sl:
                    result = await self.close_position(position_id, position.sl)
                    if result:
                        closed_positions.append(result)
                        
            # Check TP
            if position.tp is not None:
                if position.order_type == OrderType.BUY and current_price >= position.tp:
                    result = await self.close_position(position_id, position.tp)
                    if result:
                        closed_positions.append(result)
                elif position.order_type == OrderType.SELL and current_price <= position.tp:
                    result = await self.close_position(position_id, position.tp)
                    if result:
                        closed_positions.append(result)
                        
        return closed_positions
        
    def _calculate_margin(self, symbol: str, order_type: OrderType,
                         volume: float, price: float) -> float:
        """
        Calculate margin requirement for an order.
        
        Args:
            symbol: Trading symbol
            order_type: Order type
            volume: Order volume
            price: Order price
            
        Returns:
            Margin requirement
        """
        # Simplified margin calculation
        # In reality, this depends on leverage and symbol specifications
        leverage = self.config.get('leverage', 500)
        margin_per_lot = 100000  # Standard lot
        
        margin = (volume * margin_per_lot * price) / leverage
        return margin
        
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get current account information.
        
        Returns:
            Account information dictionary
        """
        # Calculate equity
        equity = self.current_balance
        for position in self.positions.values():
            if position.order_type == OrderType.BUY:
                equity += (position.current_price - position.open_price) * position.volume * 100000
            else:
                equity += (position.open_price - position.current_price) * position.volume * 100000
                
        # Calculate margin used
        margin_used = sum(
            order.margin for order in self.orders.values()
            if order.status == OrderStatus.OPEN
        )
        
        # Calculate free margin
        free_margin = equity - margin_used
        
        # Calculate margin level
        margin_level = (equity / margin_used * 100) if margin_used > 0 else 0
        
        return {
            'balance': self.current_balance,
            'equity': equity,
            'margin_used': margin_used,
            'free_margin': free_margin,
            'margin_level': margin_level,
            'open_positions': len(self.positions),
            'orders': len(self.orders)
        }
        
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        return [pos.to_dict() for pos in self.positions.values()]
        
    def get_closed_trades(self) -> List[Dict[str, Any]]:
        """Get all closed trades."""
        return self.closed_trades.copy()
