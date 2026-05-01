# Multi-Robot Trading System - Requirements

## 1. Vision & Overview

Build a distributed automated trading ecosystem composed of multiple intelligent robots (agents) that collaborate to analyze markets, detect trading opportunities, manage risk, execute trades, and learn from performance.

**Target Asset:** XAUUSD (Gold)  
**Execution Platform:** MetaTrader 5  
**System Concept:** Many small intelligent robots working together to achieve profitable trading

### 1.1 Project Specifications

**Account Details:**
- Minimum starting capital: $10
- Account type: MT5 with broker (setup required)
- API access: Required (to be configured)
- Historical data: Required for backtesting

**Trading Flexibility:**
- Support multiple trading styles (configurable):
  - Scalping (many small trades, quick exits)
  - Day trading (close all by end of day)
  - Swing trading (hold for days/weeks)
- User can switch between styles via configuration

**Risk Management Profiles:**
- Conservative: 0.5% risk per trade, max 2% daily loss
- Moderate: 1% risk per trade, max 3% daily loss
- Aggressive: 2% risk per trade, max 5% daily loss
- Profile is configurable per user preference

**Infrastructure:**
- Deployment: Local Linux machine
- Monitoring: Telegram bot notifications
- AI Strategy: Hybrid approach (ICT rules + AI confirmation)

**Timeline:**
- Phase 1 (Months 1-3): MVP with 8 core robots
- Phase 2 (Months 4-6): Expand to 25 robots
- Phase 3 (Months 7-12): Scale to 100+ robots with advanced AI
- Live trading target: 6-12 months

## 2. System Architecture

### 2.1 Core Layers

The system consists of 6 main architectural layers:

1. **Control Layer** - Central coordination and orchestration
2. **Data Layer** - Market data collection and aggregation
3. **Analysis Layer** - ICT-style market analysis
4. **Decision Layer** - Signal generation and confluence checking
5. **Risk Management Layer** - Position sizing and exposure control
6. **Execution Layer** - Trade execution and management
7. **Monitoring Layer** - System health and performance tracking
8. **Learning Layer** - Strategy optimization and AI prediction

### 2.2 Communication Architecture

Robots communicate through message events using a message bus (Redis/RabbitMQ/Kafka).

**Message Format:**
```json
{
  "bot": "LiquidityBot",
  "event": "SweepDetected",
  "price": 2021.5,
  "timeframe": "M15",
  "timestamp": "2026-03-08T10:30:00Z"
}
```

## 3. User Stories & Acceptance Criteria

### 3.1 Data Collection Swarm (6 Robots)

#### US-1: Price Data Collection
**As a** trading system  
**I want** real-time price data from MetaTrader 5  
**So that** I can analyze current market conditions

**Acceptance Criteria:**
- AC-1.1: System fetches live bid/ask prices every second
- AC-1.2: System collects OHLC data for multiple timeframes (M1, M5, M15, H1, H4, D1)
- AC-1.3: Data is stored in PostgreSQL with timestamp indexing
- AC-1.4: System handles MT5 connection failures gracefully
- AC-1.5: Price data includes spread and volume information

#### US-2: Tick Data Collection
**As a** high-frequency analysis system  
**I want** raw tick-level data  
**So that** I can perform granular market analysis

**Acceptance Criteria:**
- AC-2.1: System captures every tick from MT5
- AC-2.2: Tick data includes timestamp, bid, ask, volume
- AC-2.3: System can handle 100+ ticks per second
- AC-2.4: Tick data is buffered and batch-inserted to database

#### US-3: Multi-Timeframe Aggregation
**As a** market analyzer  
**I want** candle data across multiple timeframes  
**So that** I can identify multi-timeframe confluence

**Acceptance Criteria:**
- AC-3.1: System converts tick data to M1, M5, M15, H1, H4 candles
- AC-3.2: Candles are synchronized across timeframes
- AC-3.3: System validates candle completeness before analysis

#### US-4: Volatility Scanning
**As a** risk manager  
**I want** real-time volatility metrics  
**So that** I can adjust position sizing dynamically

**Acceptance Criteria:**
- AC-4.1: System calculates ATR (Average True Range) for multiple periods
- AC-4.2: System tracks standard deviation and Bollinger Band width
- AC-4.3: Volatility alerts are triggered when thresholds are exceeded
- AC-4.4: Volatility data is updated every minute

#### US-5: Economic News Monitoring
**As a** fundamental analyst  
**I want** economic news and event tracking  
**So that** I can avoid trading during high-impact news

**Acceptance Criteria:**
- AC-5.1: System fetches economic calendar from reliable sources
- AC-5.2: High-impact events (Federal Reserve, ECB) are flagged
- AC-5.3: Trading is paused 15 minutes before and after major news
- AC-5.4: News sentiment is classified (bullish/bearish/neutral)

#### US-6: Market Sentiment Analysis
**As a** sentiment trader  
**I want** aggregated market sentiment data  
**So that** I can gauge market psychology

**Acceptance Criteria:**
- AC-6.1: System collects sentiment from social media and financial news
- AC-6.2: Sentiment score ranges from -100 (bearish) to +100 (bullish)
- AC-6.3: Sentiment data is updated every 5 minutes
- AC-6.4: Extreme sentiment levels trigger alerts

### 3.2 Market Structure & Analysis Swarm (7 Robots)

#### US-7: Market Structure Detection
**As a** technical analyst  
**I want** automated market structure identification  
**So that** I can trade with the trend

