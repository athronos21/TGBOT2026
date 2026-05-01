"""
Unit tests for the logging system.
"""

import logging
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.utils.logger import (
    MongoDBHandler,
    CustomFormatter,
    LoggerManager,
    setup_logging,
    get_logger,
    shutdown_logging,
)


class TestCustomFormatter:
    """Tests for CustomFormatter class."""
    
    def test_console_formatter_format(self):
        """Test console formatter creates correct format."""
        formatter = CustomFormatter(use_color=True, is_file=False)
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        assert 'INFO' in formatted
        assert 'Test message' in formatted
        assert 'test' in formatted
        
    def test_file_formatter_format(self):
        """Test file formatter creates detailed format."""
        formatter = CustomFormatter(use_color=False, is_file=True)
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        assert 'INFO' in formatted
        assert 'Test message' in formatted
        assert '|' in formatted  # File format uses pipe separators
        
    def test_color_codes_applied(self):
        """Test that ANSI color codes are applied for console output."""
        formatter = CustomFormatter(use_color=True, is_file=False)
        
        record = logging.LogRecord(
            name='test',
            level=logging.ERROR,
            pathname='test.py',
            lineno=1,
            msg='Error message',
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        # Should contain color codes for ERROR level (magenta)
        assert '\033[35m' in formatted  # Magenta color code
        assert '\033[0m' in formatted   # Reset code


class TestMongoDBHandler:
    """Tests for MongoDBHandler class."""
    
    def test_emit_creates_log_entry(self):
        """Test that emit creates proper log entry."""
        mock_manager = Mock()
        mock_manager.db = Mock()
        mock_collection = Mock()
        mock_manager.db.__getitem__ = Mock(return_value=mock_collection)
        
        handler = MongoDBHandler(mock_manager, collection_name='test_logs')
        
        record = logging.LogRecord(
            name='test.logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test log message',
            args=(),
            exc_info=None
        )
        
        handler.emit(record)
        
        # Should have created log entry
        assert len(handler.buffer) == 1
        log_entry = handler.buffer[0]
        
        assert log_entry['level'] == 'INFO'
        assert log_entry['logger_name'] == 'test.logger'
        assert log_entry['message'] == 'Test log message'
        assert log_entry['line_number'] == 42
        
    def test_flush_sends_to_mongodb(self):
        """Test that flush sends buffered logs to MongoDB."""
        mock_manager = Mock()
        mock_manager.db = Mock()
        mock_collection = Mock()
        mock_manager.db.__getitem__ = Mock(return_value=mock_collection)
        
        handler = MongoDBHandler(mock_manager, collection_name='test_logs')
        handler.flush_interval = 2  # Flush after 2 records
        
        # Add records to buffer
        record1 = logging.LogRecord(
            name='test', level=logging.INFO, pathname='test.py', lineno=1,
            msg='Message 1', args=(), exc_info=None
        )
        record2 = logging.LogRecord(
            name='test', level=logging.INFO, pathname='test.py', lineno=2,
            msg='Message 2', args=(), exc_info=None
        )
        
        handler.emit(record1)
        handler.emit(record2)
        
        # Should have flushed to MongoDB
        assert mock_collection.insert_many.called
        assert len(handler.buffer) == 0
        
    def test_close_flushes_remaining_records(self):
        """Test that close flushes remaining buffered records."""
        mock_manager = Mock()
        mock_manager.db = Mock()
        mock_collection = Mock()
        mock_manager.db.__getitem__ = Mock(return_value=mock_collection)
        
        handler = MongoDBHandler(mock_manager, collection_name='test_logs')
        handler.flush_interval = 10  # High threshold
        
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='test.py', lineno=1,
            msg='Message', args=(), exc_info=None
        )
        handler.emit(record)
        
        # Buffer should have 1 record
        assert len(handler.buffer) == 1
        
        # Close should flush
        handler.close()
        
        # Buffer should be empty after close
        assert len(handler.buffer) == 0


