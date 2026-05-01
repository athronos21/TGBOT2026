import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.robots.data_collection.sentiment_bot import SentimentBot
from src.core.robot import RobotInfo


@pytest.fixture
def robot_info():
    return RobotInfo(
        id="sentiment_bot_1",
        name="Sentiment Scanner",
        swarm="data_collection"
    )

@pytest.fixture
def base_config():
    return {
        "symbols": ["XAUUSD", "EURUSD"],
        "twitter_api": "mock://twitter",
        "reddit_api": "mock://reddit"
    }

@pytest.fixture
def mock_message_bus():
    bus = AsyncMock()
    return bus

@pytest.fixture
def mock_mongo():
    return MagicMock()

def test_sentiment_scoring_algorithm(robot_info, base_config):
    bot = SentimentBot(robot_info, base_config)
    
    # 1. Very Bearish Test
    texts_bearish = [
        "Gold is going to crash hard, plummeting below support.",
        "I am bearish, sell everything!"
    ]
    # words: crash, plummet, bearish, sell (4 bear) vs support (1 bull) -> 1 - 4 = -3. total = 5. ratio = -3/5 = -0.6 -> -60.0 score
    score1 = bot._calculate_sentiment_score(texts_bearish)
    assert score1 < 0
    assert score1 == -60.0
    
    # 2. Very Bullish Test
    texts_bullish = [
        "Massive rally ahead! Going long, huge breakout.",
        "Buy buy buy! Bullish surge!"
    ]
    # words: rally, long, breakout, buy, bullish, surge (6 bull). no bear. ratio = 1.0 -> 100.0 score
    score2 = bot._calculate_sentiment_score(texts_bullish)
    assert score2 > 0
    assert score2 == 100.0
    
    # 3. Neutral Test
    texts_neutral = [
        "Nothing is happening today, sideways market."
    ]
    score3 = bot._calculate_sentiment_score(texts_neutral)
    assert score3 == 0.0
    
    # 4. Mixed Test
    texts_mixed = [
        "It might rally up, or it might crash down. Sell or buy?"
    ]
    # rally, up, buy (3 bull) - crash, down, sell (3 bear). total 6. ratio 0.0
    score4 = bot._calculate_sentiment_score(texts_mixed)
    assert score4 == 0.0

@pytest.mark.asyncio
async def test_sentiment_evaluation_flow(robot_info, base_config, mock_message_bus, mock_mongo):
    bot = SentimentBot(robot_info, base_config, message_bus=mock_message_bus, mongo_manager=mock_mongo)
    
    # Evaluate XAUUSD (which returns bullish mocks)
    await bot._evaluate_sentiment_for_symbol("XAUUSD")
    
    # Should have sent message
    assert mock_message_bus.send_message.call_count == 1
    call_args_gold = mock_message_bus.send_message.call_args[0]
    assert call_args_gold[0] == "sentiment_update"
    
    payload_gold = call_args_gold[1]
    assert payload_gold["symbol"] == "XAUUSD"
    assert payload_gold["score"] > 0  # Gold mock is heavily bullish
    assert payload_gold["volume"] == 6  # 3 from twitter mock, 3 from reddit mock
    
    # Because score > 60 is true for the Gold mock texts, mongo should have logged
    assert mock_mongo.insert_log.call_count == 1
    
    # Evaluate EURUSD (which returns bearish mocks)
    await bot._evaluate_sentiment_for_symbol("EURUSD")
    
    assert mock_message_bus.send_message.call_count == 2
    call_args_eur = mock_message_bus.send_message.call_args[0]
    payload_eur = call_args_eur[1]
    assert payload_eur["symbol"] == "EURUSD"
    assert payload_eur["score"] < 0
    
    # Mongo should log again because it is highly bearish (< -60)
    assert mock_mongo.insert_log.call_count == 2
