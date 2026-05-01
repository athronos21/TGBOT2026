"""
Error Handler for the Multi-Robot Trading System

Provides comprehensive error handling with retry logic, severity classification,
and notification system for all robots in the trading ecosystem.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import traceback


class ErrorSeverity(Enum):
    """Error severity classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error category classification"""
    CONNECTION = "connection"
    DATA = "data"
    EXECUTION = "execution"
    CONFIGURATION = "configuration"
    SYSTEM = "system"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


@dataclass
class ErrorInfo:
    """Error information"""
    error_id: str
    robot_id: str
    error_type: str
    error_message: str
    severity: ErrorSeverity
    category: ErrorCategory
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    backoff_time: float = 0.0
    handled: bool = False
    notification_sent: bool = False


@dataclass
class RetryConfig:
    """Retry configuration"""
    max_retries: int = 3
    base_backoff: float = 1.0
    max_backoff: float = 30.0
    backoff_multiplier: float = 2.0
    retryable_exceptions: List[str] = field(default_factory=lambda: [
        'ConnectionError',
        'TimeoutError',
        'ConnectionResetError',
        'ConnectionRefusedError',
        'RedisConnectionError',
        'MT5ConnectionError'
    ])


class ErrorHandler:
    """
    Centralized error handling system for the trading system.
    
    Features:
    - Error severity classification (LOW, MEDIUM, HIGH, CRITICAL)
    - Automatic retry with exponential backoff
    - Error categorization for better handling
    - Notification system for critical errors
    - Error tracking and statistics
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the error handler.
        
        Args:
            config: Error handler configuration
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Get retry configuration
        retry_config = self.config.get('retry', {})
        self.retry_config = RetryConfig(
            max_retries=retry_config.get('max_retries', 3),
            base_backoff=retry_config.get('base_backoff', 1.0),
            max_backoff=retry_config.get('max_backoff', 30.0),
            backoff_multiplier=retry_config.get('backoff_multiplier', 2.0),
            retryable_exceptions=retry_config.get('retryable_exceptions', [
                'ConnectionError',
                'TimeoutError',
                'ConnectionResetError',
                'ConnectionRefusedError',
                'RedisConnectionError',
                'MT5ConnectionError'
            ])
        )
        
        # Error tracking
        self._error_counts: Dict[str, int] = {}
        self._error_history: List[ErrorInfo] = []
        self._active_errors: Dict[str, ErrorInfo] = {}
        
        # Notification callbacks
        self._notification_callbacks: List[Callable[[ErrorInfo], None]] = []
        
        # Severity thresholds
        self._severity_thresholds = self.config.get('severity_thresholds', {
            'low': {'max_errors': 100, 'action': 'log'},
            'medium': {'max_errors': 10, 'action': 'notify'},
            'high': {'max_errors': 5, 'action': 'restart_robot'},
            'critical': {'max_errors': 1, 'action': 'kill_switch'}
        })
        
        self.logger.info("Error Handler initialized")
        
    def register_notification_callback(self, callback: Callable[[ErrorInfo], None]) -> str:
        """
        Register a notification callback.
        
        Args:
            callback: Function to call when errors occur
            
        Returns:
            Callback ID
        """
        callback_id = str(id(callback))
        self._notification_callbacks.append(callback)
        return callback_id
        
    def unregister_notification_callback(self, callback_id: str) -> bool:
        """
        Unregister a notification callback.
        
        Args:
            callback_id: Callback ID to remove
            
        Returns:
            True if removed successfully
        """
        try:
            callback = next(cb for cb in self._notification_callbacks if id(cb) == int(callback_id))
            self._notification_callbacks.remove(callback)
            return True
        except StopIteration:
            return False
            
    def classify_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorInfo:
        """
        Classify an error and create ErrorInfo.
        
        Args:
            error: The exception that occurred
            context: Additional context information
            
        Returns:
            ErrorInfo with classification
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        # Determine severity based on error type and context
        severity = self._determine_severity(error_type, error_message, context)
        
        # Determine category
        category = self._determine_category(error_type, error_message, context)
        
        # Check if error is retryable
        is_retryable = error_type in self.retry_config.retryable_exceptions
        
        # Create error info
        error_info = ErrorInfo(
            error_id=str(id(error)),
            robot_id=context.get('robot_id', 'unknown') if context else 'unknown',
            error_type=error_type,
            error_message=error_message,
            severity=severity,
            category=category,
            timestamp=datetime.now(),
            context=context or {},
            stack_trace=traceback.format_exc() if self.config.get('capture_stack_trace', True) else None,
            retry_count=0,
            max_retries=self.retry_config.max_retries if is_retryable else 0,
            backoff_time=0.0,
            handled=False,
            notification_sent=False
        )
        
        # Track error
        self._track_error(error_info)
        
        return error_info
        
    def _determine_severity(self, error_type: str, error_message: str, 
                           context: Dict[str, Any] = None) -> ErrorSeverity:
        """
        Determine error severity based on type and context.
        
        Args:
            error_type: Type of error
            error_message: Error message
            context: Additional context
            
        Returns:
            ErrorSeverity level
        """
        # Critical errors
        critical_types = [
            'SystemExit', 'KeyboardInterrupt', 'MemoryError',
            'FatalError', 'SecurityError'
        ]
        if error_type in critical_types:
            return ErrorSeverity.CRITICAL
            
        # High severity errors
        high_types = [
            'ConnectionError', 'ConnectionResetError', 'ConnectionRefusedError',
            'DatabaseError', 'MT5ConnectionError', 'RedisConnectionError',
            'AuthenticationError', 'AuthorizationError'
        ]
        if error_type in high_types:
            return ErrorSeverity.HIGH
            
        # Check for critical keywords in message
        critical_keywords = [
            'kill switch', 'emergency', 'critical', 'fatal',
            'security breach', 'data loss', 'system failure'
        ]
        if any(kw in error_message.lower() for kw in critical_keywords):
            return ErrorSeverity.CRITICAL
            
        # Medium severity errors
        medium_types = [
            'ValueError', 'TypeError', 'KeyError', 'IndexError',
            'ValidationError', 'ConfigurationError'
        ]
        if error_type in medium_types:
            return ErrorSeverity.MEDIUM
            
        # Low severity errors (default)
        return ErrorSeverity.LOW
        
    def _determine_category(self, error_type: str, error_message: str,
                           context: Dict[str, Any] = None) -> ErrorCategory:
        """
        Determine error category.
        
        Args:
            error_type: Type of error
            error_message: Error message
            context: Additional context
            
        Returns:
            ErrorCategory
        """
        # Connection errors
        connection_keywords = ['connection', 'network', 'socket', 'timeout', 'host']
        if any(kw in error_message.lower() for kw in connection_keywords):
            return ErrorCategory.CONNECTION
            
        # Data errors
        data_keywords = ['data', 'format', 'parse', 'invalid', 'null']
        if any(kw in error_message.lower() for kw in data_keywords):
            return ErrorCategory.DATA
            
        # Execution errors
        execution_keywords = ['execution', 'order', 'trade', 'position']
        if any(kw in error_message.lower() for kw in execution_keywords):
            return ErrorCategory.EXECUTION
            
        # Configuration errors
        if error_type in ['ConfigurationError', 'KeyError', 'AttributeError']:
            return ErrorCategory.CONFIGURATION
            
        # External errors
        external_keywords = ['api', 'external', 'third-party', 'service']
        if any(kw in error_message.lower() for kw in external_keywords):
            return ErrorCategory.EXTERNAL
            
        # System errors
        if error_type in ['SystemError', 'RuntimeError', 'GeneratorExit']:
            return ErrorCategory.SYSTEM
            
        return ErrorCategory.UNKNOWN
        
    def _track_error(self, error_info: ErrorInfo) -> None:
        """
        Track error statistics.
        
        Args:
            error_info: Error information
        """
        # Update error counts
        error_key = f"{error_info.robot_id}:{error_info.error_type}"
        self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1
        
        # Add to history
        self._error_history.append(error_info)
        
        # Keep only last 1000 errors
        if len(self._error_history) > 1000:
            self._error_history = self._error_history[-1000:]
            
        # Track active errors
        self._active_errors[error_info.error_id] = error_info
        
        self.logger.debug(f"Tracked error: {error_info.error_type} in {error_info.robot_id}")
        
    def get_error_count(self, robot_id: str = None, error_type: str = None) -> int:
        """
        Get error count for specific robot or error type.
        
        Args:
            robot_id: Robot ID (optional)
            error_type: Error type (optional)
            
        Returns:
            Error count
        """
        if robot_id and error_type:
            key = f"{robot_id}:{error_type}"
            return self._error_counts.get(key, 0)
        elif robot_id:
            return sum(
                count for key, count in self._error_counts.items()
                if key.startswith(f"{robot_id}:")
            )
        elif error_type:
            return sum(
                count for key, count in self._error_counts.items()
                if key.endswith(f":{error_type}")
            )
        else:
            return sum(self._error_counts.values())
            
    def get_error_history(self, robot_id: str = None, limit: int = 100) -> List[ErrorInfo]:
        """
        Get error history.
        
        Args:
            robot_id: Robot ID (optional)
            limit: Maximum number of errors to return
            
        Returns:
            List of error information
        """
        errors = self._error_history
        if robot_id:
            errors = [e for e in errors if e.robot_id == robot_id]
        return errors[-limit:]
        
    def get_active_errors(self, robot_id: str = None) -> List[ErrorInfo]:
        """
        Get currently active errors.
        
        Args:
            robot_id: Robot ID (optional)
            
        Returns:
            List of active error information
        """
        errors = list(self._active_errors.values())
        if robot_id:
            errors = [e for e in errors if e.robot_id == robot_id]
        return errors
        
    def clear_error(self, error_id: str) -> bool:
        """
        Clear a specific error.
        
        Args:
            error_id: Error ID to clear
            
        Returns:
            True if cleared
        """
        if error_id in self._active_errors:
            del self._active_errors[error_id]
            return True
        return False
        
    def clear_robot_errors(self, robot_id: str) -> int:
        """
        Clear all errors for a specific robot.
        
        Args:
            robot_id: Robot ID
            
        Returns:
            Number of errors cleared
        """
        errors_to_clear = [
            error_id for error_id, error in self._active_errors.items()
            if error.robot_id == robot_id
        ]
        for error_id in errors_to_clear:
            del self._active_errors[error_id]
        return len(errors_to_clear)
        
    def calculate_backoff(self, retry_count: int) -> float:
        """
        Calculate backoff time for retry.
        
        Args:
            retry_count: Current retry count
            
        Returns:
            Backoff time in seconds
        """
        backoff = self.retry_config.base_backoff * (
            self.retry_config.backoff_multiplier ** retry_count
        )
        return min(backoff, self.retry_config.max_backoff)
        
    def should_retry(self, error_info: ErrorInfo) -> bool:
        """
        Check if error should be retried.
        
        Args:
            error_info: Error information
            
        Returns:
            True if should retry
        """
        return (error_info.retry_count < error_info.max_retries and
                error_info.category == ErrorCategory.CONNECTION)
                
    async def handle_error(self, error_info: ErrorInfo) -> None:
        """
        Handle an error with appropriate action.
        
        Args:
            error_info: Error information
        """
        robot_id = error_info.robot_id
        severity = error_info.severity
        
        # Update retry count
        error_info.retry_count += 1
        
        # Log error
        self._log_error(error_info)
        
        # Determine action based on severity
        action = self._get_action_for_severity(severity)
        
        # Execute action
        if action == 'kill_switch':
            await self._handle_critical_error(error_info)
        elif action == 'restart_robot':
            await self._handle_high_error(error_info)
        elif action == 'notify':
            await self._handle_medium_error(error_info)
        else:
            await self._handle_low_error(error_info)
            
        # Send notifications
        await self._send_notifications(error_info)
        
        # Update error info
        error_info.handled = True
        
    def _log_error(self, error_info: ErrorInfo) -> None:
        """
        Log error with appropriate level.
        
        Args:
            error_info: Error information
        """
        log_methods = {
            ErrorSeverity.CRITICAL: self.logger.critical,
            ErrorSeverity.HIGH: self.logger.error,
            ErrorSeverity.MEDIUM: self.logger.warning,
            ErrorSeverity.LOW: self.logger.info
        }
        
        log_method = log_methods.get(error_info.severity, self.logger.info)
        
        log_message = (
            f"Error in {error_info.robot_id}: {error_info.error_type} - "
            f"{error_info.error_message} (Severity: {error_info.severity.value}, "
            f"Category: {error_info.category.value}, Retry: {error_info.retry_count}/"
            f"{error_info.max_retries})"
        )
        
        log_method(log_message)
        
        if error_info.stack_trace:
            self.logger.debug(f"Stack trace: {error_info.stack_trace}")
            
    def _get_action_for_severity(self, severity: ErrorSeverity) -> str:
        """
        Get action for error severity.
        
        Args:
            severity: Error severity
            
        Returns:
            Action to take
        """
        thresholds = self._severity_thresholds.get(severity.value, {})
        return thresholds.get('action', 'log')
        
    async def _handle_critical_error(self, error_info: ErrorInfo) -> None:
        """
        Handle critical error - trigger kill switch.
        
        Args:
            error_info: Error information
        """
        self.logger.critical(
            f"CRITICAL ERROR in {error_info.robot_id}: {error_info.error_message}"
        )
        
        # Update error info
        error_info.max_retries = 0  # No retries for critical errors
        
        # Send notification
        await self._send_notification(
            f"🚨 CRITICAL ERROR in {error_info.robot_id}: {error_info.error_message}",
            priority='CRITICAL'
        )
        
    async def _handle_high_error(self, error_info: ErrorInfo) -> None:
        """
        Handle high severity error - restart robot.
        
        Args:
            error_info: Error information
        """
        self.logger.error(
            f"HIGH ERROR in {error_info.robot_id}: {error_info.error_message}"
        )
        
        # Send notification
        await self._send_notification(
            f"⚠️ HIGH ERROR in {error_info.robot_id}: {error_info.error_message}",
            priority='HIGH'
        )
        
    async def _handle_medium_error(self, error_info: ErrorInfo) -> None:
        """
        Handle medium severity error - notify.
        
        Args:
            error_info: Error information
        """
        self.logger.warning(
            f"MEDIUM ERROR in {error_info.robot_id}: {error_info.error_message}"
        )
        
        # Send notification
        await self._send_notification(
            f"⚠️ MEDIUM ERROR in {error_info.robot_id}: {error_info.error_message}",
            priority='NORMAL'
        )
        
    async def _handle_low_error(self, error_info: ErrorInfo) -> None:
        """
        Handle low severity error - log only.
        
        Args:
            error_info: Error information
        """
        self.logger.info(
            f"LOW ERROR in {error_info.robot_id}: {error_info.error_message}"
        )
        
    async def _send_notifications(self, error_info: ErrorInfo) -> None:
        """
        Send error notifications via registered callbacks.
        
        Args:
            error_info: Error information
        """
        # Check if notification already sent
        if error_info.notification_sent:
            return
            
        # Send to registered callbacks
        for callback in self._notification_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(error_info)
                else:
                    callback(error_info)
            except Exception as e:
                self.logger.error(f"Error in notification callback: {e}")
                
        error_info.notification_sent = True
        
    async def _send_notification(self, message: str, priority: str = 'NORMAL') -> None:
        """
        Send a notification message.
        
        Args:
            message: Notification message
            priority: Notification priority
        """
        # Send to all registered callbacks
        for callback in self._notification_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                self.logger.error(f"Error sending notification: {e}")
                
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get error handling statistics.
        
        Returns:
            Statistics dictionary
        """
        severity_counts = {severity.value: 0 for severity in ErrorSeverity}
        category_counts = {category.value: 0 for category in ErrorCategory}
        
        for error in self._error_history:
            severity_counts[error.severity.value] += 1
            category_counts[error.category.value] += 1
            
        return {
            'total_errors': len(self._error_history),
            'active_errors': len(self._active_errors),
            'error_counts_by_severity': severity_counts,
            'error_counts_by_category': category_counts,
            'error_counts_by_robot': self._get_error_counts_by_robot(),
            'error_counts_by_type': self._get_error_counts_by_type()
        }
        
    def _get_error_counts_by_robot(self) -> Dict[str, int]:
        """Get error counts grouped by robot."""
        counts = {}
        for error in self._error_history:
            counts[error.robot_id] = counts.get(error.robot_id, 0) + 1
        return counts
        
    def _get_error_counts_by_type(self) -> Dict[str, int]:
        """Get error counts grouped by error type."""
        counts = {}
        for error in self._error_history:
            counts[error.error_type] = counts.get(error.error_type, 0) + 1
        return counts
        
    async def retry_with_backoff(self, func: Callable, *args, 
                                 error_info: ErrorInfo = None, **kwargs) -> Any:
        """
        Execute function with retry and backoff.
        
        Args:
            func: Function to execute
            *args: Function arguments
            error_info: Error info for tracking (optional)
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            The last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(error_info.max_retries + 1 if error_info else self.retry_config.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if error_info:
                    error_info.retry_count = attempt
                    
                # Calculate backoff
                backoff = self.calculate_backoff(attempt)
                
                if attempt < (error_info.max_retries if error_info else self.retry_config.max_retries):
                    self.logger.debug(
                        f"Retry {attempt + 1}/{error_info.max_retries if error_info else self.retry_config.max_retries} "
                        f"after {backoff}s backoff"
                    )
                    await asyncio.sleep(backoff)
                else:
                    self.logger.error(f"All retries exhausted after {attempt + 1} attempts")
                    
        raise last_exception
