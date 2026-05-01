"""
Logging System Module

Provides comprehensive logging functionality with:
- Python logging configuration
- Log rotation
- Custom log formatters
- MongoDB integration for log storage
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None


class MongoDBHandler(logging.Handler):
    """
    Custom logging handler that stores logs in MongoDB.
    
    This handler extends Python's logging.Handler to send log records
    to a MongoDB collection for centralized log storage and retrieval.
    """
    
    def __init__(self, mongodb_manager, collection_name: str = 'logs'):
        """
        Initialize MongoDB handler.
        
        Args:
            mongodb_manager: MongoDBManager instance
            collection_name: Name of the collection to store logs
        """
        super().__init__()
        self.mongodb_manager = mongodb_manager
        self.collection_name = collection_name
        self.buffer = []
        self.flush_interval = 10  # Flush every 10 records
        
    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to MongoDB.
        
        Args:
            record: LogRecord to emit
        """
        try:
            log_entry = self._create_log_entry(record)
            self.buffer.append(log_entry)
            
            if len(self.buffer) >= self.flush_interval:
                self.flush()
                
        except Exception:
            self.handleError(record)
            
    def _create_log_entry(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        Create a log entry dictionary from a LogRecord.
        
        Args:
            record: LogRecord to convert
            
        Returns:
            Dictionary suitable for MongoDB storage
        """
        return {
            'timestamp': datetime.fromtimestamp(record.created),
            'level': record.levelname,
            'logger_name': record.name,
            'module': record.module,
            'function': record.funcName,
            'line_number': record.lineno,
            'message': record.getMessage(),
            'exception': self._format_exception(record),
            'process_id': record.process,
            'thread_id': record.thread,
            'thread_name': record.threadName,
            'file_path': record.pathname,
        }
        
    def _format_exception(self, record: logging.LogRecord) -> Optional[str]:
        """
        Format exception information if present.
        
        Args:
            record: LogRecord to check for exceptions
            
        Returns:
            Formatted exception string or None
        """
        if record.exc_info:
            return self.formatException(record.exc_info)
        return None
        
    def flush(self) -> None:
        """
        Flush buffered log entries to MongoDB.
        """
        if self.buffer:
            try:
                if self.mongodb_manager.db:
                    collection = self.mongodb_manager.db[self.collection_name]
                    collection.insert_many(self.buffer)
                self.buffer = []
            except Exception:
                pass  # Don't fail on flush errors
                
    def close(self) -> None:
        """
        Close the handler and flush remaining records.
        """
        self.flush()
        super().close()


class CustomFormatter(logging.Formatter):
    """
    Custom log formatter with enhanced formatting options.
    
    Provides colored output for console and detailed formatting
    for file logging.
    """
    
    # ANSI color codes for log levels
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    
    RESET = '\033[0m'
    
    # Format for console output (colored)
    CONSOLE_FORMAT = (
        '%(asctime)s '
        '%(levelname)s '
        '%(name)s '
        '%(module)s:%(lineno)d '
        '- %(message)s'
    )
    
    # Format for file output (detailed)
    FILE_FORMAT = (
        '%(asctime)s | '
        '%(levelname)-8s | '
        '%(name)s | '
        '%(module)s:%(lineno)d | '
        '%(process)d:%(thread)d | '
        '%(message)s'
    )
    
    def __init__(self, use_color: bool = True, is_file: bool = False):
        """
        Initialize custom formatter.
        
        Args:
            use_color: Whether to use ANSI colors
            is_file: Whether this is for file output
        """
        if is_file:
            fmt = self.FILE_FORMAT
        else:
            fmt = self.CONSOLE_FORMAT
            
        super().__init__(fmt)
        self.use_color = use_color
        
    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record.
        
        Args:
            record: LogRecord to format
            
        Returns:
            Formatted log string
        """
        # Apply color if enabled and not for file
        if self.use_color:
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = (
                    f"{self.COLORS[levelname]}{levelname}{self.RESET}"
                )
                
        return super().format(record)


class LoggerManager:
    """
    Centralized logger manager for the trading system.
    
    Provides consistent logging configuration across all components
    with support for multiple output targets (console, file, MongoDB).
    """
    
    _instance: Optional['LoggerManager'] = None
    _loggers: Dict[str, logging.Logger] = {}
    
    def __new__(cls):
        """
        Implement singleton pattern.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        """
        Initialize logger manager.
        """
        if self._initialized:
            return
            
        self._initialized = True
        self.config: Optional[Dict[str, Any]] = None
        self.mongodb_handler: Optional[MongoDBHandler] = None
        self.file_handler: Optional[logging.handlers.RotatingFileHandler] = None
        self.console_handler: Optional[logging.StreamHandler] = None
        
    def configure(self, config: Dict[str, Any]) -> None:
        """
        Configure logging system.
        
        Args:
            config: Logging configuration dictionary
        """
        self.config = config
        
        # Get logging configuration
        log_config = config.get('logging', {})
        log_level = log_config.get('level', 'INFO')
        log_file = log_config.get('file', 'logs/trading_system.log')
        max_bytes = log_config.get('max_bytes', 10485760)  # 10MB
        backup_count = log_config.get('backup_count', 5)
        
        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        root_logger.handlers = []
        
        # Setup console handler
        self.console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = CustomFormatter(use_color=True, is_file=False)
        self.console_handler.setFormatter(console_formatter)
        self.console_handler.setLevel(getattr(logging, log_level.upper()))
        root_logger.addHandler(self.console_handler)
        
        # Setup file handler with rotation
        self.file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_formatter = CustomFormatter(use_color=False, is_file=True)
        self.file_handler.setFormatter(file_formatter)
        self.file_handler.setLevel(getattr(logging, log_level.upper()))
        root_logger.addHandler(self.file_handler)
        
        # Setup MongoDB handler if MongoDB is configured
        if 'mongodb' in config.get('database', {}):
            try:
                from src.database.mongodb_manager import MongoDBManager
                mongo_config = config['database']['mongodb']
                mongo_manager = MongoDBManager(mongo_config)
                mongo_manager.connect()
                
                self.mongodb_handler = MongoDBHandler(mongo_manager)
                self.mongodb_handler.setLevel(getattr(logging, log_level.upper()))
                root_logger.addHandler(self.mongodb_handler)
                
            except ImportError:
                root_logger.warning(
                    "MongoDB manager not available. Logs will not be stored in MongoDB."
                )
            except Exception as e:
                root_logger.warning(
                    f"Failed to configure MongoDB handler: {e}. "
                    "Logs will not be stored in MongoDB."
                )
                
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get or create a logger with the given name.
        
        Args:
            name: Logger name (usually __name__)
            
        Returns:
            Configured logger instance
        """
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
        return self._loggers[name]
        
    def shutdown(self) -> None:
        """
        Shutdown logging system and flush all handlers.
        """
        # Flush MongoDB handler
        if self.mongodb_handler:
            self.mongodb_handler.flush()
            self.mongodb_handler.close()
            
        # Flush file handler
        if self.file_handler:
            self.file_handler.flush()
            self.file_handler.close()
            
        # Flush console handler
        if self.console_handler:
            self.console_handler.flush()
            self.console_handler.close()
            
        # Clear loggers
        self._loggers.clear()


# Global logger manager instance
logger_manager = LoggerManager()


def setup_logging(config: Dict[str, Any]) -> None:
    """
    Setup logging system with configuration.
    
    Args:
        config: Configuration dictionary
    """
    logger_manager.configure(config)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logger_manager.get_logger(name)


def shutdown_logging() -> None:
    """
    Shutdown logging system gracefully.
    """
    logger_manager.shutdown()