**Acceptance Criteria:**
- AC-7.1: System detects higher highs, higher lows, lower highs, lower lows
- AC-7.2: System identifies BOS (Break of Structure)
- AC-7.3: System identifies CHOCH (Change of Character)
- AC-7.4: Trend direction is classified (bullish/bearish/ranging)
- AC-7.5: Structure analysis runs on M15, H1, H4 timeframes

#### US-8: Liquidity Detection
**As an** ICT trader  
**I want** liquidity sweep detection  
**So that** I can identify institutional entry zones

**Acceptance Criteria:**
- AC-8.1: System identifies equal highs and equal lows
- AC-8.2: System detects liquidity sweeps (stop hunts)
- AC-8.3: System tracks order clusters from volume profile
- AC-8.4: Liquidity zones are marked on charts
- AC-8.5: Sweep confirmation requires price rejection within 5 candles

#### US-9: Order Block Identification
**As an** institutional trader  
**I want** order block detection  
**So that** I can enter at supply/demand zones

**Acceptance Criteria:**
- AC-9.1: System identifies bullish order blocks (last down candle before rally)
- AC-9.2: System identifies bearish order blocks (last up candle before drop)
- AC-9.3: Order blocks are validated by volume and structure
- AC-9.4: Order blocks expire after 20 candles if not tested
- AC-9.5: System tracks order block strength (fresh/tested/broken)

#### US-10: Fair Value Gap Detection
**As a** price action trader  
**I want** FVG (Fair Value Gap) identification  
**So that** I can trade imbalances

**Acceptance Criteria:**
- AC-10.1: System detects 3-candle FVG patterns
- AC-10.2: FVG zones are measured in pips
- AC-10.3: System tracks FVG fill percentage
- AC-10.4: Unfilled FVGs are prioritized for entries
- AC-10.5: FVG detection works on M15, H1, H4 timeframes

#### US-11: Imbalance Detection
**As a** smart money trader  
**I want** price inefficiency detection  
**So that** I can anticipate reversals

**Acceptance Criteria:**
- AC-11.1: System identifies single-candle imbalances
- AC-11.2: System identifies multi-candle imbalances
- AC-11.3: Imbalances are classified by size (small/medium/large)
- AC-11.4: System tracks imbalance fill rate

#### US-12: Accumulation/Distribution Tracking
**As a** volume analyst  
**I want** smart money positioning analysis  
**So that** I can follow institutional flow

**Acceptance Criteria:**
- AC-12.1: System calculates accumulation/distribution indicator
- AC-12.2: System detects divergences between price and A/D
- AC-12.3: Volume spikes are flagged and analyzed
- AC-12.4: Smart money phases are identified (accumulation/markup/distribution/markdown)

#### US-13: Trend Strength Measurement
**As a** momentum trader  
**I want** trend strength quantification  
**So that** I can filter weak setups

**Acceptance Criteria:**
- AC-13.1: System calculates ADX (Average Directional Index)
- AC-13.2: System measures momentum using RSI and MACD
- AC-13.3: Trend strength is scored 0-100
- AC-13.4: Weak trends (<30) are filtered out

### 3.3 Decision & Signal Swarm (5 Robots)

#### US-14: Signal Aggregation
**As a** decision system  
**I want** combined analysis from all bots  
**So that** I can generate preliminary trade signals

**Acceptance Criteria:**
- AC-14.1: System collects outputs from all 13 analysis bots
- AC-14.2: Signals are timestamped and versioned
- AC-14.3: Conflicting signals are flagged
- AC-14.4: Signal aggregation completes within 1 second

#### US-15: Confluence Analysis
**As a** high-probability trader  
**I want** multi-factor confluence checking  
**So that** I only take the best setups

**Acceptance Criteria:**
- AC-15.1: System requires minimum 3 confluence factors
- AC-15.2: Confluence factors: OB + FVG + Liquidity + Structure + Trend
- AC-15.3: Each factor is weighted by importance
- AC-15.4: Confluence score ranges from 0-100%
- AC-15.5: Minimum confluence threshold is 70% for trade execution

#### US-16: Entry Decision
**As an** execution system  
**I want** precise entry zone and timing  
**So that** I can maximize risk/reward ratio

**Acceptance Criteria:**
- AC-16.1: Entry zone is defined with upper and lower bounds
- AC-16.2: Entry timing considers timeframe alignment
- AC-16.3: System waits for confirmation candle before entry
- AC-16.4: Entry is invalidated if price moves beyond zone

#### US-17: AI Confirmation
**As a** machine learning system  
**I want** AI-based trade filtering  
**So that** I can improve win rate

**Acceptance Criteria:**
- AC-17.1: AI model predicts trade outcome (win/loss probability)
- AC-17.2: Model is trained on historical trade data
- AC-17.3: Minimum AI confidence threshold is 60%
- AC-17.4: Model is retrained weekly with new data

#### US-18: Confidence Scoring
**As a** risk manager  
**I want** confidence scores for each trade  
**So that** I can adjust position sizing

**Acceptance Criteria:**
- AC-18.1: Confidence score combines confluence + AI + volatility
- AC-18.2: Score ranges from 0-100%
- AC-18.3: High confidence (>80%) allows larger position sizes
- AC-18.4: Low confidence (<50%) trades are rejected

### 3.4 Risk & Execution Swarm (4 Robots)

#### US-19: Risk Calculation
**As a** risk manager  
**I want** dynamic position sizing with configurable risk profiles  
**So that** I protect capital and adapt to user preferences

