import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.robots.analysis.fvg_bot import FVGBot
from src.robots.data_collection.price_bot import OHLCData
from src.core.robot import RobotInfo

@pytest.fixture
def robot_info():
    return RobotInfo(
        id="fvg_bot_1",
        name="Fair Value Gap Scanner",
        swarm="analysis"
    )

@pytest.fixture
def base_config():
    return {}

@pytest.fixture
def mock_message_bus():
    bus = AsyncMock()
    return bus

@pytest.fixture
def mock_mongo():
    return MagicMock()

@pytest.mark.asyncio
async def test_fvg_generation_and_mitigation(robot_info, base_config, mock_message_bus, mock_mongo):
    bot = FVGBot(robot_info, base_config, message_bus=mock_message_bus, mongo_manager=mock_mongo)
    await bot.initialize()
    
    # --- Bullish FVG Setup ---
    # To form a bullish FVG: C1 High < C3 Low.
    c1 = OHLCData("XAUUSD", "M5", datetime.now(), 100, 110, 95, 108, 100)
    c2 = OHLCData("XAUUSD", "M5", datetime.now(), 110, 150, 105, 145, 100) # Big displacement candle
    c3 = OHLCData("XAUUSD", "M5", datetime.now(), 145, 160, 120, 155, 100)
    
    # C1 High = 110
    # C3 Low = 120
    # GAP = [110, 120] -> Bullish FVG
    
    await bot._process_candle(c1)
    await bot._process_candle(c2)
    assert len(bot._active_fvgs) == 0
    assert mock_message_bus.send_message.call_count == 0
    
    await bot._process_candle(c3)
    assert len(bot._active_fvgs) == 1
    assert bot._active_fvgs[0].fvg_type == "BULLISH"
    assert bot._active_fvgs[0].top == 120
    assert bot._active_fvgs[0].bottom == 110
    assert not bot._active_fvgs[0].mitigated
    
    assert mock_message_bus.send_message.call_count == 1
    call_args = mock_message_bus.send_message.call_args[0]
    assert call_args[0] == "fvg_formed"
    assert call_args[1]["fvg_type"] == "BULLISH"

    # --- Mitigation of the Bullish FVG ---
    # Mitigation happens when price taps DOWN and spans the block.
    # Fully mitigated: candle.low <= 110
    c4 = OHLCData("XAUUSD", "M5", datetime.now(), 155, 160, 115, 120, 100) # Only partial drop
    
    await bot._process_candle(c4)
    # Still 1 unmitigated FVG because low (115) didn't cross bottom (110)
    assert len(bot._active_fvgs) == 1
    # Note: 115 is < 120, so it tapped it, but our logic requires it to fully clear <= 110
    
    c5 = OHLCData("XAUUSD", "M5", datetime.now(), 120, 125, 105, 122, 100) # Fully breaks through block (low=105 <= 110)
    await bot._process_candle(c5)
    
    # FVG is now mitigated and purged
    assert len(bot._active_fvgs) == 0
    assert mock_message_bus.send_message.call_count == 2
    call_args_mit = mock_message_bus.send_message.call_args[0]
    assert call_args_mit[0] == "fvg_mitigated"


@pytest.mark.asyncio
async def test_bearish_fvg_generation(robot_info, base_config, mock_message_bus, mock_mongo):
    bot = FVGBot(robot_info, base_config, message_bus=mock_message_bus, mongo_manager=mock_mongo)
    
    # --- Bearish FVG Setup ---
    # C1 Low (150) > C3 High (140). The gap is between 140 and 150.
    c1 = OHLCData("EURUSD", "M15", datetime.now(), 160, 165, 150, 155, 100)
    c2 = OHLCData("EURUSD", "M15", datetime.now(), 155, 158, 120, 125, 100)
    c3 = OHLCData("EURUSD", "M15", datetime.now(), 125, 140, 115, 130, 100)
    
    await bot._process_candle(c1)
    await bot._process_candle(c2)
    await bot._process_candle(c3)
    
    assert len(bot._active_fvgs) == 1
    assert bot._active_fvgs[0].fvg_type == "BEARISH"
    assert bot._active_fvgs[0].top == 150
    assert bot._active_fvgs[0].bottom == 140
    
    assert mock_message_bus.send_message.call_count == 1
