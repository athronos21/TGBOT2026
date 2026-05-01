# Multi-Robot Trading System - Design Document

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MASTER CONTROLLER                            │
│                  (Orchestration & Coordination)                  │
└────────────┬────────────────────────────────────┬────────────────┘
             │                                    │
             ▼                                    ▼
┌────────────────────────┐          ┌────────────────────────────┐
│   REDIS MESSAGE BUS    │◄────────►│   CONFIGURATION MANAGER    │
│  (Event Communication) │          │   (Dynamic Config)         │
└────────────┬───────────┘          └────────────────────────────┘
             │
    ┌────────┼────────┬────────┬────────┬────────┐
    ▼        ▼        ▼        ▼        ▼        ▼
┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
│ DATA   ││ANALYSIS││DECISION││  RISK  ││EXECUTE ││MONITOR │
│ SWARM  ││ SWARM  ││ SWARM  ││ SWARM  ││ SWARM  ││ SWARM  │
│(6 bots)││(7 bots)││(5 bots)││(4 bots)││(4 bots)││(3 bots)│
└───┬────┘└───┬────┘└───┬────┘└───┬────┘└───┬────┘└───┬────┘
    │         │         │         │         │         │
    └─────────┴─────────┴─────────┴─────────┴─────────┘
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
    ┌───────────────┐       ┌──────────────┐
    │  POSTGRESQL   │       │   MONGODB    │
    │ (Structured)  │       │   (Logs)     │
    └───────────────┘       └──────────────┘
            │                       │
            └───────────┬───────────┘
                        ▼
            ┌───────────────────────┐
            │   METATRADER 5 API    │
            │   (Trade Execution)   │
            └───────────────────────┘
```

### 1.2 Layered Architecture

**Layer 1: Presentation Layer**
- Web Dashboard (Flask/FastAPI)
- Telegram Bot Interface
- PDF Report Generator

**Layer 2: Application Layer**
- Master Controller
- Robot Swarms (44 robots)
- Configuration Manager

**Layer 3: Communication Layer**
- Redis Message Bus
- Event Router
- Message Queue Manager

**Layer 4: Data Layer**
- PostgreSQL (trades, signals, market data)
- MongoDB (logs, events, unstructured data)
- Redis Cache (real-time data)

**Layer 5: Integration Layer**
- MetaTrader 5 API
- Telegram API
- News/Sentiment APIs



## 2. Core Components Design

### 2.1 Master Controller

**Responsibilities:**
- Orchestrate robot lifecycle (start, stop, restart)
- Coordinate workflow between swarms
- Monitor system health
- Handle emergency situations (kill switch)
- Manage configuration updates

**Class Design:**
```python
class MasterController:
    def __init__(self, config: Config, message_bus: MessageBus):
        self.config = config
        self.message_bus = message_bus
        self.robots: Dict[str, Robot] = {}
        self.state: SystemState = SystemState.STOPPED
        
    async def start(self):
        """Start all enabled robots"""
        
    async def stop(self):
        """Stop all robots gracefully"""
        
    async def restart_robot(self, robot_id: str):
        """Restart specific robot"""
        
    async def handle_kill_switch(self):
        """Emergency stop all trading"""
        
    async def process_events(self):
        """Main event processing loop"""
```

### 2.2 Robot Base Class

**Standard Interface:**
```python
from abc import ABC, abstractmethod
from typing import Any, Dict

class Robot(ABC):
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        self.robot_id = robot_id
        self.config = config
        self.message_bus = message_bus
        self.state = RobotState.IDLE
        self.logger = logging.getLogger(robot_id)
        
    @abstractmethod
    async def initialize(self):
        """Initialize robot resources"""
        pass
        
    @abstractmethod
    async def process(self, data: Any) -> Any:
        """Main processing logic"""
        pass
        
    @abstractmethod
    async def cleanup(self):
        """Cleanup resources"""
        pass
        
    async def receive_message(self, message: Message):
        """Receive message from bus"""
        
    async def send_message(self, event: str, data: Dict):
        """Send message to bus"""
        
    async def handle_error(self, error: Exception):
        """Handle errors gracefully"""
```

### 2.3 Message Bus Design

**Message Format:**
```python
@dataclass
class Message:
    message_id: str
    source_bot: str
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime
    priority: Priority  # LOW, NORMAL, HIGH, CRITICAL
    ttl: int  # Time to live in seconds