**Acceptance Criteria:**
- AC-19.1: System supports 3 risk profiles (Conservative/Moderate/Aggressive)
- AC-19.2: Conservative: 0.5% risk per trade, 2% max daily loss, 8% max drawdown
- AC-19.3: Moderate: 1% risk per trade, 3% max daily loss, 10% max drawdown
- AC-19.4: Aggressive: 2% risk per trade, 5% max daily loss, 15% max drawdown
- AC-19.5: Position size adjusts based on volatility (ATR) and account balance
- AC-19.6: Stop loss is placed beyond order block or liquidity zone
- AC-19.7: Minimum position size is 0.01 lots (micro lot)
- AC-19.8: System handles accounts as small as $10
- AC-19.9: Risk profile can be changed via configuration file
- AC-19.10: Daily loss limit triggers trading pause until next day

#### US-20: Trade Execution
**As an** execution bot  
**I want** reliable order placement on MT5  
**So that** trades are executed without slippage

**Acceptance Criteria:**
- AC-20.1: Orders are sent to MT5 via Python API
- AC-20.2: Order confirmation is received within 2 seconds
- AC-20.3: Slippage is monitored and logged
- AC-20.4: Failed orders are retried up to 3 times
- AC-20.5: Order details include symbol, type, lot size, SL, TP

#### US-21: Trade Management
**As a** trade manager  
**I want** dynamic trade adjustments  
**So that** I maximize profits and minimize losses

**Acceptance Criteria:**
- AC-21.1: Stop loss moves to break-even after 1:1 RR
- AC-21.2: Trailing stop activates after 1.5:1 RR
- AC-21.3: Partial close (50%) at 2:1 RR
- AC-21.4: Remaining position trails with 20-pip buffer
- AC-21.5: Trade is closed if structure breaks against position

#### US-22: Stop Loss & Take Profit Management
**As a** risk controller  
**I want** dynamic SL/TP adjustment  
**So that** I adapt to changing market conditions

**Acceptance Criteria:**
- AC-22.1: SL adjusts based on ATR (2x ATR minimum)
- AC-22.2: TP targets next liquidity zone or FVG
- AC-22.3: SL never widens, only tightens
- AC-22.4: TP can extend if momentum continues

### 3.5 Monitoring & Learning Swarm (3 Robots)

#### US-23: Performance Monitoring
**As a** system administrator  
**I want** real-time performance metrics  
**So that** I can evaluate system effectiveness

**Acceptance Criteria:**
- AC-23.1: System tracks win rate, profit factor, drawdown
- AC-23.2: Metrics are updated after each trade
- AC-23.3: Daily, weekly, monthly reports are generated
- AC-23.4: Performance dashboard is accessible via web interface
- AC-23.5: Alerts are sent when performance degrades

#### US-24: Error Monitoring
**As a** system administrator  
**I want** error detection and alerting  
**So that** I can maintain system uptime

**Acceptance Criteria:**
- AC-24.1: System detects MT5 connection failures
- AC-24.2: System detects database connection issues
- AC-24.3: System detects bot crashes and restarts them
- AC-24.4: Error logs are stored with severity levels
- AC-24.5: Critical errors trigger immediate notifications

#### US-25: Backtesting & Optimization
**As a** strategy developer  
**I want** automated backtesting and optimization  
**So that** I can improve strategy parameters

**Acceptance Criteria:**
- AC-25.1: System backtests strategies on 2+ years of data
- AC-25.2: Optimization uses walk-forward analysis
- AC-25.3: Overfitting is detected and prevented
- AC-25.4: Best parameters are automatically deployed
- AC-25.5: Backtest results include all key metrics

### 3.6 Notification & Communication (2 Robots)

#### US-26: Telegram Notification Bot
**As a** trader  
**I want** real-time Telegram notifications  
**So that** I stay informed about system activity

**Acceptance Criteria:**
- AC-26.1: System sends trade entry notifications with details (symbol, direction, price, SL, TP)
- AC-26.2: System sends trade exit notifications with P&L
- AC-26.3: System sends daily performance summary at market close
- AC-26.4: System sends error alerts for critical issues
- AC-26.5: System sends risk alerts when daily loss limit is approached
- AC-26.6: Notifications include emoji indicators (🟢 profit, 🔴 loss, ⚠️ warning)
- AC-26.7: User can configure notification verbosity (minimal/normal/detailed)
- AC-26.8: Telegram bot responds to basic commands (/status, /stats, /pause, /resume)

#### US-27: Configuration Manager Bot
**As a** system administrator  
**I want** dynamic configuration management  
**So that** I can adjust settings without restarting the system

**Acceptance Criteria:**
- AC-27.1: Trading style can be changed (scalping/day trading/swing trading)
- AC-27.2: Risk profile can be changed (conservative/moderate/aggressive)
- AC-27.3: Individual robot parameters can be adjusted
- AC-27.4: Configuration changes are validated before applying
- AC-27.5: Configuration history is tracked with timestamps
- AC-27.6: Invalid configurations are rejected with error messages
- AC-27.7: Configuration can be changed via Telegram bot commands
- AC-27.8: System reloads configuration without full restart

## 4. Technical Requirements

### 4.1 Technology Stack
- **Language:** Python 3.10+
- **Trading Platform:** MetaTrader 5 (with Python API: MetaTrader5 package)
- **Databases:** 
  - PostgreSQL (structured data: trades, signals, market data)
  - MongoDB (logs, events, unstructured data)
- **Message Bus:** Redis (lightweight, fast, suitable for local deployment)
- **AI/ML:** PyTorch (primary) or TensorFlow (alternative)
- **Notifications:** python-telegram-bot library
- **Deployment:** Docker containers on Linux (Ubuntu 22.04+)
- **Process Management:** systemd or supervisord
- **Web Dashboard:** Flask or FastAPI (optional, Phase 2+)

