import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.robots.data_collection.tick_bot import TickBot, TickData
from src.core.robot import RobotInfo


@pytest.fixture
def mock_mt5():
    mt5 = AsyncMock()
    # Mock tick data response
    mock_tick = MagicMock()
    mock_tick.bid = 1950.5
    mock_tick.ask = 1951.0
    mock_tick.volume = 100
    mock_tick.time = datetime(2026, 4, 8, 14, 0, 0)
    mt5.get_tick.return_value = mock_tick
    return mt5


@pytest.fixture
def mock_postgres():
    postgres = AsyncMock()
    return postgres


@pytest.fixture
def mock_mongo():
    mongo = MagicMock()
    return mongo


@pytest.fixture
def mock_message_bus():
    bus = AsyncMock()
    return bus


@pytest.fixture
def robot_info():
    return RobotInfo(
        id="tick_bot_01",
        name="Tick Collector",
        swarm="data_collection"
    )


@pytest.fixture
def base_config():
    return {
        "symbols": ["XAUUSD"],
        "tick_interval": 0.01,
        "max_ticks_per_batch": 5
    }


@pytest.mark.asyncio
async def test_tick_bot_initialization(robot_info, base_config, mock_postgres, mock_mongo):
    bot = TickBot(
        robot_info=robot_info,
        config=base_config,
        postgres_manager=mock_postgres,
        mongo_manager=mock_mongo
    )
    
    assert bot.symbols == ["XAUUSD"]
    assert bot.tick_interval == 0.01
    assert bot.max_ticks_per_batch == 5
    
    success = await bot.initialize()
    assert success is True
    
    mock_postgres.create_market_data_table.assert_called_once()
    mock_mongo.create_logs_collection.assert_called_once()
    mock_mongo.create_events_collection.assert_called_once()


@pytest.mark.asyncio
async def test_tick_bot_fetch_and_validate(robot_info, base_config, mock_mt5):
    bot = TickBot(
        robot_info=robot_info,
        config=base_config,
        mt5_connection=mock_mt5
    )
    
    tick = await bot._fetch_tick_data("XAUUSD")
    assert tick is not None
    assert tick.symbol == "XAUUSD"
    assert tick.bid == 1950.5
    assert tick.ask == 1951.0
    
    assert bot._validate_tick_data(tick) is True
    
    # Test invalid data
    invalid_tick = TickData(
        symbol="XAUUSD",
        bid=1952.0,
        ask=1951.0,  # bid > ask is invalid
        volume=10,
        timestamp=datetime.now()
    )
    assert bot._validate_tick_data(invalid_tick) is False


@pytest.mark.asyncio
async def test_tick_bot_buffer_flush(robot_info, base_config, mock_mt5, mock_postgres, mock_message_bus):
    # Set small batch limit
    config = base_config.copy()
    config["max_ticks_per_batch"] = 2
    
    bot = TickBot(
        robot_info=robot_info,
        config=config,
        message_bus=mock_message_bus,
        mt5_connection=mock_mt5,
        postgres_manager=mock_postgres
    )
    
    # Manually test tick processing
    tick1 = TickData("XAUUSD", 1000.0, 1001.0, 10, datetime.now())
    tick2 = TickData("XAUUSD", 1001.0, 1002.0, 12, datetime.now())
    
    await bot._process_tick_data(tick1)
    # Shouldn't have flushed yet, length should be 1
    assert len(bot._tick_buffer) == 1
    mock_postgres.insert_market_data.assert_not_called()
    
    await bot._process_tick_data(tick2)
    # Should have triggered flush because max_ticks_per_batch == 2
    assert len(bot._tick_buffer) == 0
    mock_postgres.insert_market_data.assert_called_once()
    
    # Message bus should have been called twice
    assert mock_message_bus.publish.call_count == 2
