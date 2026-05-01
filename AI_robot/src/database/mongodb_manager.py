"""
MongoDB Database Manager

Manages MongoDB connections and operations for logs, events, and unstructured data.
"""

import logging
from typing import Dict, List, Any, Optional
from contextlib import contextmanager

try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.collection import Collection
    from pymongo.database import Database
except ImportError:
    MongoClient = None
    Collection = None
    Database = None


class MongoDBManager:
    """
    Manages MongoDB database connections and operations.
    
    Provides methods for:
    - Log storage and retrieval
    - Event tracking
    - System metrics
    - AI training data
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize MongoDB manager.
        
        Args:
            config: Database configuration
        """
        if MongoClient is None:
            raise ImportError("pymongo is not installed. Run: pip install pymongo")
            
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self._host = config.get('host', 'localhost')
        self._port = config.get('port', 27017)
        self._database = config.get('database', 'trading_logs')
        self._user = config.get('user', '')
        self._password = config.get('password', '')
        
    def connect(self) -> None:
        """Connect to MongoDB"""
        self.logger.info(f"Connecting to MongoDB: {self._host}:{self._port}/{self._database}")
        
        try:
            uri = f"mongodb://{self._host}:{self._port}/"
            if self._user and self._password:
                uri = f"mongodb://{self._user}:{self._password}@{self._host}:{self._port}/"
                
            self.client = MongoClient(uri)
            self.db = self.client[self._database]
            
            # Test connection
            self.client.admin.command('ping')
            self.logger.info("MongoDB connection established")
        except Exception as e:
            self.logger.error(f"Failed to connect to MongoDB: {e}")
            raise
            
    def disconnect(self) -> None:
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            self.logger.info("MongoDB connection closed")
            
    @contextmanager
    def get_collection(self, name: str):
        """Get a collection from the database"""
        if not self.db:
            raise RuntimeError("Not connected to database")
            
        collection: Collection = self.db[name]
        try:
            yield collection
        finally:
            pass
            
    def create_index(self, collection_name: str, fields: List[str],
                     unique: bool = False) -> None:
        """
        Create an index on a collection.
        
        Args:
            collection_name: Collection name
            fields: Fields to index
            unique: Whether index should be unique
        """
        if not self.db:
            raise RuntimeError("Not connected to database")
            
        collection = self.db[collection_name]
        index_keys = [(field, ASCENDING) for field in fields]
        collection.create_index(index_keys, unique=unique)
        self.logger.info(f"Created index on {collection_name}: {fields}")
        
    # Log operations
    def create_logs_collection(self) -> None:
        """Create logs collection if not exists"""
        if not self.db:
            raise RuntimeError("Not connected to database")
            
        if 'logs' not in self.db.list_collection_names():
            self.db.create_collection('logs')
            
        self.create_index('logs', ['timestamp', 'level'])
        
    def insert_log(self, log_data: Dict[str, Any]) -> str:
        """
        Insert a log entry.
        
        Args:
            log_data: Log information
            
        Returns:
            Inserted document ID
        """
        if not self.db:
            raise RuntimeError("Not connected to database")
            
        result = self.db.logs.insert_one(log_data)
        return str(result.inserted_id)
        
    def get_logs(self, level: str = None, limit: int = 100,
                 skip: int = 0) -> List[Dict[str, Any]]:
        """
        Get log entries.
        
        Args:
            level: Filter by log level (optional)
            limit: Maximum number of results
            skip: Number of results to skip
            
        Returns:
            List of log entries
        """
        if not self.db:
            raise RuntimeError("Not connected to database")
            
        query = {}
        if level:
            query['level'] = level
            
        cursor = self.db.logs.find(query).skip(skip).limit(limit).sort('timestamp', DESCENDING)
        return list(cursor)
        
    # Event operations
    def create_events_collection(self) -> None:
        """Create events collection if not exists"""
        if not self.db:
            raise RuntimeError("Not connected to database")
            
        if 'events' not in self.db.list_collection_names():
            self.db.create_collection('events')
            
        self.create_index('events', ['timestamp', 'event_type'])
        
    def insert_event(self, event_data: Dict[str, Any]) -> str:
        """
        Insert an event.
        
        Args:
            event_data: Event information
            
        Returns:
            Inserted document ID
        """
        if not self.db:
            raise RuntimeError("Not connected to database")
            
        result = self.db.events.insert_one(event_data)
        return str(result.inserted_id)
        
    def get_events(self, event_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get events.
        
        Args:
            event_type: Filter by event type (optional)
            limit: Maximum number of results
            
        Returns:
            List of events
        """
        if not self.db:
            raise RuntimeError("Not connected to database")
            
        query = {}
        if event_type:
            query['event_type'] = event_type
            
        cursor = self.db.events.find(query).limit(limit).sort('timestamp', DESCENDING)
        return list(cursor)
        
    # AI training data operations
    def create_training_data_collection(self) -> None:
        """Create training data collection if not exists"""
        if not self.db:
            raise RuntimeError("Not connected to database")
            
        if 'training_data' not in self.db.list_collection_names():
            self.db.create_collection('training_data')
            
        self.create_index('training_data', ['symbol', 'timestamp'])
        
    def insert_training_data(self, data: List[Dict[str, Any]]) -> int:
        """
        Insert training data records.
        
        Args:
            data: List of training data records
            
        Returns:
            Number of records inserted
        """
        if not self.db:
            raise RuntimeError("Not connected to database")
            
        result = self.db.training_data.insert_many(data, ordered=False)
        return len(result.inserted_ids)
        
    def get_training_data(self, symbol: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get training data for a symbol.
        
        Args:
            symbol: Trading symbol
            limit: Maximum number of results
            
        Returns:
            List of training data records
        """
        if not self.db:
            raise RuntimeError("Not connected to database")
            
        cursor = self.db.training_data.find({'symbol': symbol}).limit(limit)
        return list(cursor)

    # System logs operations
    def create_system_logs_collection(self) -> None:
        """Create system_logs collection if not exists"""
        if not self.db:
            raise RuntimeError("Not connected to database")

        if 'system_logs' not in self.db.list_collection_names():
            self.db.create_collection('system_logs')

        self.create_index('system_logs', ['timestamp', 'component', 'level'])

    def insert_system_log(self, log_data: Dict[str, Any]) -> str:
        """
        Insert a system log entry.

        Args:
            log_data: System log information

        Returns:
            Inserted document ID
        """
        if not self.db:
            raise RuntimeError("Not connected to database")

        result = self.db.system_logs.insert_one(log_data)
        return str(result.inserted_id)

    def get_system_logs(self, component: str = None, level: str = None,
                        limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get system log entries.

        Args:
            component: Filter by component (optional)
            level: Filter by log level (optional)
            limit: Maximum number of results

        Returns:
            List of system log entries
        """
        if not self.db:
            raise RuntimeError("Not connected to database")

        query = {}
        if component:
            query['component'] = component
        if level:
            query['level'] = level

        cursor = self.db.system_logs.find(query).limit(limit).sort('timestamp', DESCENDING)
        return list(cursor)

    # Configurations operations
    def create_configurations_collection(self) -> None:
        """Create configurations collection if not exists"""
        if not self.db:
            raise RuntimeError("Not connected to database")

        if 'configurations' not in self.db.list_collection_names():
            self.db.create_collection('configurations')

        self.create_index('configurations', ['key', 'version'])

    def insert_configuration(self, config_data: Dict[str, Any]) -> str:
        """
        Insert a configuration document.

        Args:
            config_data: Configuration data

        Returns:
            Inserted document ID
        """
        if not self.db:
            raise RuntimeError("Not connected to database")

        result = self.db.configurations.insert_one(config_data)
        return str(result.inserted_id)

    def get_configuration(self, key: str, version: int = None) -> Optional[Dict[str, Any]]:
        """
        Get a configuration by key.

        Args:
            key: Configuration key
            version: Configuration version (optional, gets latest if not specified)

        Returns:
            Configuration document or None
        """
        if not self.db:
            raise RuntimeError("Not connected to database")

        query = {'key': key}
        if version is not None:
            query['version'] = version

        return self.db.configurations.find_one(query, sort=[('version', DESCENDING)])

    def get_all_configurations(self, key_prefix: str = None) -> List[Dict[str, Any]]:
        """
        Get all configurations, optionally filtered by key prefix.

        Args:
            key_prefix: Filter by key prefix (optional)

        Returns:
            List of configuration documents
        """
        if not self.db:
            raise RuntimeError("Not connected to database")

        query = {}
        if key_prefix:
            query['key'] = {'$regex': f'^{key_prefix}'}

        cursor = self.db.configurations.find(query).sort('key', ASCENDING)
        return list(cursor)

    def update_configuration(self, key: str, config_data: Dict[str, Any],
                             version: int = None) -> str:
        """
        Update or insert a configuration.

        Args:
            key: Configuration key
            config_data: Configuration data to update
            version: Configuration version (auto-incremented if not specified)

        Returns:
            Inserted/updated document ID
        """
        if not self.db:
            raise RuntimeError("Not connected to database")

        existing = self.get_configuration(key, version)
        if existing:
            config_data['_id'] = existing['_id']
            if version is None:
                config_data['version'] = existing.get('version', 0) + 1
            result = self.db.configurations.replace_one({'_id': existing['_id']}, config_data)
            return str(result.upserted_id) if result.upserted_id else str(existing['_id'])
        else:
            if version is None:
                config_data['version'] = 1
            config_data['key'] = key
            result = self.db.configurations.insert_one(config_data)
            return str(result.inserted_id)