### 4.2 Performance Requirements
- **Latency:** Signal generation < 1 second
- **Throughput:** Handle 100+ ticks/second
- **Uptime:** 99.5% availability during market hours
- **Scalability:** Support 25-100 robots
- **Memory:** Maximum 4GB RAM usage for full system
- **CPU:** Efficient multi-threading for parallel robot execution
- **Disk:** Minimum 50GB for databases and logs

### 4.3 Security Requirements
- **API Keys:** Stored in .env file (never committed to git)
- **MT5 Credentials:** Encrypted storage using cryptography library
- **Database:** Password-protected with SSL connections
- **Telegram Bot:** Token stored securely, webhook validation
- **Logs:** No sensitive data (passwords, API keys) in logs
- **Access:** File permissions restricted to user only (chmod 600)

### 4.4 Configuration Requirements

#### 4.4.1 Trading Style Configuration
```yaml
trading_style:
  mode: "day_trading"  # scalping, day_trading, swing_trading
  scalping:
    max_trade_duration: 15  # minutes
    min_profit_target: 5    # pips
  day_trading:
    close_all_by: "23:00"   # UTC time
    min_profit_target: 10   # pips
  swing_trading:
    max_trade_duration: 72  # hours
    min_profit_target: 50   # pips
```

#### 4.4.2 Risk Profile Configuration
```yaml
risk_profile:
  mode: "moderate"  # conservative, moderate, aggressive
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
```

#### 4.4.3 Broker & MT5 Configuration
```yaml
mt5:
  broker: "IC Markets"  # configurable broker name
  account_type: "demo"  # demo, live
  account_number: 12345678
  server: "ICMarketsSC-Demo"
  leverage: 500  # 1:100, 1:500, 1:1000
  multiple_accounts:
    enabled: false
    accounts:
      - account_id: "account1"
        number: 12345678
        type: "demo"
      - account_id: "account2"
        number: 87654321
        type: "live"
```

#### 4.4.4 Data Management Configuration
```yaml
data:
  historical_storage:
    duration: "5_years"  # 1_year, 5_years, all_data
    cleanup_policy: "archive_old"  # delete_old, archive_old, keep_all
  
  symbols:
    primary: "XAUUSD"
    additional: []  # ["EURUSD", "GBPUSD"] for multi-symbol analysis
    correlation_tracking:
      enabled: true
      symbols: ["DXY", "USOIL", "US10Y"]  # USD index, Oil, Treasury
  
  sentiment_sources:
    twitter: true
    reddit: true
    news_feeds: true
    competitor_analysis: false
```

#### 4.4.5 Trade Execution Configuration
```yaml
execution:
  max_simultaneous_trades: 3  # 1, 3, 5, unlimited (-1)
  
  hedging:
    enabled: false  # allow opposite direction trades
    max_hedge_ratio: 0.5  # max hedge size relative to main position
  
  advanced_strategies:
    martingale:
      enabled: false  # WARNING: High risk
      multiplier: 2.0
      max_levels: 3
    grid_trading:
      enabled: false  # WARNING: High risk
      grid_size: 10  # pips
      max_grid_levels: 5
  
  news_trading:
    mode: "pause"  # pause, continue, aggressive
    pause_before: 15  # minutes before news
    pause_after: 15   # minutes after news
    high_impact_only: true
```

#### 4.4.6 AI/ML Configuration
```yaml
ai:
  prediction_target: "win_probability"  # price_direction, win_probability, optimal_entry_exit
  
  model_training:
    frequency: "weekly"  # daily, weekly, monthly
    min_samples: 100  # minimum trades before retraining
    validation_split: 0.2
  
  learning:
    learn_from_losses: true
    avoid_similar_setups: true
    similarity_threshold: 0.85
  
  sentiment_analysis:
    twitter:
      enabled: true
      keywords: ["gold", "xauusd", "fed", "inflation"]
    reddit:
      enabled: true
      subreddits: ["forex", "wallstreetbets", "gold"]
    news:
      enabled: true
      sources: ["reuters", "bloomberg", "forexfactory"]
```

#### 4.4.7 Reporting Configuration
```yaml
reporting:
  pdf_reports:
    enabled: true
    frequency: ["daily", "weekly", "monthly"]
    include_charts: true
    email_delivery: false
  
  performance_tracking:
    by_time_of_day: true
    by_day_of_week: true
    by_market_session: true  # Asian, London, New York
    by_strategy: true
  
  benchmarking:
    compare_buy_hold: true
    compare_previous_month: true
  
  cost_analysis:
    track_slippage: true
    track_spread: true
    track_commission: true
    track_swap: true
```

#### 4.4.8 Advanced Features Configuration
```yaml
advanced:
  copy_trading:
    enabled: false
    master_account: "account1"
    slave_accounts: ["account2", "account3"]
    copy_ratio: 1.0  # 1.0 = 100%, 0.5 = 50% of master size
  
  manual_override:
    telegram_commands: true
    allowed_commands:
      - "close_all"
      - "close_trade"
      - "pause_trading"
      - "resume_trading"
      - "force_entry"  # manual trade entry
  
  web_dashboard:
    enabled: true
    port: 8080
    access:
      local_only: true  # false for remote access
      password_protected: true
      allowed_ips: ["192.168.1.0/24"]
  
  custom_strategies:
    backtesting_support: true
    strategy_directory: "strategies/custom/"
    hot_reload: true  # reload strategies without restart
```

