"""
Sentiment Bot - Data Collection Robot

Aggregates qualitative social media datastreams (Twitter, Reddit) 
and parses string patterns using natural language processing maps to 
derive a unified market sentiment score (-100 Bearish to +100 Bullish).
"""

import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import urllib.request
from urllib.error import URLError
from concurrent.futures import ThreadPoolExecutor
import re

from ...core.robot import Robot, RobotInfo

@dataclass
class SentimentResult:
    """Structure tracking a generated market sentiment score."""
    symbol: str
    score: float
    volume: int
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'score': self.score,
            'volume': self.volume,
            'timestamp': self.timestamp.isoformat()
        }

class SentimentBot(Robot):
    """
    Sentiment Qualitative Bot
    
    Responsible for tracking market sentiment through social media text analysis,
    generating a uniform score that can act as confluence for other bots.
    """
    
    DEFAULT_POLL_INTERVAL = 300  # Default to polling every 5 minutes
    
    # Generic dictionary simulation of an NLP model
    BULLISH_TERMS = {'buy', 'bullish', 'long', 'up', 'moon', 'rally', 'surge', 'gain', 'breakout', 'support'}
    BEARISH_TERMS = {'sell', 'bearish', 'short', 'down', 'crash', 'drop', 'plummet', 'loss', 'resistance', 'dump'}
    
    def __init__(self, robot_info: RobotInfo, config: Dict[str, Any], 
                 message_bus=None, mongo_manager=None):
        super().__init__(robot_info, config)
        
        self.message_bus = message_bus
        self.mongo = mongo_manager
        
        self.symbols = config.get('symbols', ['XAUUSD', 'EURUSD'])
        self.poll_interval = config.get('poll_interval', self.DEFAULT_POLL_INTERVAL)
        
        # Mocks
        self.twitter_api_url = config.get('twitter_api', 'mock://twitter')
        self.reddit_api_url = config.get('reddit_api', 'mock://reddit')
        
    async def initialize(self) -> bool:
        """Initialize the Sentiment Bot."""
        self.logger.info(f"Initializing {self.robot_id}...")
        
        if self.message_bus:
            self.set_message_bus(self.message_bus)
            
        self.logger.info(f"{self.robot_id} initialized successfully")
        return True

    async def process(self, data: Any = None) -> Any:
        """Main processing loop checks social media and updates statuses."""
        try:
            for symbol in self.symbols:
                await self._evaluate_sentiment_for_symbol(symbol)
                
            # Internal sleep for strict poll interval polling
            await asyncio.sleep(self.poll_interval)
            
        except Exception as e:
            self.logger.error(f"Error in sentiment process loop: {e}")
            
        return None

    async def _evaluate_sentiment_for_symbol(self, symbol: str):
        """Scrape endpoints and parse texts."""
        loop = asyncio.get_event_loop()
        
        with ThreadPoolExecutor() as pool:
            # Run requests in parallel using threads
            twitter_future = loop.run_in_executor(pool, self._fetch_social_data, self.twitter_api_url, symbol)
            reddit_future = loop.run_in_executor(pool, self._fetch_social_data, self.reddit_api_url, symbol)
            
            twitter_texts, reddit_texts = await asyncio.gather(twitter_future, reddit_future)
            
        combined_texts = twitter_texts + reddit_texts
        
        if not combined_texts:
            return
            
        score = self._calculate_sentiment_score(combined_texts)
        volume = len(combined_texts)
        
        result = SentimentResult(
            symbol=symbol,
            score=score,
            volume=volume,
            timestamp=datetime.now()
        )
        
        await self._dispatch_sentiment(result)

    def _fetch_social_data(self, endpoint: str, symbol: str) -> List[str]:
        """Fetch raw text data from an endpoint."""
        if 'mock' in endpoint:
            # We enforce mocking for local test phases unless specifically passed a real URL
            return self._generate_mock_texts(symbol)
            
        # Standard HTTP proxy fallback behavior
        target_url = f"{endpoint}?query={symbol}"
        try:
            req = urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode('utf-8'))
                return [item.get('text', '') for item in payload.get('data', [])]
        except Exception as e:
            self.logger.warning(f"Error fetching from {endpoint}: {e}")
            return []

    def _generate_mock_texts(self, symbol: str) -> List[str]:
        """Dummy data generator simulating organic posts."""
        if symbol == "XAUUSD":
            return [
                "Gold is looking incredibly bullish right now, breaking resistance!",
                "Time to buy some heavy volume, looking for a strong rally",
                "Holding long positions, expected to surge."
            ]
        elif symbol == "EURUSD":
            return [
                "The Euro looks ready to crash below support levels.",
                "Massive sell wall spotted, very bearish structure.",
                "Shorting this immediately.",
                "Rally attempt failed, plummeting."
            ]
        return ["Neutral chops across the board..."]

    def _calculate_sentiment_score(self, texts: List[str]) -> float:
        """
        Processes texts and assigns a score:
        +1 for bullish keywords, -1 for bearish keywords.
        Returns a normalized score clamped between -100 and +100.
        """
        bull_count = 0
        bear_count = 0
        
        for text in texts:
            # Tokenize strictly by alphanumeric word boundaries, convert to lower.
            words = set(re.findall(r'\b[a-z]+\b', text.lower()))
            
            bullish_matches = words.intersection(self.BULLISH_TERMS)
            bearish_matches = words.intersection(self.BEARISH_TERMS)
            
            bull_count += len(bullish_matches)
            bear_count += len(bearish_matches)
            
        total = bull_count + bear_count
        if total == 0:
            return 0.0
            
        # Calculate raw ratio between -1 and 1
        raw_ratio = (bull_count - bear_count) / total
        
        # Scale to -100 to 100
        return round(raw_ratio * 100, 2)

    async def _dispatch_sentiment(self, result: SentimentResult) -> None:
        """Emits generated sentiment tracking records across the bus."""
        payload = result.to_dict()
        
        if self._message_bus:
            await self.send_message('sentiment_update', payload)
            
        if self.mongo:
            # Only log extreme anomalies to prevent db bloat over routine 5m checks
            abs_score = abs(result.score)
            if abs_score > 60:
                self.mongo.insert_log({
                    'level': 'INFO',
                    'component': self.robot_id,
                    'message': f"Extreme Sentiment detected for {result.symbol}: {result.score} (Volume: {result.volume})",
                    'data': payload,
                    'timestamp': datetime.now().isoformat()
                })
                
    async def cleanup(self) -> None:
        """Cleanup gracefully."""
        self.logger.info(f"Cleaning up {self.robot_id}...")
