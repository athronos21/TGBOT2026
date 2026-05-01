"""
Configuration Manager for Multi-Robot Trading System

This module provides centralized configuration management with support for:
- YAML configuration files
- Environment variable substitution
- Dynamic configuration updates
- Configuration validation
- Configuration watching/callbacks
"""

import os
import re
import json
import yaml
import logging
from typing import Any, Dict, Callable, Optional, List
from pathlib import Path
from datetime import datetime


class ConfigurationManager:
    """
    Manages system configuration with support for environment variable substitution
    and dynamic updates.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the Configuration Manager.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.watchers: List[tuple] = []
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file and substitute environment variables.
        
        Returns:
            Loaded configuration dictionary
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            # Substitute environment variables
            self.config = self.substitute_env_vars(config)
            self.logger.info(f"Configuration loaded from {self.config_path}")
            
            return self.config
            
        except yaml.YAMLError as e:
            self.logger.error(f"Failed to parse YAML configuration: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise
            
    def substitute_env_vars(self, config: Any) -> Any:
        """
        Recursively substitute environment variables in configuration.
        
        Supports ${VAR_NAME} and ${VAR_NAME:default_value} syntax.
        
        Args:
            config: Configuration object (dict, list, or string)
            
        Returns:
            Configuration with substituted values
        """
        if isinstance(config, dict):
            return {key: self.substitute_env_vars(value) for key, value in config.items()}
        elif isinstance(config, list):
            return [self.substitute_env_vars(item) for item in config]
        elif isinstance(config, str):
            return self._substitute_string(config)
        else:
            return config
            
    def _substitute_string(self, value: str) -> str:
        """
        Substitute environment variables in a string.
        
        Args:
            value: String potentially containing ${VAR} patterns
            
        Returns:
            String with substituted values
        """
        # Pattern matches ${VAR} or ${VAR:default}
        pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
        
        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ''
            return os.getenv(var_name, default_value)
            
        return re.sub(pattern, replace_var, value)
        
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot-notation path.
        
        Args:
            key_path: Dot-separated path (e.g., 'database.postgresql.host')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
            
        Example:
            >>> config.get('mt5.broker')
            'IC Markets'
            >>> config.get('mt5.account_number', 0)
            12345678
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
                
        return value
        
    def set(self, key_path: str, value: Any) -> None:
        """
        Set configuration value using dot-notation path.
        
        Args:
            key_path: Dot-separated path
            value: Value to set
            
        Example:
            >>> config.set('risk.profile', 'aggressive')
        """
        keys = key_path.split('.')
        config = self.config
        
        # Navigate to the parent dictionary
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
            
        # Set the value
        config[keys[-1]] = value
        
        # Notify watchers
        self.notify_watchers(key_path, value)
        
        self.logger.info(f"Configuration updated: {key_path} = {value}")
        
    def update(self, updates: Dict[str, Any]) -> None:
        """
        Update multiple configuration values at once.
        
        Args:
            updates: Dictionary of key_path: value pairs
            
        Example:
            >>> config.update({
            ...     'risk.profile': 'conservative',
            ...     'trading.style': 'day_trading'
            ... })
        """
        for key_path, value in updates.items():
            self.set(key_path, value)
            
    def save_config(self, backup: bool = True) -> None:
        """
        Save current configuration to file.
        
        Args:
            backup: Whether to create a backup of the existing file
        """
        try:
            # Create backup if requested
            if backup and self.config_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self.config_path.with_suffix(f'.{timestamp}.yaml.bak')
                self.config_path.rename(backup_path)
                self.logger.info(f"Configuration backup created: {backup_path}")
                
            # Save configuration
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
                
            self.logger.info(f"Configuration saved to {self.config_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            raise
            
    def reload(self) -> None:
        """
        Reload configuration from file.
        """
        self.logger.info("Reloading configuration...")
        self.load_config()
        
        # Notify all watchers about reload
        for key_path, callback in self.watchers:
            value = self.get(key_path)
            callback(key_path, value)
            
    def watch(self, key_path: str, callback: Callable[[str, Any], None]) -> None:
        """
        Register a callback to be notified when a configuration value changes.
        
        Args:
            key_path: Dot-separated path to watch
            callback: Function to call when value changes (receives key_path and new value)
            
        Example:
            >>> def on_risk_change(key, value):
            ...     print(f"Risk profile changed to: {value}")
            >>> config.watch('risk.profile', on_risk_change)
        """
        self.watchers.append((key_path, callback))
        self.logger.debug(f"Watcher registered for: {key_path}")
        
    def unwatch(self, key_path: str, callback: Callable[[str, Any], None]) -> None:
        """
        Unregister a configuration watcher.
        
        Args:
            key_path: Dot-separated path
            callback: Callback function to remove
        """
        self.watchers = [(k, c) for k, c in self.watchers if not (k == key_path and c == callback)]
        self.logger.debug(f"Watcher unregistered for: {key_path}")
        
    def notify_watchers(self, key_path: str, value: Any) -> None:
        """
        Notify all watchers interested in a configuration change.
        
        Args:
            key_path: Path that changed
            value: New value
        """
        for watched_path, callback in self.watchers:
            # Exact match or parent path match
            if key_path == watched_path or key_path.startswith(watched_path + '.'):
                try:
                    callback(key_path, value)
                except Exception as e:
                    self.logger.error(f"Error in watcher callback for {key_path}: {e}")
                    
    def validate(self) -> bool:
        """
        Validate configuration structure and required fields.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        required_sections = ['system', 'mt5', 'trading', 'risk', 'database', 'robots']
        
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")
                
        # Validate risk profile
        risk_profile = self.get('risk.profile')
        if risk_profile not in ['conservative', 'moderate', 'aggressive']:
            raise ValueError(f"Invalid risk profile: {risk_profile}")
            
        # Validate trading style
        trading_style = self.get('trading.style')
        if trading_style not in ['scalping', 'day_trading', 'swing_trading']:
            raise ValueError(f"Invalid trading style: {trading_style}")
            
        self.logger.info("Configuration validation passed")
        return True
        
    def get_risk_config(self) -> Dict[str, float]:
        """
        Get current risk configuration based on selected profile.
        
        Returns:
            Dictionary with risk parameters
        """
        profile = self.get('risk.profile', 'moderate')
        return self.get(f'risk.{profile}', {})
        
    def get_trading_config(self) -> Dict[str, Any]:
        """
        Get current trading configuration based on selected style.
        
        Returns:
            Dictionary with trading parameters
        """
        style = self.get('trading.style', 'day_trading')
        return self.get(f'trading.{style}', {})
        
    def get_robot_config(self, robot_id: str) -> Dict[str, Any]:
        """
        Get configuration for a specific robot.
        
        Args:
            robot_id: Robot identifier
            
        Returns:
            Robot configuration dictionary
        """
        return self.get(f'robots.{robot_id}', {})
        
    def is_robot_enabled(self, robot_id: str) -> bool:
        """
        Check if a robot is enabled.
        
        Args:
            robot_id: Robot identifier
            
        Returns:
            True if robot is enabled
        """
        enabled_robots = self.get('robots.enabled', [])
        return robot_id in enabled_robots
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Get the entire configuration as a dictionary.
        
        Returns:
            Configuration dictionary
        """
        return self.config.copy()
        
    def __repr__(self) -> str:
        return f"ConfigurationManager(config_path='{self.config_path}')"