#### 4.4.9 Safety Limits Configuration
```yaml
safety:
  trading_limits:
    max_trades_per_day: 10  # -1 for unlimited
    min_time_between_trades: 5  # minutes
    max_trades_per_hour: 3
  
  loss_protection:
    pause_after_consecutive_losses: 3
    pause_duration: 60  # minutes
    resume_automatically: true
  
  kill_switch:
    enabled: true
    triggers:
      - "telegram_command"  # /killswitch
      - "max_drawdown_exceeded"
      - "critical_error"
    action: "close_all_and_pause"  # close_all_and_pause, pause_only
  
  circuit_breaker:
    enabled: true
    daily_loss_limit: 3.0  # percentage
    weekly_loss_limit: 7.0
    monthly_loss_limit: 15.0
```

#### 4.4.10 Notification Configuration
```yaml
notifications:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"
    verbosity: "normal"  # minimal, normal, detailed
    
    notify_on:
      trade_entry: true
      trade_exit: true
      daily_summary: true
      weekly_summary: true
      error_critical: true
      error_warning: false
      risk_alert: true
      performance_milestone: true  # e.g., 10% profit
      
    quiet_hours:
      enabled: false
      start: "23:00"
      end: "07:00"
      timezone: "UTC"
```

### 4.5 MT5 Setup Requirements
- **Broker Requirements:**
  - Support for MetaTrader 5 platform
  - API/algorithmic trading enabled
  - XAUUSD symbol available
  - Minimum deposit: $10
  - Micro lots (0.01) supported

- **MT5 Configuration:**
  - Enable "Allow algorithmic trading" in settings
  - Enable "Allow DLL imports" (for Python integration)
  - Stable internet connection to broker server
  - Historical data downloaded (minimum 2 years for XAUUSD)

- **Python MT5 Integration:**
  - Install MetaTrader5 Python package
  - Configure MT5 terminal path
  - Test connection and data retrieval
  - Verify order execution capabilities

## 5. Minimum Viable System (MVP)

**Phase 1 - Core 10 Robots (Months 1-3):**
1. Price Bot (Data Collection)
2. Structure Bot (Market Analysis)
3. Liquidity Bot (Market Analysis)
4. Order Block Bot (Market Analysis)
5. Signal Aggregator Bot (Decision)
6. Risk Bot (Risk Management)
7. Execution Bot (Execution)
8. Trade Manager Bot (Trade Management)
9. Performance Monitor Bot (Monitoring)
10. Telegram Notification Bot (Communication)

**MVP Success Criteria:**
- System executes 1-3 trades per day (depending on trading style)
- Win rate > 50% over 30 days
- Risk per trade matches configured profile
- System runs for 30 days without critical errors
- All trades logged to database
- Telegram notifications working reliably
- MT5 connection stable (99%+ uptime)
- Backtesting shows positive expectancy

**MVP Configuration:**
- Trading Style: Day Trading (close all by end of day)
- Risk Profile: Conservative (0.5% per trade)
- Account Size: $10 minimum
- Asset: XAUUSD only
- Timeframes: M15, H1, H4
- Advanced features: Disabled (martingale, grid, hedging)
- Multi-account: Disabled
- Web dashboard: Optional

**Phase 2 - Expand to 44 Robots (Months 4-6):**

Add remaining analysis bots (7):
- Fair Value Gap Bot
- Imbalance Bot
- Accumulation/Distribution Bot
- Trend Strength Bot
- Volatility Scanner Bot
- News & Events Bot
- Sentiment Bot

Add data collection bots (2):
- Multi-Timeframe Aggregator Bot
- Tick Bot

Add decision bots (3):
- Confluence Bot
- Entry Decision Bot
- AI Confirmation Bot
- Confidence Scoring Bot

Add execution bots (1):
- Stop Loss/Take Profit Bot

Add monitoring bots (2):
- Error Monitor Bot
- Backtesting & Optimizer Bot

Add communication bots (1):
- Configuration Manager Bot

Add advanced trading bots (6):
- Multi-Account Manager Bot
- Multi-Symbol Analysis Bot
- Advanced Strategy Bot (Martingale/Grid)
- News Trading Manager Bot
- Hedging Manager Bot
- Copy Trading Bot

Add safety bots (4):
- Trading Limits Enforcer Bot
- Loss Protection Bot
- Kill Switch Bot
- Circuit Breaker Bot

Add reporting bots (3):
- PDF Report Generator Bot
- Performance Analytics Bot
- Cost Analysis Bot

Add dashboard bots (2):
- Web Dashboard Bot
- Manual Override Bot

Add custom strategy bots (2):
- Custom Strategy Loader Bot
- Strategy Backtesting Bot

**Total Phase 2: 44 Robots**

**Phase 2 Success Criteria:**
- Win rate > 55%
- Profit factor > 1.5
- Maximum drawdown < 10%
- Support all 3 trading styles
- Support all 3 risk profiles
- AI confirmation improving win rate by 5%+
- Multi-account support working
- Web dashboard operational
- All safety features tested

**Phase 3 - Scale to 100+ Robots (Months 7-12):**
- Advanced AI prediction models (LSTM, Transformer, Reinforcement Learning)
- Multi-asset support (EUR/USD, GBP/USD, BTC/USD, etc.)
- Specialized robots for different market conditions (trending, ranging, volatile)
- Market regime detection robots
- Sentiment analysis robots (Twitter, Reddit, News)
- Economic indicator robots (GDP, CPI, NFP, etc.)
- Seasonal pattern robots
- Inter-market analysis robots
- Portfolio optimization robots
- Self-learning optimization robots
- Advanced risk management (correlation, VaR, CVaR)
- High-frequency trading robots (if broker supports)
- Options and futures support (if applicable)

