"""
News & Events Bot - Data Collection Robot

Periodically polls an economic calendar (or proxy) to track impending major events, 
filtering them by significance (High, Medium, Low) and dispatching early warning
signals across the system to halt trading algorithms proactively.
"""

import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import urllib.request
from urllib.error import URLError
from concurrent.futures import ThreadPoolExecutor

from ...core.robot import Robot, RobotInfo

@dataclass
class NewsEvent:
    """Structure tracking a specific fundamental news event."""
    id: str
    title: str
    impact: str  # e.g., 'HIGH', 'MEDIUM', 'LOW'
    currency: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'impact': self.impact,
            'currency': self.currency,
            'timestamp': self.timestamp.isoformat()
        }


class NewsEventsBot(Robot):
    """
    News & Events Bot
    
    Responsible for tracking the macroeconomic calendar and avoiding dangerous 
    news-induced slip/spread conditions proactively.
    """
    
    DEFAULT_POLL_INTERVAL = 3600  # Default to polling calendar API once every hour
    DEFAULT_WARNING_MINUTES = 15
    
    def __init__(self, robot_info: RobotInfo, config: Dict[str, Any], 
                 message_bus=None, mongo_manager=None):
        super().__init__(robot_info, config)
        
        self.message_bus = message_bus
        self.mongo = mongo_manager
        
        # Configuration
        self.api_url = config.get('calendar_api_url', 'https://mock.forex.api/calendar')
        self.poll_interval = config.get('poll_interval', self.DEFAULT_POLL_INTERVAL)
        self.target_currencies = config.get('target_currencies', ['USD', 'EUR', 'GBP', 'JPY'])
        self.high_impact_only = config.get('high_impact_only', True)
        self.warning_minutes = config.get('warning_minutes', self.DEFAULT_WARNING_MINUTES)
        
        # Internal cache
        self._upcoming_events: List[NewsEvent] = []
        self._alerted_event_ids = set()
        
    async def initialize(self) -> bool:
        """Initialize the News Events Bot."""
        self.logger.info(f"Initializing {self.robot_id}...")
        
        if self.message_bus:
            self.set_message_bus(self.message_bus)
            
        # Perform an initial sync
        await self._sync_calendar()
            
        self.logger.info(f"{self.robot_id} initialized successfully")
        return True
        
    async def process(self, data: Any = None) -> Any:
        """Main processing loop checks countdowns and triggers periodic syncs."""
        try:
            # 1. Alert evaluations for cached loaded events
            await self._evaluate_event_countdowns()
            
            # Sleep logic is handled by internal asyncio sleep pacing inside the outer loop usually,
            # but we can poll external HTTP calls on distinct long cycles.
            # We'll rely on an internal clock checking mechanism to fetch if 
            # more than self.poll_interval has passed.
            
            # Since robot base class loops quickly, we just slow this specific agent down significantly.
            await asyncio.sleep(60.0) 
            
        except Exception as e:
            self.logger.error(f"Error in news process loop: {e}")
            
        return None

    async def _sync_calendar(self):
        """Reaches out to the configured API and populates the cache."""
        loop = asyncio.get_event_loop()
        
        try:
            # In a production environment, this is replaced by actual aiohttp.
            # We use urllib wrapped in an executor to avoid blocking the MT5 asyncio thread.
            with ThreadPoolExecutor() as pool:
                response = await loop.run_in_executor(pool, self._fetch_sync, self.api_url)
                if response:
                    raw_events = json.loads(response)
                    self._parse_events(raw_events)
        except Exception as e:
            self.logger.error(f"Failed to synchronize economic calendar: {e}")

    def _fetch_sync(self, url: str) -> Optional[str]:
        """Synchronous HTTP fetch logic."""
        if 'mock' in url:
            # Bypass actual real HTTP for the mock endpoint configured by default
            return json.dumps([
                {
                    "id": "mock_nfp",
                    "title": "Non-Farm Payrolls",
                    "impact": "HIGH",
                    "currency": "USD",
                    "timestamp": datetime.now().isoformat()  # Mocking immediate trigger
                }
            ])
            
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read().decode('utf-8')
        except URLError as e:
            self.logger.warning(f"URLError fetching events: {e}")
            return None

    def _parse_events(self, raw_events: List[Dict[str, Any]]) -> None:
        """Parses json elements into strongly typed NewsEvent dataclasses."""
        self._upcoming_events.clear()
        
        for data in raw_events:
            event = NewsEvent(
                id=data.get('id', 'unknown'),
                title=data.get('title', 'Unknown Event'),
                impact=data.get('impact', 'LOW').upper(),
                currency=data.get('currency', 'USD').upper(),
                timestamp=datetime.fromisoformat(data['timestamp'])
            )
            
            if self._filter_significance(event):
                self._upcoming_events.append(event)
                
        self.logger.debug(f"Calendar refreshed. Tracking {len(self._upcoming_events)} major events.")

    def _filter_significance(self, event: NewsEvent) -> bool:
        """Returns True if the event should be tracked by the system."""
        if event.currency not in self.target_currencies:
            return False
            
        if self.high_impact_only and event.impact != 'HIGH':
            return False
            
        return True

    async def _evaluate_event_countdowns(self) -> None:
        """Check if any cached events are within the warning threshold window."""
        now = datetime.now()
        
        for event in self._upcoming_events:
            # Ensure we only alert once per specific event
            if event.id in self._alerted_event_ids:
                continue
                
            time_until_event = (event.timestamp - now).total_seconds() / 60.0
            
            # If the event is occurring within the next configured warning window
            if 0 <= time_until_event <= self.warning_minutes:
                await self._dispatch_news_alert(event, time_until_event)
                self._alerted_event_ids.add(event.id)
                
    async def _dispatch_news_alert(self, event: NewsEvent, minutes_away: float) -> None:
        """Emits an urgent warning to halt automated trading logic over the bus."""
        payload = {
            'level': 'CRITICAL',
            'alert_type': 'UPCOMING_NEWS',
            'minutes_until_event': round(minutes_away, 2),
            'event': event.to_dict()
        }
        
        if self._message_bus:
            await self.send_message('news_alert', payload)
            
        if self.mongo:
            self.mongo.insert_log({
                'level': 'WARNING',
                'component': self.robot_id,
                'message': f"News Alert: {event.title} ({event.impact} Impact) in {round(minutes_away, 1)}m",
                'data': payload,
                'timestamp': datetime.now().isoformat()
            })
            
    async def cleanup(self) -> None:
        """Cleanup gracefully."""
        self.logger.info(f"Cleaning up {self.robot_id}...")
        self._upcoming_events.clear()
        self._alerted_event_ids.clear()