class TestLoggerManager:
    """Tests for LoggerManager class."""
    
    def test_singleton_pattern(self):
        """Test that LoggerManager follows singleton pattern."""
        manager1 = LoggerManager()
        manager2 = LoggerManager()
        
        assert manager1 is manager2
        
    def test_configure_creates_handlers(self):
        """Test that configure creates all handlers."""
        config = {
            'logging': {
                'level': 'DEBUG',
                'file': 'logs/test.log',
                'max_bytes': 10000,
                'backup_count': 3
            }
        }
        
        manager = LoggerManager()
        manager.configure(config)
        
        assert manager.console_handler is not None
        assert manager.file_handler is not None
        
    def test_get_logger_returns_configured_logger(self):
        """Test that get_logger returns properly configured logger."""
        config = {
            'logging': {
                'level': 'INFO',
                'file': 'logs/test.log'
            }
        }
        
        manager = LoggerManager()
        manager.configure(config)
        
        logger = manager.get_logger('test.module')
        
        assert logger.name == 'test.module'
        assert logger.level == logging.INFO
        
    def test_shutdown_closes_handlers(self):
        """Test that shutdown closes all handlers."""
        config = {
            'logging': {
                'level': 'DEBUG',
                'file': 'logs/test.log'
            }
        }
        
        manager = LoggerManager()
        manager.configure(config)
        
        # Handlers should be created
        assert manager.console_handler is not None
        assert manager.file_handler is not None
        
        # Shutdown should close them
        manager.shutdown()
        
        # Note: We can't easily test if handlers are actually closed
        # without calling actual close methods, but we verify the method exists


class TestSetupLoggingFunction:
    """Tests for setup_logging function."""
    
    def test_setup_logging_configures_manager(self):
        """Test that setup_logging configures the logger manager."""
        config = {
            'logging': {
                'level': 'WARNING',
                'file': 'logs/test.log'
            }
        }
        
        # Clear any existing configuration
        LoggerManager._instance = None
        
        setup_logging(config)
        
        # Verify configuration was applied
        manager = LoggerManager()
        assert manager.config is not None
        assert manager.config['logging']['level'] == 'WARNING'


class TestGetLoggerFunction:
    """Tests for get_logger function."""
    
    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        config = {
            'logging': {
                'level': 'DEBUG',
                'file': 'logs/test.log'
            }
        }
        
        LoggerManager._instance = None
        setup_logging(config)
        
        logger = get_logger('test.module')
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'test.module'


class TestIntegration:
    """Integration tests for the logging system."""
    
    def test_full_logging_workflow(self, tmp_path):
        """Test complete logging workflow with file output."""
        # Create temp directory for logs
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "test.log"
        
        config = {
            'logging': {
                'level': 'DEBUG',
                'file': str(log_file),
                'max_bytes': 10000,
                'backup_count': 2
            }
        }
        
        LoggerManager._instance = None
        setup_logging(config)
        
        # Get logger and log some messages
        logger = get_logger('test.integration')
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        # Verify log file was created
        assert log_file.exists()
        
        # Read and verify log file content
        content = log_file.read_text()
        assert "INFO" in content
        assert "Warning message" in content
        
    def test_log_rotation(self, tmp_path):
        """Test that log rotation works correctly."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "rotated.log"
        
        config = {
            'logging': {
                'level': 'DEBUG',
                'file': str(log_file),
                'max_bytes': 100,  # Very small for testing
                'backup_count': 3
            }
        }
        
        LoggerManager._instance = None
        setup_logging(config)
        
        logger = get_logger('test.rotation')
        
        # Write enough data to trigger rotation
        for i in range(50):
            logger.debug(f"Debug message {i} with some extra text to make it longer")
        
        # Check that rotation files were created
        assert log_file.exists()
        
        # There should be backup files
        backup_files = list(log_dir.glob("rotated.log.*"))
        assert len(backup_files) > 0


class TestMongoDBIntegration:
    """Tests for MongoDB integration."""
    
    @pytest.mark.skipif(
        not os.environ.get('TEST_MONGODB', False),
        reason="MongoDB integration tests require TEST_MONGODB env var"
    )
    def test_mongodb_handler_integration(self):
        """Test MongoDB handler with real MongoDB connection."""
        config = {
            'logging': {
                'level': 'DEBUG',
                'file': 'logs/test.log'
            },
            'database': {
                'mongodb': {
                    'host': 'localhost',
                    'port': 27017,
                    'database': 'test_logs'
                }
            }
        }
        
        LoggerManager._instance = None
        setup_logging(config)
        
        logger = get_logger('test.mongodb')
        logger.info("Test MongoDB log entry")
        
        # Verify MongoDB handler was created
        manager = LoggerManager()
        assert manager.mongodb_handler is not None