**Phase 3 Success Criteria:**
- Win rate > 60%
- Profit factor > 2.0
- Maximum drawdown < 10%
- Sharpe ratio > 1.5
- Multi-asset trading operational
- 100+ robots working in harmony
- Self-learning optimization showing improvements
- Ready for live trading with real capital
- System handles all market conditions
- Minimal manual intervention required

## 6. Future Enhancements

- Multi-asset support (Forex pairs: EUR/USD, GBP/USD, USD/JPY)
- Cryptocurrency trading (BTC/USD, ETH/USD via Binance API)
- Commodities (Oil, Silver)
- 100+ specialized robots
- Advanced AI prediction models (LSTM, Transformer)
- Self-learning optimization with reinforcement learning
- Multi-broker support (Interactive Brokers, Binance)
- Mobile app for monitoring
- Advanced portfolio management
- Social trading features (copy trading)
- Cloud deployment option (AWS, DigitalOcean)

## 7. Deployment & Operations

### 7.1 Local Linux Deployment

**System Requirements:**
- OS: Ubuntu 22.04 LTS or newer
- CPU: 4+ cores recommended
- RAM: 8GB minimum, 16GB recommended
- Disk: 100GB SSD recommended
- Network: Stable broadband (10+ Mbps)

**Installation Steps:**
1. Install Python 3.10+
2. Install PostgreSQL and MongoDB
3. Install Redis
4. Install MetaTrader 5 (via Wine if needed)
5. Clone repository and install dependencies
6. Configure environment variables
7. Initialize databases
8. Run setup scripts
9. Start robot services
10. Configure Telegram bot

**Service Management:**
```bash
# Start all robots
sudo systemctl start trading-system

# Stop all robots
sudo systemctl stop trading-system

# Check status
sudo systemctl status trading-system

# View logs
journalctl -u trading-system -f
```

### 7.2 Monitoring & Maintenance

**Daily Tasks:**
- Check Telegram notifications
- Review trade performance
- Monitor system health

**Weekly Tasks:**
- Review win rate and profit factor
- Analyze losing trades
- Adjust parameters if needed
- Backup databases

**Monthly Tasks:**
- Full system audit
- Strategy optimization
- Update AI models
- Review and update requirements

### 7.3 Disaster Recovery

**Backup Strategy:**
- Database backups: Daily at 00:00 UTC
- Configuration backups: After each change
- Log retention: 90 days
- Trade history: Permanent

**Recovery Procedures:**
- MT5 connection loss: Auto-reconnect every 30 seconds
- Database failure: Switch to backup database
- Critical error: Pause trading, send alert
- System crash: Auto-restart via systemd

### 7.4 Testing Strategy

**Unit Testing:**
- Test each robot independently
- Mock external dependencies (MT5, database)
- Achieve 80%+ code coverage

**Integration Testing:**
- Test robot communication via message bus
- Test end-to-end trade execution flow
- Test error handling and recovery

**Backtesting:**
- Test on 2+ years of historical data
- Walk-forward optimization
- Out-of-sample validation
- Monte Carlo simulation

**Paper Trading:**
- Run system with real data but simulated trades
- Minimum 30 days before live trading
- Verify all metrics match expectations

## 7. Constraints & Assumptions

**Constraints:**
- MT5 API rate limits (varies by broker)
- Market hours (24/5 for Forex, closed weekends)
- Minimum account balance: $10
- Local Linux machine resources (CPU, RAM, disk)
- Internet connection stability required
- Broker-specific limitations (leverage, spreads, commissions)
- Python MT5 library limitations
- Redis memory limits for message bus

**Assumptions:**
- Stable internet connection (99%+ uptime)
- MT5 account with broker (setup in progress)
- API access will be enabled by broker
- Historical data available for backtesting (minimum 2 years)
- ICT concepts are valid for XAUUSD trading
- Telegram bot API available and stable
- User has basic Linux system administration skills
- Broker allows algorithmic trading
- XAUUSD spreads are reasonable (< 30 pips)
- No major regulatory changes during development
- User can dedicate time for initial setup and monitoring

## 8. Glossary

- **BOS:** Break of Structure - Price breaks previous high/low indicating trend continuation
- **CHOCH:** Change of Character - Market structure shift indicating potential reversal
- **FVG:** Fair Value Gap - Price imbalance showing inefficiency in the market
- **OB:** Order Block - Institutional supply/demand zone where smart money entered
- **ICT:** Inner Circle Trader methodology - Trading concepts by Michael Huddleston
- **ATR:** Average True Range - Volatility indicator measuring price movement
- **RR:** Risk/Reward ratio - Ratio of potential profit to potential loss
- **Liquidity Sweep:** Price movement to trigger stop losses before reversing
- **Smart Money:** Institutional traders (banks, hedge funds, market makers)
- **Confluence:** Multiple technical factors aligning for trade setup
- **Drawdown:** Peak-to-trough decline in account balance
- **Profit Factor:** Gross profit divided by gross loss
- **Slippage:** Difference between expected and actual execution price
- **Pip:** Smallest price movement (0.01 for XAUUSD)
- **Lot:** Trading volume unit (0.01 = micro lot)
- **Spread:** Difference between bid and ask price
- **Timeframe:** Chart period (M1=1min, M5=5min, H1=1hour, etc.)

## 9. Risk Disclaimer

