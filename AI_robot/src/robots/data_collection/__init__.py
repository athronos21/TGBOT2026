"""Data collection robot swarm"""

from .price_bot import PriceBot
from .tick_bot import TickBot
from .mtf_bot import MTFAggregatorBot
from .volatility_bot import VolatilityScannerBot
from .news_bot import NewsEventsBot
from .sentiment_bot import SentimentBot

__all__ = ["PriceBot", "TickBot", "MTFAggregatorBot", "VolatilityScannerBot", "NewsEventsBot", "SentimentBot"]
