import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.robots.analysis.imbalance_bot import ImbalanceBot
from src.robots.data_collection.price_bot import OHLCData
from src.core.robot import RobotInfo

@pytest.fixture
def robot_info():
    return RobotInfo(
        id="imbalance_bot_1",
        name="Imbalance Analyser",
        swarm="analysis"
    )

@pytest.fixture
def base_config():
    # Accelerate evaluation limit for testing by using smaller period requirements
    return {
        "history_period": 4, 
        "size_multiplier": 2.0,
        "vol_multiplier": 1.5
    }

@pytest.fixture
def mock_message_bus():
    bus = AsyncMock()
    return bus

@pytest.fixture
def mock_mongo():
    return MagicMock()

@pytest.mark.asyncio
async def test_imbalance_logic(robot_info, base_config, mock_message_bus, mock_mongo):
    bot = ImbalanceBot(robot_info, base_config, message_bus=mock_message_bus, mongo_manager=mock_mongo)
    await bot.initialize()
    
    # Send 3 normal, tight-ranging candles to establish a baseline.
    # Body Size: 5. Volume: 100.
    c1 = OHLCData("XAUUSD", "M5", datetime.now(), 1000, 1010, 995, 1005, 100)
    c2 = OHLCData("XAUUSD", "M5", datetime.now(), 1005, 1015, 1000, 1010, 100)
    c3 = OHLCData("XAUUSD", "M5", datetime.now(), 1010, 1020, 1005, 1005, 100) # body is 5
    
    await bot._process_candle(c1)
    await bot._process_candle(c2)
    # At this point, length=2. `history_period=4`, half=2, so it CAN evaluate the 3rd candle against the first 2.
    # Averages: Body=5, Vol=100. Thresholds: Body > 10, Vol > 150
    await bot._process_candle(c3)
    
    assert mock_message_bus.send_message.call_count == 0
    
    # Now send an explosive candle
    # Imbalance: Body Size 20, Volume: 200
    # Meets thresholds!
    c4 = OHLCData("XAUUSD", "M5", datetime.now(), 1005, 1040, 1000, 1025, 200)
    await bot._process_candle(c4)
    
    assert mock_message_bus.send_message.call_count == 1
    call_args = mock_message_bus.send_message.call_args[0]
    
    payload = call_args[1]
    assert call_args[0] == "imbalance_detected"
    assert payload["imbalance_type"] == "BULLISH"
    assert payload["start_price"] == 1005
    assert payload["end_price"] == 1025
    assert payload["volume"] == 200

@pytest.mark.asyncio
async def test_bearish_imbalance(robot_info, base_config, mock_message_bus, mock_mongo):
    bot = ImbalanceBot(robot_info, base_config, message_bus=mock_message_bus, mongo_manager=mock_mongo)
    await bot.initialize()
    
    c1 = OHLCData("EURUSD", "H1", datetime.now(), 1.1000, 1.1010, 1.0990, 1.0995, 1000) # body 0.0005
    c2 = OHLCData("EURUSD", "H1", datetime.now(), 1.0995, 1.1005, 1.0985, 1.0990, 1000) # body 0.0005
    # average size = 0.0005, volume = 1000
    
    await bot._process_candle(c1)
    await bot._process_candle(c2)
    
    # Bearish plunge 
    # Body: 1.0990 to 1.0900 (0.0090 size)
    # Volume: 3000
    c3 = OHLCData("EURUSD", "H1", datetime.now(), 1.0990, 1.0995, 1.0850, 1.0900, 3000)
    
    await bot._process_candle(c3)
    
    assert mock_message_bus.send_message.call_count == 1
    payload = mock_message_bus.send_message.call_args[0][1]
    assert payload["imbalance_type"] == "BEARISH"