**Important Notice:**
- Trading involves substantial risk of loss
- Past performance does not guarantee future results
- This system is for educational and research purposes
- Start with minimum capital ($10) and conservative settings
- Never risk more than you can afford to lose
- Monitor system performance regularly
- Be prepared for losing streaks
- Understand that no trading system is 100% profitable
- Market conditions can change, requiring strategy adjustments
- Technical failures can occur (internet, broker, system crashes)
- User is responsible for all trading decisions and outcomes

## 10. Success Metrics

**MVP Success (Phase 1 - 3 months):**
- System stability: 99%+ uptime
- Win rate: > 50%
- Profit factor: > 1.2
- Maximum drawdown: < 8%
- Average trades per day: 1-3
- Zero critical errors causing data loss

**Phase 2 Success (Months 4-6):**
- Win rate: > 55%
- Profit factor: > 1.5
- Maximum drawdown: < 10%
- AI confirmation improving results by 5%+
- Support all trading styles and risk profiles
- Telegram bot fully functional

**Phase 3 Success (Months 7-12):**
- Win rate: > 60%
- Profit factor: > 2.0
- Maximum drawdown: < 10%
- Multi-asset trading operational
- 100+ robots working in harmony
- Self-learning optimization showing improvements
- Ready for live trading with real capital

**Long-term Success (Year 1+):**
- Consistent monthly profitability
- Sharpe ratio > 1.5
- Maximum drawdown < 15%
- System handles various market conditions
- Minimal manual intervention required
- Scalable to larger account sizes


### 3.7 Advanced Trading Features (6 Robots)

#### US-28: Multi-Account Manager Bot
**As a** professional trader  
**I want** to manage multiple MT5 accounts simultaneously  
**So that** I can diversify across brokers or account types

**Acceptance Criteria:**
- AC-28.1: System supports multiple MT5 accounts (demo and live)
- AC-28.2: Each account has independent configuration
- AC-28.3: Accounts can be enabled/disabled individually
- AC-28.4: System tracks performance per account
- AC-28.5: Copy trading between accounts is supported
- AC-28.6: Master-slave account relationship configurable
- AC-28.7: Copy ratio adjustable (50%, 100%, 200%)

#### US-29: Multi-Symbol Analysis Bot
**As a** diversified trader  
**I want** to analyze multiple symbols simultaneously  
**So that** I can find the best trading opportunities

**Acceptance Criteria:**
- AC-29.1: System supports configurable symbol list
- AC-29.2: Primary symbol is XAUUSD, additional symbols optional
- AC-29.3: Correlation analysis between symbols
- AC-29.4: System tracks USD index, Oil, Treasury yields
- AC-29.5: Correlation alerts when threshold exceeded
- AC-29.6: Symbol-specific strategy parameters
- AC-29.7: Performance comparison across symbols

#### US-30: Advanced Strategy Bot (Martingale/Grid)
**As an** aggressive trader  
**I want** optional martingale and grid trading strategies  
**So that** I can recover from losses (with full risk awareness)

**Acceptance Criteria:**
- AC-30.1: Martingale strategy is disabled by default (high risk)
- AC-30.2: Configurable multiplier (2x, 3x) and max levels
- AC-30.3: Grid trading with configurable grid size and levels
- AC-30.4: Clear warnings about risk in configuration
- AC-30.5: Maximum exposure limits enforced
- AC-30.6: Strategy can be enabled/disabled per symbol
- AC-30.7: Performance tracked separately for advanced strategies

#### US-31: News Trading Manager Bot
**As a** news trader  
**I want** configurable news trading behavior  
**So that** I can choose to pause, continue, or trade aggressively during news

**Acceptance Criteria:**
- AC-31.1: Three modes: pause, continue, aggressive
- AC-31.2: Configurable pause duration before/after news
- AC-31.3: High-impact news filter (only pause for major events)
- AC-31.4: Economic calendar integration
- AC-31.5: News events logged with impact on trades
- AC-31.6: Automatic resume after pause period
- AC-31.7: Manual override via Telegram

#### US-32: Hedging Manager Bot
**As a** risk-averse trader  
**I want** optional position hedging  
**So that** I can protect against adverse moves

**Acceptance Criteria:**
- AC-32.1: Hedging disabled by default
- AC-32.2: Configurable hedge ratio (50%, 100%)
- AC-32.3: Automatic hedge trigger conditions
- AC-32.4: Manual hedge via Telegram command
- AC-32.5: Hedge positions tracked separately
- AC-32.6: Net exposure calculated and displayed
- AC-32.7: Hedge exit strategy configurable

#### US-33: Copy Trading Bot
**As a** portfolio manager  
**I want** to copy trades from master to slave accounts  
**So that** I can scale my strategy across multiple accounts

**Acceptance Criteria:**
- AC-33.1: Master account generates signals
- AC-33.2: Slave accounts copy trades automatically
- AC-33.3: Configurable copy ratio per slave account
- AC-33.4: Delay between master and slave execution < 1 second
- AC-33.5: Failed copies are logged and alerted
- AC-33.6: Individual slave accounts can be paused
- AC-33.7: Performance tracked per account

### 3.8 Safety & Control (4 Robots)

#### US-34: Trading Limits Enforcer Bot
**As a** risk manager  
**I want** configurable trading limits  
**So that** I prevent overtrading and excessive risk

**Acceptance Criteria:**
- AC-34.1: Maximum trades per day limit enforced
- AC-34.2: Maximum trades per hour limit enforced
- AC-34.3: Minimum time between trades enforced
- AC-34.4: Limits configurable per trading style
- AC-34.5: Limit violations logged and alerted
- AC-34.6: Trading pauses when limits reached
- AC-34.7: Automatic resume at next period

#### US-35: Loss Protection Bot
**As a** capital protector  
**I want** automatic trading pause after consecutive losses  
**So that** I avoid emotional revenge trading

