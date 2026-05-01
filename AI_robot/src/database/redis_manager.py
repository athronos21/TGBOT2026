"""
Redis Manager

Manages Redis connections and operations for message bus and caching.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from contextlib import contextmanager

try:
    import redis
    from redis import Redis, ConnectionPool
except ImportError:
    redis = None
    Redis = None
    ConnectionPool = None


class RedisManager:
    """
    Manages Redis connections and operations.
    
    Provides methods for:
    - Pub/Sub messaging (message bus backend)
    - Caching
    - Rate limiting
    - Distributed locks
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Redis manager.
        
        Args:
            config: Redis configuration
        """
        if redis is None:
            raise ImportError("redis is not installed. Run: pip install redis")
            
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.client: Optional[Redis] = None
        self._host = config.get('host', 'localhost')
        self._port = config.get('port', 6379)
        self._db = config.get('db', 0)
        self._password = config.get('password', '')
        
    def connect(self) -> None:
        """Connect to Redis"""
        self.logger.info(f"Connecting to Redis: {self._host}:{self._port}/{self._db}")
        
        try:
            self.client = redis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self._password,
                decode_responses=True
            )
            # Test connection
            self.client.ping()
            self.logger.info("Redis connection established")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise
            
    def disconnect(self) -> None:
        """Close Redis connection"""
        if self.client:
            self.client.close()
            self.logger.info("Redis connection closed")
            
    @contextmanager
    def get_connection(self):
        """Get a Redis connection"""
        if not self.client:
            raise RuntimeError("Not connected to Redis")
            
        try:
            yield self.client
        finally:
            pass
            
    # Pub/Sub operations
    def publish(self, channel: str, message: Any) -> int:
        """
        Publish a message to a channel.
        
        Args:
            channel: Channel name
            message: Message to publish
            
        Returns:
            Number of subscribers that received the message
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")
            
        return self.client.publish(channel, message)
        
    def subscribe(self, channels: List[str]) -> None:
        """
        Subscribe to channels.
        
        Args:
            channels: List of channel names
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")
            
        pubsub = self.client.pubsub()
        pubsub.subscribe(*channels)
        return pubsub
        
    # Caching operations
    def set(self, key: str, value: Any, expire: int = None) -> bool:
        """
        Set a cache value.
        
        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds (optional)
            
        Returns:
            True if successful
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")
            
        if expire:
            return self.client.setex(key, expire, value)
        else:
            return self.client.set(key, value)
            
    def get(self, key: str) -> Optional[str]:
        """
        Get a cached value.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")
            
        return self.client.get(key)
        
    def delete(self, key: str) -> bool:
        """
        Delete a cached value.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")
            
        return bool(self.client.delete(key))
        
    def exists(self, key: str) -> bool:
        """
        Check if a key exists.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")
            
        return bool(self.client.exists(key))
        
    # Rate limiting
    def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """
        Check if request is within rate limit.
        
        Args:
            key: Rate limit key (e.g., user ID)
            limit: Maximum requests per window
            window: Window size in seconds
            
        Returns:
            True if request is allowed
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")
            
        current = self.client.get(key)
        
        if current is None:
            self.client.setex(key, window, 1)
            return True
        elif int(current) < limit:
            self.client.incr(key)
            return True
        else:
            return False
            
    # Distributed locks
    def acquire_lock(self, key: str, timeout: int = 10) -> Optional[str]:
        """
        Acquire a distributed lock.
        
        Args:
            key: Lock key
            timeout: Lock timeout in seconds
            
        Returns:
            Lock token or None if lock not acquired
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")
            
        lock = self.client.lock(key, timeout=timeout)
        acquired = lock.acquire(blocking=False)
        
        if acquired:
            return lock.token
        return None
        
    def release_lock(self, key: str, token: str) -> bool:
        """
        Release a distributed lock.
        
        Args:
            key: Lock key
            token: Lock token
            
        Returns:
            True if lock was released
        """
        if not self.client:
            raise RuntimeError("Not connected to Redis")
            
        lock = self.client.lock(key, token=token)
        try:
            lock.release()
            return True
        except:
            return False
