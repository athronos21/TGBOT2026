import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.robots.data_collection.volatility_bot import VolatilityScannerBot
from src.robots.data_collection.price_bot import OHLCData
from src.core.robot import RobotInfo


@pytest.fixture
def robot_info():
    return RobotInfo(
        id="volatility_bot_1",
        name="Volatility Scanner",
        swarm="data_collection"
    )

@pytest.fixture
def base_config():
    return {
        "atr_period": 3,
        "bb_period": 4,
        "bb_std_dev": 2.0
    }

@pytest.fixture
def mock_message_bus():
    bus = AsyncMock()
    return bus

@pytest.fixture
def mock_mongo():
    return MagicMock()

@pytest.mark.asyncio
async def test_volatility_metrics_generation(robot_info, base_config, mock_message_bus, mock_mongo):
    bot = VolatilityScannerBot(robot_info, base_config, message_bus=mock_message_bus, mongo_manager=mock_mongo)
    
    await bot.initialize()
    
    # We set atr_period=3, bb_period=4.
    # Therefore, 4 candles are needed before BB is calculated.
    
    c1 = OHLCData("XAUUSD", "M1", datetime.now(), 10.0, 15.0, 8.0, 12.0, 100)
    c2 = OHLCData("XAUUSD", "M1", datetime.now(), 12.0, 20.0, 10.0, 18.0, 100)
    c3 = OHLCData("XAUUSD", "M1", datetime.now(), 18.0, 25.0, 15.0, 24.0, 100)
    c4 = OHLCData("XAUUSD", "M1", datetime.now(), 24.0, 30.0, 20.0, 28.0, 100)
    
    await bot._process_candle(c1)
    await bot._process_candle(c2)
    mock_message_bus.send_message.assert_not_called()  # Buffer only has 2 items.
    
    await bot._process_candle(c3)
    # At 3 items, ATR triggers (because atr_period=3). but BB not yet.
    assert mock_message_bus.send_message.call_count == 1
    call_args = mock_message_bus.send_message.call_args[0]
    assert call_args[0] == "volatility_update"
    assert "atr" in call_args[1]["metrics"]
    assert "bb_upper" not in call_args[1]["metrics"]

    # Now provide the 4th item. Both ATR and BB should trigger.
    await bot._process_candle(c4)
    # The 4th item triggers another volatility update.
    assert mock_message_bus.send_message.call_count == 2
    call_args_4 = mock_message_bus.send_message.call_args[0]
    metrics = call_args_4[1]["metrics"]
    
    assert "atr" in metrics
    assert "bb_upper" in metrics
    assert "bb_mid" in metrics
    assert "bb_lower" in metrics

    # Test Bollinger Band Math explicitly
    # closes: 12.0, 18.0, 24.0, 28.0
    # SMA = (12+18+24+28)/4 = 82/4 = 20.5
    assert metrics["bb_mid"] == 20.5
    # Variance = ((-8.5)^2 + (-2.5)^2 + (3.5)^2 + (7.5)^2) / 4 
    # = (72.25 + 6.25 + 12.25 + 56.25) / 4 = 147 / 4 = 36.75
    # StdDev = sqrt(36.75) ~ 6.06217
    # Upper = 20.5 + 2 * std_dev ~ 32.62
    
    # We just ensure it's calculated and standard upper > mid > lower
    assert metrics["bb_upper"] > metrics["bb_mid"] > metrics["bb_lower"]
    
@pytest.mark.asyncio
async def test_volatility_alerts(robot_info, base_config, mock_message_bus, mock_mongo):
    bot = VolatilityScannerBot(robot_info, base_config, message_bus=mock_message_bus, mongo_manager=mock_mongo)
    
    # Send 4 standard candles
    c1 = OHLCData("XAUUSD", "M1", datetime.now(), 10.0, 15.0, 8.0, 12.0, 100)
    c2 = OHLCData("XAUUSD", "M1", datetime.now(), 12.0, 20.0, 10.0, 18.0, 100)
    c3 = OHLCData("XAUUSD", "M1", datetime.now(), 18.0, 25.0, 15.0, 24.0, 100)
    c4 = OHLCData("XAUUSD", "M1", datetime.now(), 24.0, 30.0, 20.0, 28.0, 100)
    
    await bot._process_candle(c1)
    await bot._process_candle(c2)
    await bot._process_candle(c3)
    await bot._process_candle(c4)
    # bb_upper is around 32.62.
    
    # Now send an explosive candle that closes completely outside the upper band
    c5 = OHLCData("XAUUSD", "M1", datetime.now(), 28.0, 60.0, 28.0, 50.0, 100)
    await bot._process_candle(c5)
    
    # We should have seen a volatility_alert dispatched because c5 closed at 50, exceeding the SMA+2SD upper band.
    # The internal queue processes it, evaluates it against the newly established band.
    
    alert_triggered = False
    for call in mock_message_bus.send_message.mock_calls:
        if call[1][0] == 'volatility_alert':
            payload = call[1][1]
            if 'PRICE_ABOVE_UPPER_BB' in payload['alerts']:
                alert_triggered = True
                
    assert alert_triggered is True
    assert mock_mongo.insert_log.call_count > 0