**Acceptance Criteria:**
- AC-35.1: Configurable consecutive loss threshold (3, 5, 7)
- AC-35.2: Configurable pause duration (30, 60, 120 minutes)
- AC-35.3: Automatic resume after pause period
- AC-35.4: Manual resume via Telegram command
- AC-35.5: Loss streak notifications sent
- AC-35.6: System analyzes losing trades during pause
- AC-35.7: Suggestions provided for strategy adjustment

#### US-36: Kill Switch Bot
**As a** trader  
**I want** an emergency kill switch  
**So that** I can immediately stop all trading

**Acceptance Criteria:**
- AC-36.1: Telegram command /killswitch closes all positions
- AC-36.2: Automatic trigger on max drawdown exceeded
- AC-36.3: Automatic trigger on critical system error
- AC-36.4: All open positions closed at market price
- AC-36.5: Trading paused indefinitely until manual resume
- AC-36.6: Kill switch activation logged with reason
- AC-36.7: Notification sent immediately on activation

#### US-37: Circuit Breaker Bot
**As a** risk manager  
**I want** multi-timeframe loss limits  
**So that** I protect capital over different periods

**Acceptance Criteria:**
- AC-37.1: Daily loss limit enforced (configurable %)
- AC-37.2: Weekly loss limit enforced (configurable %)
- AC-37.3: Monthly loss limit enforced (configurable %)
- AC-37.4: Trading pauses when any limit reached
- AC-37.5: Limits reset at period boundaries
- AC-37.6: Warning alerts at 50%, 75%, 90% of limit
- AC-37.7: Manual override requires confirmation

### 3.9 Reporting & Analytics (3 Robots)

#### US-38: PDF Report Generator Bot
**As a** trader  
**I want** automated PDF reports  
**So that** I can review performance professionally

**Acceptance Criteria:**
- AC-38.1: Daily, weekly, monthly reports generated
- AC-38.2: Reports include performance charts
- AC-38.3: Reports include trade list with details
- AC-38.4: Reports include key metrics (win rate, profit factor, etc.)
- AC-38.5: Reports sent via Telegram or email
- AC-38.6: Report template customizable
- AC-38.7: Historical reports archived

#### US-39: Performance Analytics Bot
**As an** analyst  
**I want** detailed performance breakdowns  
**So that** I can identify patterns and optimize

**Acceptance Criteria:**
- AC-39.1: Performance tracked by time of day
- AC-39.2: Performance tracked by day of week
- AC-39.3: Performance tracked by market session (Asian/London/NY)
- AC-39.4: Performance tracked by strategy type
- AC-39.5: Best/worst performing periods identified
- AC-39.6: Statistical significance calculated
- AC-39.7: Recommendations generated for optimization

#### US-40: Cost Analysis Bot
**As a** trader  
**I want** detailed cost tracking  
**So that** I understand true profitability

**Acceptance Criteria:**
- AC-40.1: Slippage tracked per trade
- AC-40.2: Spread costs calculated per trade
- AC-40.3: Commission tracked per trade
- AC-40.4: Swap/rollover costs tracked
- AC-40.5: Total costs summarized daily/weekly/monthly
- AC-40.6: Cost as percentage of profit calculated
- AC-40.7: High-cost trades flagged for review

### 3.10 Web Dashboard & Manual Control (2 Robots)

#### US-41: Web Dashboard Bot
**As a** trader  
**I want** a web-based monitoring dashboard  
**So that** I can view system status from any device

**Acceptance Criteria:**
- AC-41.1: Dashboard accessible via web browser
- AC-41.2: Real-time trade display
- AC-41.3: Performance charts and metrics
- AC-41.4: System health indicators
- AC-41.5: Password protected access
- AC-41.6: IP whitelist for security
- AC-41.7: Mobile-responsive design
- AC-41.8: Auto-refresh every 5 seconds

#### US-42: Manual Override Bot
**As a** trader  
**I want** manual control via Telegram  
**So that** I can intervene when needed

**Acceptance Criteria:**
- AC-42.1: /close_all command closes all positions
- AC-42.2: /close_trade [id] closes specific trade
- AC-42.3: /pause_trading pauses system
- AC-42.4: /resume_trading resumes system
- AC-42.5: /force_entry [symbol] [direction] forces manual entry
- AC-42.6: /status shows current system state
- AC-42.7: /stats shows performance summary
- AC-42.8: All manual actions logged and confirmed

### 3.11 Custom Strategy Support (2 Robots)

#### US-43: Custom Strategy Loader Bot
**As a** strategy developer  
**I want** to backtest custom strategies  
**So that** I can test new ideas

**Acceptance Criteria:**
- AC-43.1: Custom strategies loaded from directory
- AC-43.2: Strategy interface standardized
- AC-43.3: Hot reload without system restart
- AC-43.4: Strategy validation before loading
- AC-43.5: Multiple strategies can run simultaneously
- AC-43.6: Strategy performance tracked separately
- AC-43.7: Best performing strategy auto-selected

#### US-44: Strategy Backtesting Bot
**As a** strategy developer  
**I want** comprehensive backtesting capabilities  
**So that** I can validate strategies before live trading

**Acceptance Criteria:**
- AC-44.1: Backtest on historical data (2+ years)
- AC-44.2: Walk-forward optimization
- AC-44.3: Monte Carlo simulation
- AC-44.4: Out-of-sample validation
- AC-44.5: Detailed backtest report generated
- AC-44.6: Overfitting detection
- AC-44.7: Parameter sensitivity analysis
