import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.robots.data_collection.news_bot import NewsEventsBot, NewsEvent
from src.core.robot import RobotInfo


@pytest.fixture
def robot_info():
    return RobotInfo(
        id="news_bot_1",
        name="News Tracker",
        swarm="data_collection"
    )

@pytest.fixture
def base_config():
    return {
        "calendar_api_url": "mock",
        "target_currencies": ["USD", "EUR"],
        "high_impact_only": True,
        "warning_minutes": 15
    }

@pytest.fixture
def mock_message_bus():
    bus = AsyncMock()
    return bus

@pytest.fixture
def mock_mongo():
    return MagicMock()

@pytest.mark.asyncio
async def test_news_bot_parsing_and_filters(robot_info, base_config, mock_message_bus, mock_mongo):
    bot = NewsEventsBot(robot_info, base_config, message_bus=mock_message_bus, mongo_manager=mock_mongo)
    
    raw_mock_events = [
        {
            "id": "e1",
            "title": "Fed Interest Rate Decision",
            "impact": "HIGH",
            "currency": "USD",
            "timestamp": datetime.now().isoformat()
        },
        {
            "id": "e2",
            "title": "Minor Euro Report",
            "impact": "LOW",
            "currency": "EUR",
            "timestamp": datetime.now().isoformat()
        },
        {
            "id": "e3",
            "title": "Bank of Japan Update",
            "impact": "HIGH",
            "currency": "JPY",  # Not in target_currencies
            "timestamp": datetime.now().isoformat()
        }
    ]
    
    bot._parse_events(raw_mock_events)
    
    # Only e1 should survive the filter (USD, HIGH)
    assert len(bot._upcoming_events) == 1
    assert bot._upcoming_events[0].id == "e1"

@pytest.mark.asyncio
async def test_news_bot_alert_countdown(robot_info, base_config, mock_message_bus, mock_mongo):
    bot = NewsEventsBot(robot_info, base_config, message_bus=mock_message_bus, mongo_manager=mock_mongo)
    
    now = datetime.now()
    
    # Event 1 is exactly 10 minutes away (within 15m threshold)
    e1 = NewsEvent("e1", "NFP", "HIGH", "USD", now + timedelta(minutes=10))
    # Event 2 is 30 minutes away (outside threshold)
    e2 = NewsEvent("e2", "CPI", "HIGH", "USD", now + timedelta(minutes=30))
    # Event 3 is in the past (handled edge case naturally if negative threshold applied or just ignored)
    e3 = NewsEvent("e3", "Old News", "HIGH", "USD", now - timedelta(minutes=5))
    
    bot._upcoming_events = [e1, e2, e3]
    
    await bot._evaluate_event_countdowns()
    
    # Event 1 should have dispatched
    assert mock_message_bus.send_message.call_count == 1
    call_args = mock_message_bus.send_message.call_args[0]
    
    assert call_args[0] == "news_alert"
    assert call_args[1]["level"] == "CRITICAL"
    assert call_args[1]["event"]["id"] == "e1"
    
    # Event 1's ID should be cached to prevent duplicate spam
    assert "e1" in bot._alerted_event_ids
    
    # Run loop again, it shouldn't trigger again for e1
    await bot._evaluate_event_countdowns()
    assert mock_message_bus.send_message.call_count == 1  # Still 1