```

**Message Bus Implementation:**
```python
class MessageBus:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.subscribers: Dict[str, List[Callable]] = {}
        
    async def publish(self, message: Message):
        """Publish message to channel"""
        channel = f"channel:{message.event_type}"
        await self.redis.publish(channel, message.to_json())
        
    async def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to event type"""
        
    async def unsubscribe(self, event_type: str, callback: Callable):
        """Unsubscribe from event type"""
```



## 3. Database Schema Design

### 3.1 PostgreSQL Schema

**Table: market_data**
```sql
CREATE TABLE market_data (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open DECIMAL(18, 5) NOT NULL,
    high DECIMAL(18, 5) NOT NULL,
    low DECIMAL(18, 5) NOT NULL,
    close DECIMAL(18, 5) NOT NULL,
    volume BIGINT NOT NULL,
    spread DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timeframe, timestamp)
);

CREATE INDEX idx_market_data_symbol_time ON market_data(symbol, timeframe, timestamp DESC);
```

**Table: trades**
```sql
CREATE TABLE trades (
    id BIGSERIAL PRIMARY KEY,
    trade_id VARCHAR(50) UNIQUE NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,  -- BUY, SELL
    entry_price DECIMAL(18, 5) NOT NULL,
    exit_price DECIMAL(18, 5),
    lot_size DECIMAL(10, 2) NOT NULL,
    stop_loss DECIMAL(18, 5),
    take_profit DECIMAL(18, 5),
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    profit_loss DECIMAL(18, 2),
    profit_loss_pips DECIMAL(10, 2),
    commission DECIMAL(10, 2),
    swap DECIMAL(10, 2),
    slippage DECIMAL(10, 2),
    strategy VARCHAR(50),
    confidence_score DECIMAL(5, 2),
    status VARCHAR(20),  -- OPEN, CLOSED, CANCELLED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trades_account ON trades(account_id);
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_entry_time ON trades(entry_time DESC);
```

**Table: signals**
```sql
CREATE TABLE signals (
    id BIGSERIAL PRIMARY KEY,
    signal_id VARCHAR(50) UNIQUE NOT NULL,
    bot_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    signal_type VARCHAR(20) NOT NULL,  -- BUY, SELL, NEUTRAL
    confidence DECIMAL(5, 2) NOT NULL,
    entry_zone_low DECIMAL(18, 5),
    entry_zone_high DECIMAL(18, 5),
    stop_loss DECIMAL(18, 5),
    take_profit DECIMAL(18, 5),
    timeframe VARCHAR(10),
    analysis_data JSONB,
    executed BOOLEAN DEFAULT FALSE,
    trade_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_signals_symbol ON signals(symbol);
CREATE INDEX idx_signals_executed ON signals(executed);
CREATE INDEX idx_signals_created ON signals(created_at DESC);
```

**Table: analysis_results**
```sql
CREATE TABLE analysis_results (
    id BIGSERIAL PRIMARY KEY,
    bot_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    analysis_type VARCHAR(50) NOT NULL,
    result JSONB NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analysis_bot_time ON analysis_results(bot_name, timestamp DESC);
CREATE INDEX idx_analysis_symbol ON analysis_results(symbol, timeframe);
```

**Table: performance_metrics**
```sql
CREATE TABLE performance_metrics (
    id BIGSERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    metric_date DATE NOT NULL,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 2),
    profit_factor DECIMAL(10, 2),
    total_profit DECIMAL(18, 2),
    total_loss DECIMAL(18, 2),
    net_profit DECIMAL(18, 2),
    max_drawdown DECIMAL(10, 2),
    sharpe_ratio DECIMAL(10, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, metric_date)
);

CREATE INDEX idx_metrics_account_date ON performance_metrics(account_id, metric_date DESC);
```

**Table: robot_health**
```sql
CREATE TABLE robot_health (
    id BIGSERIAL PRIMARY KEY,
    robot_id VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- RUNNING, STOPPED, ERROR
    last_heartbeat TIMESTAMP NOT NULL,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    cpu_usage DECIMAL(5, 2),
    memory_usage DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_robot_health_id ON robot_health(robot_id);
CREATE INDEX idx_robot_health_status ON robot_health(status);
```



### 3.2 MongoDB Collections

**Collection: system_logs**
```javascript
{
    _id: ObjectId,
    timestamp: ISODate,
    level: "INFO|WARNING|ERROR|CRITICAL",
    robot_id: String,
    message: String,
    context: {
        // Additional context data
    },
    stack_trace: String  // For errors
}
```

**Collection: events**
```javascript
{
    _id: ObjectId,
    event_id: String,
    event_type: String,
    source_bot: String,
    data: Object,
    timestamp: ISODate,
    processed: Boolean,
    processing_time_ms: Number
}
```

**Collection: configurations**
```javascript
{
    _id: ObjectId,
    config_version: String,
    config_data: Object,
    applied_at: ISODate,
    applied_by: String,
    previous_version: String
}
```

## 4. Robot Swarm Designs

### 4.1 Data Collection Swarm

**Price Bot Design:**
```python
class PriceBot(Robot):
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.mt5 = MT5Connection(config['mt5'])
        self.symbols = config['symbols']
        self.update_interval = config.get('update_interval', 1)  # seconds
        
    async def process(self, data: Any) -> Any:
        """Fetch and publish price data"""
        for symbol in self.symbols:
            tick = await self.mt5.get_tick(symbol)
            price_data = {
                'symbol': symbol,
                'bid': tick.bid,
                'ask': tick.ask,
                'spread': tick.ask - tick.bid,
                'volume': tick.volume,
                'timestamp': tick.time
            }
            await self.send_message('price_update', price_data)
```

**Structure Bot Design:**
```python
class StructureBot(Robot):
    async def process(self, data: Any) -> Any:
        """Analyze market structure"""
        candles = data['candles']
        
        # Detect higher highs and higher lows
        hh_hl = self.detect_higher_highs_lows(candles)
        
        # Detect BOS (Break of Structure)
        bos = self.detect_bos(candles)
        
        # Detect CHOCH (Change of Character)
        choch = self.detect_choch(candles)
        
        structure_analysis = {
            'symbol': data['symbol'],
            'timeframe': data['timeframe'],
            'trend': self.determine_trend(hh_hl, bos, choch),
            'bos_detected': bos is not None,
            'choch_detected': choch is not None,
            'structure_data': {
                'hh_hl': hh_hl,
                'bos': bos,
                'choch': choch
            }
        }
        
        await self.send_message('structure_analysis', structure_analysis)
        return structure_analysis
```



### 4.2 Decision Swarm Design

**Signal Aggregator Bot:**
```python
class SignalAggregatorBot(Robot):
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.analysis_cache = {}
        self.required_analyses = [
            'structure_analysis',
            'liquidity_analysis',
            'order_block_analysis'
        ]
        
    async def process(self, data: Any) -> Any:
        """Aggregate signals from analysis bots"""
        analysis_type = data['analysis_type']
        self.analysis_cache[analysis_type] = data
        
        # Check if we have all required analyses
        if self.has_all_analyses():
            signal = await self.generate_signal()
            await self.send_message('trade_signal', signal)
            self.analysis_cache.clear()
            return signal
            
    def has_all_analyses(self) -> bool:
        return all(a in self.analysis_cache for a in self.required_analyses)
        
    async def generate_signal(self) -> Dict:
        """Generate trade signal from aggregated analyses"""
        structure = self.analysis_cache['structure_analysis']
        liquidity = self.analysis_cache['liquidity_analysis']
        order_block = self.analysis_cache['order_block_analysis']
        
        # Determine signal direction
        signal_type = self.determine_signal_type(structure, liquidity, order_block)
        
        # Calculate confidence
        confidence = self.calculate_confidence(structure, liquidity, order_block)
        
        return {
            'signal_id': generate_uuid(),
            'symbol': structure['symbol'],
            'signal_type': signal_type,
            'confidence': confidence,
            'entry_zone': self.calculate_entry_zone(order_block),
            'stop_loss': self.calculate_stop_loss(order_block, liquidity),
            'take_profit': self.calculate_take_profit(structure, liquidity),
            'timestamp': datetime.utcnow()
        }
```

### 4.3 Risk Management Swarm Design

**Risk Bot:**
```python
class RiskBot(Robot):
    async def process(self, data: Any) -> Any:
        """Calculate position size and validate risk"""
        signal = data['signal']
        account_info = await self.get_account_info()
        
        # Get risk profile from config
        risk_profile = self.config['risk_profile']
        risk_per_trade = risk_profile['risk_per_trade'] / 100
        
        # Calculate position size
        account_balance = account_info['balance']
        risk_amount = account_balance * risk_per_trade
        
        # Calculate pip value and lot size
        pip_distance = abs(signal['entry_zone']['mid'] - signal['stop_loss'])
        lot_size = self.calculate_lot_size(risk_amount, pip_distance, signal['symbol'])
        
        # Validate against limits
        if not self.validate_risk_limits(lot_size, account_info):
            await self.send_message('risk_rejected', {
                'signal_id': signal['signal_id'],
                'reason': 'Risk limits exceeded'
            })
            return None
            
        risk_approved_signal = {
            **signal,
            'lot_size': lot_size,
            'risk_amount': risk_amount,
            'risk_approved': True
        }
        
        await self.send_message('risk_approved', risk_approved_signal)
        return risk_approved_signal
```

### 4.4 Execution Swarm Design

**Execution Bot:**
```python
class ExecutionBot(Robot):
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.mt5 = MT5Connection(config['mt5'])
        self.max_retries = 3
        
    async def process(self, data: Any) -> Any:
        """Execute trade on MT5"""
        signal = data['signal']
        
        # Prepare order
        order = {
            'symbol': signal['symbol'],
            'type': MT5.ORDER_TYPE_BUY if signal['signal_type'] == 'BUY' else MT5.ORDER_TYPE_SELL,
            'volume': signal['lot_size'],
            'price': signal['entry_zone']['mid'],
            'sl': signal['stop_loss'],
            'tp': signal['take_profit'],
            'comment': f"Signal:{signal['signal_id']}"
        }
        
        # Execute with retries
        for attempt in range(self.max_retries):
            try:
                result = await self.mt5.place_order(order)
                if result.retcode == MT5.TRADE_RETCODE_DONE:
                    trade_data = {
                        'trade_id': result.order,
                        'signal_id': signal['signal_id'],
                        'execution_price': result.price,
                        'slippage': abs(result.price - order['price']),
                        'status': 'EXECUTED'
                    }
                    await self.send_message('trade_executed', trade_data)
                    await self.save_trade(trade_data, signal)
                    return trade_data
            except Exception as e:
                self.logger.error(f"Execution attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
                    
        # All retries failed
        await self.send_message('execution_failed', {
            'signal_id': signal['signal_id'],
            'reason': 'Max retries exceeded'
        })
        return None
```



## 5. Configuration Management

### 5.1 Configuration Structure

**config.yaml:**
```yaml
system:
  name: "Multi-Robot Trading System"
  version: "1.0.0"
  environment: "production"  # development, staging, production
  
mt5:
  broker: "IC Markets"
  account_number: 12345678
  server: "ICMarketsSC-Demo"
  password: "${MT5_PASSWORD}"
  leverage: 500
  
trading:
  style: "day_trading"  # scalping, day_trading, swing_trading
  risk_profile: "moderate"  # conservative, moderate, aggressive
  
  scalping:
    max_trade_duration: 15
    min_profit_target: 5
    
  day_trading:
    close_all_by: "23:00"
    min_profit_target: 10
    
  swing_trading:
    max_trade_duration: 72
    min_profit_target: 50
    
risk:
  conservative:
    risk_per_trade: 0.5
    max_daily_loss: 2.0
    max_drawdown: 8.0
    
  moderate:
    risk_per_trade: 1.0
    max_daily_loss: 3.0
    max_drawdown: 10.0
    
  aggressive:
    risk_per_trade: 2.0
    max_daily_loss: 5.0
    max_drawdown: 15.0
    
execution:
  max_simultaneous_trades: 3
  hedging_enabled: false
  martingale_enabled: false
  grid_trading_enabled: false
  
robots:
  enabled:
    - price_bot
    - structure_bot
    - liquidity_bot
    - order_block_bot
    - signal_aggregator_bot
    - risk_bot
    - execution_bot
    - trade_manager_bot
    - performance_monitor_bot
    - telegram_bot
    
  price_bot:
    update_interval: 1
    symbols: ["XAUUSD"]
    
  structure_bot:
    timeframes: ["M15", "H1", "H4"]
    lookback_periods: 100
    
database:
  postgresql:
    host: "localhost"
    port: 5432
    database: "trading_system"
    user: "${DB_USER}"
    password: "${DB_PASSWORD}"
    
  mongodb:
    host: "localhost"
    port: 27017
    database: "trading_logs"
    
  redis:
    host: "localhost"
    port: 6379
    db: 0
    
notifications:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"
    verbosity: "normal"
```

### 5.2 Configuration Manager Design

```python
class ConfigurationManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self.load_config()
        self.watchers = []
        
    def load_config(self) -> Dict:
        """Load configuration from YAML file"""
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        # Substitute environment variables
        return self.substitute_env_vars(config)
        
    def substitute_env_vars(self, config: Dict) -> Dict:
        """Replace ${VAR} with environment variable values"""
        config_str = json.dumps(config)
        for match in re.finditer(r'\$\{(\w+)\}', config_str):
            var_name = match.group(1)
            var_value = os.getenv(var_name, '')
            config_str = config_str.replace(match.group(0), var_value)
        return json.loads(config_str)
        
    def get(self, key_path: str, default=None):
        """Get configuration value by dot-notation path"""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
        
    def update(self, key_path: str, value: Any):
        """Update configuration value"""
        keys = key_path.split('.')
        config = self.config
        for key in keys[:-1]:
            config = config.setdefault(key, {})
        config[keys[-1]] = value
        self.save_config()
        self.notify_watchers(key_path, value)
        
    def watch(self, key_path: str, callback: Callable):
        """Watch for configuration changes"""
        self.watchers.append((key_path, callback))
```



## 6. API Specifications

### 6.1 Internal Robot API

**Message Events:**

```python
# Price Update Event
{
    "event": "price_update",
    "data": {
        "symbol": "XAUUSD",
        "bid": 2015.50,
        "ask": 2015.70,
        "spread": 0.20,
        "volume": 1000,
        "timestamp": "2026-03-08T10:30:00Z"
    }
}

# Structure Analysis Event
{
    "event": "structure_analysis",
    "data": {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "trend": "bullish",
        "bos_detected": true,
        "choch_detected": false,
        "structure_data": {...}
    }
}

# Trade Signal Event
{
    "event": "trade_signal",
    "data": {
        "signal_id": "uuid-here",
        "symbol": "XAUUSD",
        "signal_type": "BUY",
        "confidence": 0.85,
        "entry_zone": {"low": 2010.0, "high": 2012.0, "mid": 2011.0},
        "stop_loss": 2005.0,
        "take_profit": 2025.0
    }
}

# Risk Approved Event
{
    "event": "risk_approved",
    "data": {
        "signal_id": "uuid-here",
        "lot_size": 0.01,
        "risk_amount": 10.0,
        "risk_approved": true
    }
}

# Trade Executed Event
{
    "event": "trade_executed",
    "data": {
        "trade_id": "12345",
        "signal_id": "uuid-here",
        "execution_price": 2011.50,
        "slippage": 0.50,
        "status": "EXECUTED"
    }
}
```

### 6.2 Telegram Bot API

**Commands:**
```
/start - Start bot and show menu
/status - Show system status
/stats - Show performance statistics
/trades - Show open trades
/close_all - Close all open positions
/close_trade <id> - Close specific trade
/pause - Pause trading
/resume - Resume trading
/config - Show current configuration
/set_risk <profile> - Change risk profile (conservative/moderate/aggressive)
/set_style <style> - Change trading style (scalping/day_trading/swing_trading)
/killswitch - Emergency stop all trading
/help - Show help message
```

**Telegram Bot Design:**
```python
class TelegramBot(Robot):
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.bot = telegram.Bot(token=config['telegram']['bot_token'])
        self.chat_id = config['telegram']['chat_id']
        
    async def send_notification(self, message: str, parse_mode='Markdown'):
        """Send notification to user"""
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=message,
            parse_mode=parse_mode
        )
        
    async def handle_command(self, update, context):
        """Handle user commands"""
        command = update.message.text
        
        if command == '/status':
            status = await self.get_system_status()
            await self.send_notification(self.format_status(status))
            
        elif command == '/stats':
            stats = await self.get_performance_stats()
            await self.send_notification(self.format_stats(stats))
            
        elif command == '/killswitch':
            await self.send_message('kill_switch_activated', {})
            await self.send_notification("🚨 KILL SWITCH ACTIVATED - All trading stopped!")
```

### 6.3 Web Dashboard API

**REST Endpoints:**

```python
# GET /api/status
# Returns system status
{
    "status": "running",
    "active_robots": 10,
    "open_trades": 2,
    "account_balance": 1050.00,
    "daily_pnl": 50.00
}

# GET /api/trades
# Returns list of trades
{
    "trades": [
        {
            "trade_id": "12345",
            "symbol": "XAUUSD",
            "direction": "BUY",
            "entry_price": 2011.50,
            "current_price": 2015.00,
            "pnl": 35.00,
            "status": "OPEN"
        }
    ]
}

# GET /api/performance
# Returns performance metrics
{
    "win_rate": 0.56,
    "profit_factor": 1.9,
    "total_trades": 100,
    "winning_trades": 56,
    "losing_trades": 44,
    "net_profit": 500.00,
    "max_drawdown": 7.5
}

# POST /api/control/pause
# Pause trading
{
    "action": "pause",
    "reason": "Manual pause"
}

# POST /api/control/resume
# Resume trading
{
    "action": "resume"
}

# POST /api/control/close_trade
# Close specific trade
{
    "trade_id": "12345"
}
```



## 7. AI/ML Component Design

### 7.1 AI Confirmation Bot

```python
class AIConfirmationBot(Robot):
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.model = self.load_model()
        self.feature_extractor = FeatureExtractor()
        
    def load_model(self):
        """Load trained PyTorch model"""
        model = TradePredictionModel()
        model.load_state_dict(torch.load('models/trade_predictor.pth'))
        model.eval()
        return model
        
    async def process(self, data: Any) -> Any:
        """Predict trade outcome"""
        signal = data['signal']
        
        # Extract features
        features = await self.feature_extractor.extract(signal)
        
        # Predict
        with torch.no_grad():
            prediction = self.model(features)
            win_probability = torch.sigmoid(prediction).item()
            
        # Apply threshold
        min_confidence = self.config.get('min_confidence', 0.6)
        ai_approved = win_probability >= min_confidence
        
        result = {
            'signal_id': signal['signal_id'],
            'ai_win_probability': win_probability,
            'ai_approved': ai_approved,
            'ai_confidence': win_probability
        }
        
        await self.send_message('ai_confirmation', result)
        return result
```

### 7.2 Model Architecture

```python
class TradePredictionModel(nn.Module):
    def __init__(self, input_size=50, hidden_size=128):
        super().__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.bn1 = nn.BatchNorm1d(hidden_size)
        self.dropout1 = nn.Dropout(0.3)
        
        self.fc2 = nn.Linear(hidden_size, 64)
        self.bn2 = nn.BatchNorm1d(64)
        self.dropout2 = nn.Dropout(0.3)
        
        self.fc3 = nn.Linear(64, 32)
        self.bn3 = nn.BatchNorm1d(32)
        
        self.fc4 = nn.Linear(32, 1)
        
    def forward(self, x):
        x = F.relu(self.bn1(self.fc1(x)))
        x = self.dropout1(x)
        
        x = F.relu(self.bn2(self.fc2(x)))
        x = self.dropout2(x)
        
        x = F.relu(self.bn3(self.fc3(x)))
        x = self.fc4(x)
        
        return x
```

### 7.3 Feature Extraction

```python
class FeatureExtractor:
    def __init__(self):
        self.feature_names = [
            'trend_strength', 'volatility', 'volume_ratio',
            'rsi', 'macd', 'atr', 'bollinger_width',
            'liquidity_sweep', 'order_block_strength',
            'fvg_size', 'confluence_score', 'time_of_day',
            'day_of_week', 'market_session', 'spread',
            # ... 35 more features
        ]
        
    async def extract(self, signal: Dict) -> torch.Tensor:
        """Extract features from signal"""
        features = []
        
        # Technical indicators
        features.append(self.calculate_trend_strength(signal))
        features.append(self.calculate_volatility(signal))
        features.append(self.calculate_volume_ratio(signal))
        
        # ICT features
        features.append(1.0 if signal.get('liquidity_sweep') else 0.0)
        features.append(signal.get('order_block_strength', 0.0))
        features.append(signal.get('fvg_size', 0.0))
        
        # Time features
        features.append(self.encode_time_of_day(signal['timestamp']))
        features.append(self.encode_day_of_week(signal['timestamp']))
        
        # ... extract remaining features
        
        return torch.tensor(features, dtype=torch.float32)
```

### 7.4 Model Training Pipeline

```python
class ModelTrainer:
    def __init__(self, config: Dict):
        self.config = config
        self.model = TradePredictionModel()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        self.criterion = nn.BCEWithLogitsLoss()
        
    async def train(self, train_data, val_data, epochs=100):
        """Train the model"""
        best_val_loss = float('inf')
        patience = 10
        patience_counter = 0
        
        for epoch in range(epochs):
            # Training
            self.model.train()
            train_loss = 0.0
            for batch in train_data:
                features, labels = batch
                
                self.optimizer.zero_grad()
                outputs = self.model(features)
                loss = self.criterion(outputs, labels)
                loss.backward()
                self.optimizer.step()
                
                train_loss += loss.item()
                
            # Validation
            self.model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for batch in val_data:
                    features, labels = batch
                    outputs = self.model(features)
                    loss = self.criterion(outputs, labels)
                    val_loss += loss.item()
                    
            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                torch.save(self.model.state_dict(), 'models/trade_predictor.pth')
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    break
```



## 8. Safety & Control Systems

### 8.1 Kill Switch Design

```python
class KillSwitchBot(Robot):
    async def process(self, data: Any) -> Any:
        """Handle kill switch activation"""
        trigger = data.get('trigger', 'manual')
        
        # Log activation
        self.logger.critical(f"KILL SWITCH ACTIVATED: {trigger}")
        
        # Close all open positions
        await self.close_all_positions()
        
        # Pause all trading robots
        await self.pause_all_robots()
        
        # Send notifications
        await self.send_message('kill_switch_activated', {
            'trigger': trigger,
            'timestamp': datetime.utcnow(),
            'open_positions_closed': True
        })
        
        # Update system state
        await self.update_system_state('EMERGENCY_STOPPED')
        
    async def close_all_positions(self):
        """Close all open MT5 positions"""
        positions = await self.mt5.get_open_positions()
        for position in positions:
            await self.mt5.close_position(position.ticket)
```

### 8.2 Circuit Breaker Design

```python
class CircuitBreakerBot(Robot):
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.daily_loss_limit = config['risk']['max_daily_loss']
        self.weekly_loss_limit = config.get('weekly_loss_limit', 7.0)
        self.monthly_loss_limit = config.get('monthly_loss_limit', 15.0)
        
    async def process(self, data: Any) -> Any:
        """Monitor loss limits"""
        # Get current losses
        daily_loss = await self.get_daily_loss()
        weekly_loss = await self.get_weekly_loss()
        monthly_loss = await self.get_monthly_loss()
        
        # Check limits
        if daily_loss >= self.daily_loss_limit:
            await self.trigger_circuit_breaker('daily', daily_loss)
        elif weekly_loss >= self.weekly_loss_limit:
            await self.trigger_circuit_breaker('weekly', weekly_loss)
        elif monthly_loss >= self.monthly_loss_limit:
            await self.trigger_circuit_breaker('monthly', monthly_loss)
            
        # Send warnings at 50%, 75%, 90%
        await self.check_warning_thresholds(daily_loss, weekly_loss, monthly_loss)
        
    async def trigger_circuit_breaker(self, period: str, loss: float):
        """Trigger circuit breaker"""
        self.logger.warning(f"Circuit breaker triggered: {period} loss limit exceeded ({loss}%)")
        
        await self.send_message('circuit_breaker_triggered', {
            'period': period,
            'loss_percentage': loss,
            'limit': getattr(self, f'{period}_loss_limit')
        })
        
        # Pause trading
        await self.send_message('pause_trading', {
            'reason': f'{period.capitalize()} loss limit exceeded'
        })
```

### 8.3 Trading Limits Enforcer

```python
class TradingLimitsEnforcerBot(Robot):
    def __init__(self, robot_id: str, config: Dict, message_bus: MessageBus):
        super().__init__(robot_id, config, message_bus)
        self.max_trades_per_day = config.get('max_trades_per_day', 10)
        self.max_trades_per_hour = config.get('max_trades_per_hour', 3)
        self.min_time_between_trades = config.get('min_time_between_trades', 5)  # minutes
        self.trade_history = []
        
    async def process(self, data: Any) -> Any:
        """Validate trade against limits"""
        signal = data['signal']
        
        # Check daily limit
        today_trades = self.count_trades_today()
        if today_trades >= self.max_trades_per_day:
            await self.reject_trade(signal, 'Daily trade limit exceeded')
            return None
            
        # Check hourly limit
        hour_trades = self.count_trades_last_hour()
        if hour_trades >= self.max_trades_per_hour:
            await self.reject_trade(signal, 'Hourly trade limit exceeded')
            return None
            
        # Check time between trades
        if self.trade_history:
            last_trade_time = self.trade_history[-1]['timestamp']
            time_diff = (datetime.utcnow() - last_trade_time).total_seconds() / 60
            if time_diff < self.min_time_between_trades:
                await self.reject_trade(signal, 'Minimum time between trades not met')
                return None
                
        # All checks passed
        await self.send_message('limits_approved', signal)
        return signal
```



## 9. Deployment Architecture

### 9.1 Docker Compose Setup

```yaml
version: '3.8'

services:
  postgresql:
    image: postgres:15
    environment:
      POSTGRES_DB: trading_system
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped
    
  mongodb:
    image: mongo:6
    environment:
      MONGO_INITDB_DATABASE: trading_logs
    volumes:
      - mongo_data:/data/db
    ports:
      - "27017:27017"
    restart: unless-stopped
    
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped
    
  trading_system:
    build: .
    depends_on:
      - postgresql
      - mongodb
      - redis
    environment:
      - DB_HOST=postgresql
      - DB_PORT=5432
      - MONGO_HOST=mongodb
      - REDIS_HOST=redis
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
      - ./models:/app/models
    restart: unless-stopped
    
  web_dashboard:
    build:
      context: .
      dockerfile: Dockerfile.dashboard
    depends_on:
      - trading_system
    ports:
      - "8080:8080"
    restart: unless-stopped

volumes:
  postgres_data:
  mongo_data:
```

### 9.2 Systemd Service Configuration

```ini
[Unit]
Description=Multi-Robot Trading System
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=trading
WorkingDirectory=/opt/trading-system
ExecStart=/usr/bin/docker-compose up
ExecStop=/usr/bin/docker-compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 9.3 Project Structure

```
multi-robot-trading-system/
├── config/
│   ├── config.yaml
│   ├── config.production.yaml
│   ├── config.development.yaml
│   └── .env
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── master_controller.py
│   │   ├── robot_base.py
│   │   ├── message_bus.py
│   │   └── config_manager.py
│   ├── robots/
│   │   ├── data/
│   │   │   ├── price_bot.py
│   │   │   ├── tick_bot.py
│   │   │   └── ...
│   │   ├── analysis/
│   │   │   ├── structure_bot.py
│   │   │   ├── liquidity_bot.py
│   │   │   └── ...
│   │   ├── decision/
│   │   │   ├── signal_aggregator_bot.py
│   │   │   └── ...
│   │   ├── risk/
│   │   │   ├── risk_bot.py
│   │   │   └── ...
│   │   ├── execution/
│   │   │   ├── execution_bot.py
│   │   │   └── ...
│   │   └── monitoring/
│   │       ├── performance_monitor_bot.py
│   │       └── ...
│   ├── ai/
│   │   ├── models.py
│   │   ├── feature_extractor.py
│   │   ├── trainer.py
│   │   └── predictor.py
│   ├── database/
│   │   ├── postgres_manager.py
│   │   ├── mongo_manager.py
│   │   └── models.py
│   ├── integrations/
│   │   ├── mt5_connection.py
│   │   ├── telegram_bot.py
│   │   └── news_api.py
│   ├── utils/
│   │   ├── logger.py
│   │   ├── helpers.py
│   │   └── validators.py
│   └── main.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── backtesting/
├── models/
│   └── trade_predictor.pth
├── logs/
├── data/
│   ├── historical/
│   └── backtest/
├── docs/
│   ├── architecture.md
│   ├── api.md
│   └── deployment.md
├── scripts/
│   ├── setup.sh
│   ├── backup.sh
│   └── deploy.sh
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```



## 10. Error Handling & Resilience

### 10.1 Error Handling Strategy

```python
class ErrorHandler:
    def __init__(self, config: Dict):
        self.config = config
        self.error_counts = {}
        self.max_retries = 3
        self.backoff_multiplier = 2
        
    async def handle_error(self, robot_id: str, error: Exception, context: Dict):
        """Handle robot errors with retry logic"""
        error_type = type(error).__name__
        error_key = f"{robot_id}:{error_type}"
        
        # Increment error count
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Log error
        self.logger.error(f"Error in {robot_id}: {error}", extra=context)
        
        # Determine severity
        severity = self.determine_severity(error)
        
        if severity == 'CRITICAL':
            await self.handle_critical_error(robot_id, error, context)
        elif severity == 'HIGH':
            await self.handle_high_error(robot_id, error, context)
        else:
            await self.handle_normal_error(robot_id, error, context)
            
    async def handle_critical_error(self, robot_id: str, error: Exception, context: Dict):
        """Handle critical errors - trigger kill switch"""
        await self.send_notification(
            f"🚨 CRITICAL ERROR in {robot_id}: {error}",
            priority='CRITICAL'
        )
        await self.trigger_kill_switch(reason=f"Critical error: {error}")
        
    async def handle_high_error(self, robot_id: str, error: Exception, context: Dict):
        """Handle high severity errors - restart robot"""
        await self.send_notification(
            f"⚠️ HIGH ERROR in {robot_id}: {error}",
            priority='HIGH'
        )
        await self.restart_robot(robot_id)
        
    async def handle_normal_error(self, robot_id: str, error: Exception, context: Dict):
        """Handle normal errors - retry with backoff"""
        error_key = f"{robot_id}:{type(error).__name__}"
        retry_count = self.error_counts.get(error_key, 0)
        
        if retry_count < self.max_retries:
            backoff_time = self.backoff_multiplier ** retry_count
            await asyncio.sleep(backoff_time)
            # Retry will happen automatically
        else:
            await self.send_notification(
                f"⚠️ Max retries exceeded for {robot_id}: {error}",
                priority='HIGH'
            )
```

### 10.2 Health Monitoring

```python
class HealthMonitor:
    def __init__(self, config: Dict):
        self.config = config
        self.health_checks = {}
        self.check_interval = 60  # seconds
        
    async def monitor(self):
        """Continuous health monitoring"""
        while True:
            for robot_id in self.get_active_robots():
                health = await self.check_robot_health(robot_id)
                await self.update_health_status(robot_id, health)
                
                if health['status'] != 'HEALTHY':
                    await self.handle_unhealthy_robot(robot_id, health)
                    
            await asyncio.sleep(self.check_interval)
            
    async def check_robot_health(self, robot_id: str) -> Dict:
        """Check individual robot health"""
        robot = self.get_robot(robot_id)
        
        health = {
            'robot_id': robot_id,
            'status': 'HEALTHY',
            'last_heartbeat': robot.last_heartbeat,
            'error_count': robot.error_count,
            'cpu_usage': await self.get_cpu_usage(robot),
            'memory_usage': await self.get_memory_usage(robot),
            'message_queue_size': await self.get_queue_size(robot)
        }
        
        # Determine health status
        if (datetime.utcnow() - robot.last_heartbeat).seconds > 120:
            health['status'] = 'UNRESPONSIVE'
        elif robot.error_count > 10:
            health['status'] = 'DEGRADED'
        elif health['memory_usage'] > 90:
            health['status'] = 'RESOURCE_CONSTRAINED'
            
        return health
```

### 10.3 Backup & Recovery

```python
class BackupManager:
    def __init__(self, config: Dict):
        self.config = config
        self.backup_dir = config.get('backup_dir', '/backups')
        
    async def backup_database(self):
        """Backup PostgreSQL database"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{self.backup_dir}/db_backup_{timestamp}.sql"
        
        cmd = f"pg_dump -h {self.config['db_host']} -U {self.config['db_user']} " \
              f"-d {self.config['db_name']} > {backup_file}"
              
        await self.execute_command(cmd)
        await self.compress_backup(backup_file)
        await self.upload_to_cloud(backup_file)  # Optional
        
    async def backup_configuration(self):
        """Backup configuration files"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{self.backup_dir}/config_backup_{timestamp}.tar.gz"
        
        cmd = f"tar -czf {backup_file} config/"
        await self.execute_command(cmd)
        
    async def restore_database(self, backup_file: str):
        """Restore database from backup"""
        cmd = f"psql -h {self.config['db_host']} -U {self.config['db_user']} " \
              f"-d {self.config['db_name']} < {backup_file}"
              
        await self.execute_command(cmd)
```



## 11. Performance Optimization

### 11.1 Caching Strategy

```python
class CacheManager:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.default_ttl = 300  # 5 minutes
        
    async def get_cached_data(self, key: str) -> Optional[Any]:
        """Get data from cache"""
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
        
    async def set_cached_data(self, key: str, data: Any, ttl: int = None):
        """Set data in cache"""
        ttl = ttl or self.default_ttl
        await self.redis.setex(key, ttl, json.dumps(data))
        
    async def invalidate_cache(self, pattern: str):
        """Invalidate cache by pattern"""
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
```

**Caching Strategy:**
- Market data: Cache for 1 second (real-time)
- Analysis results: Cache for 5 minutes
- Configuration: Cache for 1 hour
- Performance metrics: Cache for 5 minutes
- Historical data: Cache for 1 day

### 11.2 Database Optimization

**Indexing Strategy:**
```sql
-- Market data indexes
CREATE INDEX idx_market_data_symbol_time ON market_data(symbol, timeframe, timestamp DESC);
CREATE INDEX idx_market_data_timestamp ON market_data(timestamp DESC);

-- Trades indexes
CREATE INDEX idx_trades_account ON trades(account_id);
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_entry_time ON trades(entry_time DESC);
CREATE INDEX idx_trades_strategy ON trades(strategy);

-- Signals indexes
CREATE INDEX idx_signals_symbol ON signals(symbol);
CREATE INDEX idx_signals_executed ON signals(executed);
CREATE INDEX idx_signals_created ON signals(created_at DESC);

-- Composite indexes
CREATE INDEX idx_trades_account_status ON trades(account_id, status);
CREATE INDEX idx_trades_symbol_time ON trades(symbol, entry_time DESC);
```

**Query Optimization:**
```python
class OptimizedQueries:
    @staticmethod
    async def get_recent_trades(account_id: str, limit: int = 100):
        """Optimized query for recent trades"""
        query = """
            SELECT * FROM trades
            WHERE account_id = $1
            ORDER BY entry_time DESC
            LIMIT $2
        """
        return await db.fetch(query, account_id, limit)
        
    @staticmethod
    async def get_performance_summary(account_id: str, days: int = 30):
        """Optimized aggregation query"""
        query = """
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(profit_loss) as net_profit,
                AVG(profit_loss) as avg_profit,
                MAX(profit_loss) as max_win,
                MIN(profit_loss) as max_loss
            FROM trades
            WHERE account_id = $1
              AND entry_time >= NOW() - INTERVAL '$2 days'
              AND status = 'CLOSED'
        """
        return await db.fetchrow(query, account_id, days)
```

### 11.3 Async Processing

```python
class AsyncProcessor:
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)
        
    async def process_batch(self, items: List[Any], processor: Callable):
        """Process items in parallel with concurrency limit"""
        async def process_with_semaphore(item):
            async with self.semaphore:
                return await processor(item)
                
        tasks = [process_with_semaphore(item) for item in items]
        return await asyncio.gather(*tasks, return_exceptions=True)
        
    async def process_stream(self, stream: AsyncIterator, processor: Callable):
        """Process stream of data asynchronously"""
        tasks = []
        async for item in stream:
            task = asyncio.create_task(processor(item))
            tasks.append(task)
            
            # Limit concurrent tasks
            if len(tasks) >= self.max_workers:
                done, tasks = await asyncio.wait(
                    tasks, 
                    return_when=asyncio.FIRST_COMPLETED
                )
                
        # Wait for remaining tasks
        if tasks:
            await asyncio.gather(*tasks)
```

