"""
Message Bus for robot communication

Provides pub/sub messaging between robots in the trading system.
"""

import asyncio
import logging
from typing import Dict, List, Callable, Any, Optional
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import uuid
import json
import redis


@dataclass
class Message:
    """Message in the bus"""
    id: str
    event: str
    data: Any
    timestamp: datetime
    sender: Optional[str] = None
    priority: str = "NORMAL"  # LOW, NORMAL, HIGH, CRITICAL
    ttl: Optional[int] = None  # Time to live in seconds
    
    def is_expired(self) -> bool:
        """Check if message has expired based on TTL"""
        if self.ttl is None:
            return False
        elapsed = (datetime.now() - self.timestamp).total_seconds()
        return elapsed > self.ttl
    
    def get_remaining_ttl(self) -> Optional[float]:
        """Get remaining time to live in seconds"""
        if self.ttl is None:
            return None
        elapsed = (datetime.now() - self.timestamp).total_seconds()
        return max(0, self.ttl - elapsed)


class MessageBus:
    """
    Pub/Sub message bus for robot communication.
    
    Robots can publish events and subscribe to events they're interested in.
    Supports Redis pub/sub, message priority, TTL, and message routing.
    """
    
    # Priority levels
    PRIORITY_LOW = "LOW"
    PRIORITY_NORMAL = "NORMAL"
    PRIORITY_HIGH = "HIGH"
    PRIORITY_CRITICAL = "CRITICAL"
    
    # Priority order for sorting
    PRIORITY_ORDER = {
        PRIORITY_LOW: 0,
        PRIORITY_NORMAL: 1,
        PRIORITY_HIGH: 2,
        PRIORITY_CRITICAL: 3
    }
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0):
        """
        Initialize the message bus.
        
        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            redis_db: Redis database number
        """
        self.logger = logging.getLogger(__name__)
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._priority_queues: Dict[str, asyncio.Queue] = {
            self.PRIORITY_LOW: asyncio.Queue(),
            self.PRIORITY_NORMAL: asyncio.Queue(),
            self.PRIORITY_HIGH: asyncio.Queue(),
            self.PRIORITY_CRITICAL: asyncio.Queue()
        }
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
        
        # Redis connection
        self._redis_host = redis_host
        self._redis_port = redis_port
        self._redis_db = redis_db
        self._redis_client: Optional[redis.Redis] = None
        self._redis_pubsub: Optional[redis.client.PubSub] = None
        self._redis_channels: List[str] = []
        
    async def connect_redis(self) -> bool:
        """
        Connect to Redis server.
        
        Returns:
            True if connection successful
        """
        try:
            self._redis_client = redis.Redis(
                host=self._redis_host,
                port=self._redis_port,
                db=self._redis_db,
                decode_responses=True
            )
            # Test connection
            self._redis_client.ping()
            self.logger.info(f"Connected to Redis at {self._redis_host}:{self._redis_port}")
            return True
        except redis.ConnectionError as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            return False
            
    async def disconnect_redis(self) -> None:
        """Disconnect from Redis server"""
        if self._redis_pubsub:
            self._redis_pubsub.close()
            self._redis_pubsub = None
            
        if self._redis_client:
            self._redis_client.close()
            self._redis_client = None
            
        self.logger.info("Disconnected from Redis")
        
    def is_redis_connected(self) -> bool:
        """Check if Redis is connected"""
        return self._redis_client is not None
    
    async def start(self) -> None:
        """Start the message bus processor"""
        self._running = True
        
        # Connect to Redis if not already connected
        if not self.is_redis_connected():
            await self.connect_redis()
            
        # Initialize Redis pubsub
        if self._redis_client:
            self._redis_pubsub = self._redis_client.pubsub()
            
        self._processor_task = asyncio.create_task(self._process_messages())
        self.logger.info("Message bus started")
        
    async def stop(self) -> None:
        """Stop the message bus"""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        await self.disconnect_redis()
        self.logger.info("Message bus stopped")
        
    async def publish(self, event: str, data: Any = None, sender: str = None, 
                     priority: str = "NORMAL", ttl: Optional[int] = None) -> str:
        """
        Publish an event to the bus.
        
        Args:
            event: Event name/topic
            data: Event data
            sender: Sender ID (optional)
            priority: Message priority (LOW, NORMAL, HIGH, CRITICAL)
            ttl: Time to live in seconds (optional)
            
        Returns:
            Message ID
        """
        message_id = str(uuid.uuid4())
        message = Message(
            id=message_id,
            event=event,
            data=data,
            timestamp=datetime.now(),
            sender=sender,
            priority=priority,
            ttl=ttl
        )
        
        # Add to priority queue
        await self._priority_queues[priority].put(message)
        
        # Publish to Redis if connected
        if self._redis_client:
            try:
                channel = f"channel:{event}"
                message_json = json.dumps({
                    "id": message.id,
                    "event": message.event,
                    "data": message.data,
                    "timestamp": message.timestamp.isoformat(),
                    "sender": message.sender,
                    "priority": message.priority,
                    "ttl": message.ttl
                })
                self._redis_client.publish(channel, message_json)
            except redis.RedisError as e:
                self.logger.error(f"Failed to publish to Redis: {e}")
        
        self.logger.debug(f"Published event: {event} (ID: {message_id}, Priority: {priority})")
        
        return message_id
        
    async def subscribe(self, event: str, callback: Callable[[Message], None]) -> str:
        """
        Subscribe to an event.
        
        Args:
            event: Event name to subscribe to
            callback: Function to call when event is received
            
        Returns:
            Subscription ID
        """
        subscription_id = str(uuid.uuid4())
        self._subscribers[event].append(callback)
        self.logger.debug(f"Subscribed to {event} (ID: {subscription_id})")
        
        # Subscribe to Redis channel if connected
        if self._redis_client and self._redis_pubsub:
            try:
                channel = f"channel:{event}"
                self._redis_pubsub.subscribe(**{channel: self._handle_redis_message})
                self._redis_channels.append(channel)
            except redis.RedisError as e:
                self.logger.error(f"Failed to subscribe to Redis channel {channel}: {e}")
                
        return subscription_id
        
    async def _handle_redis_message(self, message: dict) -> None:
        """
        Handle incoming Redis message.
        
        Args:
            message: Redis message dict
        """
        try:
            if message['type'] == 'message':
                data = json.loads(message['data'])
                message_obj = Message(
                    id=data['id'],
                    event=data['event'],
                    data=data['data'],
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    sender=data.get('sender'),
                    priority=data.get('priority', 'NORMAL'),
                    ttl=data.get('ttl')
                )
                
                # Deliver to subscribers
                if message_obj.event in self._subscribers:
                    for callback in self._subscribers[message_obj.event]:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(message_obj)
                            else:
                                callback(message_obj)
                        except Exception as e:
                            self.logger.error(
                                f"Error in subscriber callback for {message_obj.event}: {e}"
                            )
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Failed to parse Redis message: {e}")
        
    async def unsubscribe(self, event: str, callback: Callable[[Message], None]) -> bool:
        """
        Unsubscribe from an event.
        
        Args:
            event: Event name
            callback: Callback to remove
            
        Returns:
            True if unsubscribed successfully
        """
        if event in self._subscribers:
            self._subscribers[event] = [
                cb for cb in self._subscribers[event] if cb != callback
            ]
            self.logger.debug(f"Unsubscribed from {event}")
            
            # Unsubscribe from Redis if no more subscribers
            if not self._subscribers[event] and self._redis_pubsub:
                try:
                    channel = f"channel:{event}"
                    self._redis_pubsub.unsubscribe(channel)
                    if channel in self._redis_channels:
                        self._redis_channels.remove(channel)
                except redis.RedisError as e:
                    self.logger.error(f"Failed to unsubscribe from Redis channel {channel}: {e}")
                    
            return True
        return False
        
    async def wait_for_message(self, event: str, timeout: float = 5.0, 
                              priority: Optional[str] = None) -> Optional[Message]:
        """
        Wait for a specific event with timeout.
        
        Args:
            event: Event to wait for
            timeout: Timeout in seconds
            priority: Optional priority filter
            
        Returns:
            Message if received, None if timeout
        """
        try:
            if priority:
                # Wait for specific priority queue
                message = await asyncio.wait_for(
                    self._priority_queues[priority].get(),
                    timeout=timeout
                )
                if message.event == event:
                    return message
                else:
                    # Put it back if not the right event
                    await self._priority_queues[priority].put(message)
                    return None
            else:
                # Check all priority queues
                for p in [self.PRIORITY_CRITICAL, self.PRIORITY_HIGH, 
                         self.PRIORITY_NORMAL, self.PRIORITY_LOW]:
                    try:
                        message = asyncio.wait_for(
                            self._priority_queues[p].get(),
                            timeout=timeout
                        )
                        if message.event == event:
                            return message
                        else:
                            await self._priority_queues[p].put(message)
                    except asyncio.TimeoutError:
                        continue
                return None
        except asyncio.TimeoutError:
            return None
            
    async def _process_messages(self) -> None:
        """Process messages from the priority queues"""
        while self._running:
            try:
                # Process messages by priority (highest first)
                for priority in [self.PRIORITY_CRITICAL, self.PRIORITY_HIGH, 
                                self.PRIORITY_NORMAL, self.PRIORITY_LOW]:
                    try:
                        message = asyncio.wait_for(
                            self._priority_queues[priority].get(),
                            timeout=0.01  # Short timeout to check all queues
                        )
                        
                        # Check if message is expired
                        if message.is_expired():
                            self.logger.warning(
                                f"Message expired: {message.id} (event: {message.event})"
                            )
                            continue
                        
                        # Deliver to subscribers
                        if message.event in self._subscribers:
                            for callback in self._subscribers[message.event]:
                                try:
                                    if asyncio.iscoroutinefunction(callback):
                                        await callback(message)
                                    else:
                                        callback(message)
                                except Exception as e:
                                    self.logger.error(
                                        f"Error in subscriber callback for {message.event}: {e}"
                                    )
                                    
                    except asyncio.TimeoutError:
                        continue
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error processing message: {e}")
