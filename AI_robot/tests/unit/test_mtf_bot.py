import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.robots.data_collection.mtf_bot import MTFAggregatorBot
from src.robots.data_collection.tick_bot import TickData
from src.robots.data_collection.price_bot import OHLCData
from src.core.robot import RobotInfo


@pytest.fixture
def robot_info():
    return RobotInfo(
        id="mtf_bot_01",
        name="MTF Aggregator",
        swarm="data_collection"
    )

@pytest.fixture
def mock_postgres():
    return AsyncMock()

@pytest.fixture
def mock_mongo():
    return MagicMock()

@pytest.fixture
def mock_message_bus():
    bus = AsyncMock()
    # Stubbing subscribe to not block
    bus.subscribe.return_value = None
    return bus

@pytest.fixture
def base_config():
    return {
        "symbols": ["XAUUSD"],
        "timeframes": ["M1"]
    }

@pytest.mark.asyncio
async def test_mtf_bot_initialization(robot_info, base_config, mock_postgres, mock_mongo, mock_message_bus):
    bot = MTFAggregatorBot(
        robot_info, 
        base_config, 
        message_bus=mock_message_bus,
        postgres_manager=mock_postgres,
        mongo_manager=mock_mongo
    )

    assert bot.symbols == ["XAUUSD"]
    assert bot.timeframes == ["M1"]
    
    success = await bot.initialize()
    assert success is True
    mock_postgres.create_market_data_table.assert_called_once()
    
def test_get_period_start(robot_info, base_config):
    bot = MTFAggregatorBot(robot_info, base_config)
    
    dt = datetime(2026, 4, 8, 14, 13, 45)
    
    m1_start = bot._get_period_start(dt, "M1")
    assert m1_start == datetime(2026, 4, 8, 14, 13, 0)
    
    m5_start = bot._get_period_start(dt, "M5")
    assert m5_start == datetime(2026, 4, 8, 14, 10, 0)
    
    m15_start = bot._get_period_start(dt, "M15")
    assert m15_start == datetime(2026, 4, 8, 14, 0, 0)
    
    h1_start = bot._get_period_start(dt, "H1")
    assert h1_start == datetime(2026, 4, 8, 14, 0, 0)

@pytest.mark.asyncio
async def test_tick_to_candle_aggregation(robot_info, base_config, mock_postgres, mock_message_bus):
    bot = MTFAggregatorBot(
        robot_info, 
        base_config, 
        message_bus=mock_message_bus,
        postgres_manager=mock_postgres
    )
    
    # Send First Tick at 14:05:10
    t1 = TickData("XAUUSD", bid=1950.0, ask=1950.5, volume=10, timestamp=datetime(2026, 4, 8, 14, 5, 10))
    await bot._process_tick(t1)
    
    active_m1 = bot._active_candles["XAUUSD"]["M1"]
    assert active_m1 is not None
    assert active_m1.open == 1950.0
    assert active_m1.high == 1950.0
    assert active_m1.low == 1950.0
    assert active_m1.close == 1950.0
    assert active_m1.volume == 10
    
    # Mock bus shouldn't have dispatched yet
    mock_message_bus.send_message.assert_not_called()
    
    # Send Second Tick inside the same M1 candle (14:05:40) with higher price
    t2 = TickData("XAUUSD", bid=1952.0, ask=1952.5, volume=5, timestamp=datetime(2026, 4, 8, 14, 5, 40))
    await bot._process_tick(t2)
    
    active_m1 = bot._active_candles["XAUUSD"]["M1"]
    assert active_m1.open == 1950.0 # Open is unchanged
    assert active_m1.high == 1952.0 # High increased
    assert active_m1.low == 1950.0 # Low unchanged
    assert active_m1.close == 1952.0 # Close updated
    assert active_m1.volume == 15 # Vol accumulated
    
    mock_message_bus.send_message.assert_not_called()
    
    # Send Third Tick crossing the M1 boundary (14:06:05) -> causes rollover
    t3 = TickData("XAUUSD", bid=1948.0, ask=1948.5, volume=20, timestamp=datetime(2026, 4, 8, 14, 6, 5))
    await bot._process_tick(t3)
    
    # The previous candle must have been finalized and dispatched
    assert mock_postgres.insert_market_data.call_count == 1
    
    # A new candle is generated exactly on the boundary
    new_active_m1 = bot._active_candles["XAUUSD"]["M1"]
    assert new_active_m1.open == 1948.0
    assert new_active_m1.close == 1948.0
    assert new_active_m1.timestamp == datetime(2026, 4, 8, 14, 6, 0)
    
@pytest.mark.asyncio
async def test_validate_candle(robot_info, base_config):
    bot = MTFAggregatorBot(robot_info, base_config)
    
    valid_candle = OHLCData("XAUUSD", "M1", datetime.now(), 100, 105, 95, 102, 100)
    assert bot._validate_candle(valid_candle) is True
    
    invalid_candle_high_low = OHLCData("XAUUSD", "M1", datetime.now(), 100, 90, 105, 102, 100)
    assert bot._validate_candle(invalid_candle_high_low) is False

    invalid_candle_close = OHLCData("XAUUSD", "M1", datetime.now(), 100, 105, 95, 106, 100)
    assert bot._validate_candle(invalid_candle_close) is False
