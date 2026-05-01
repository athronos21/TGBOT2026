"""
Unit tests for ConfigurationManager

Tests configuration loading, environment variable substitution,
dynamic updates, and validation.
"""

import os
import pytest
import tempfile
import yaml
from pathlib import Path
from src.config.config_manager import ConfigurationManager


@pytest.fixture
def temp_config_file():
    """Create a temporary configuration file for testing."""
    config_data = {
        'system': {
            'name': 'Test System',
            'version': '1.0.0',
            'environment': '${ENVIRONMENT:development}'
        },
        'database': {
            'postgresql': {
                'host': '${DB_HOST:localhost}',
                'port': 5432,
                'user': '${DB_USER}',
                'password': '${DB_PASSWORD}'
            }
        },
        'mt5': {
            'password': '${MT5_PASSWORD}',
            'account_number': 12345
        },
        'risk': {
            'profile': 'moderate',
            'conservative': {
                'risk_per_trade': 0.5
            },
            'moderate': {
                'risk_per_trade': 1.0
            }
        },
        'trading': {
            'style': 'day_trading',
            'day_trading': {
                'close_all_by': '23:00'
            }
        },
        'robots': {
            'enabled': ['price_bot', 'structure_bot']
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
        
    yield temp_path
    
    # Cleanup
    os.unlink(temp_path)


class TestConfigurationManager:
    """Test suite for ConfigurationManager."""
    
    def test_load_config(self, temp_config_file):
        """Test basic configuration loading."""
        config = ConfigurationManager(temp_config_file)
        assert config.config is not None
        assert 'system' in config.config
        assert 'database' in config.config
        
    def test_env_var_substitution_with_value(self, temp_config_file):
        """Test environment variable substitution when variable is set."""
        os.environ['DB_USER'] = 'test_user'
        os.environ['DB_PASSWORD'] = 'test_password'
        
        config = ConfigurationManager(temp_config_file)
        
        assert config.get('database.postgresql.user') == 'test_user'
        assert config.get('database.postgresql.password') == 'test_password'
        
        # Cleanup
        del os.environ['DB_USER']
        del os.environ['DB_PASSWORD']
        
    def test_env_var_substitution_with_default(self, temp_config_file):
        """Test environment variable substitution with default value."""
        # Ensure ENVIRONMENT is not set
        if 'ENVIRONMENT' in os.environ:
            del os.environ['ENVIRONMENT']
            
        config = ConfigurationManager(temp_config_file)
        
        # Should use default value 'development'
        assert config.get('system.environment') == 'development'
        
    def test_env_var_substitution_without_default(self, temp_config_file):
        """Test environment variable substitution without default (empty string)."""
        # Ensure MT5_PASSWORD is not set
        if 'MT5_PASSWORD' in os.environ:
            del os.environ['MT5_PASSWORD']
            
        config = ConfigurationManager(temp_config_file)
        
        # Should be empty string when not set and no default
        assert config.get('mt5.password') == ''
        
    def test_env_var_substitution_override_default(self, temp_config_file):
        """Test that environment variable overrides default value."""
        os.environ['ENVIRONMENT'] = 'production'
        
        config = ConfigurationManager(temp_config_file)
        
        assert config.get('system.environment') == 'production'
        
        # Cleanup
        del os.environ['ENVIRONMENT']
        
    def test_get_with_dot_notation(self, temp_config_file):
        """Test getting values using dot notation."""
        config = ConfigurationManager(temp_config_file)
        
        assert config.get('database.postgresql.host') == 'localhost'
        assert config.get('database.postgresql.port') == 5432
        assert config.get('system.name') == 'Test System'
        
    def test_get_with_default(self, temp_config_file):
        """Test getting non-existent values with default."""
        config = ConfigurationManager(temp_config_file)
        
        assert config.get('nonexistent.key', 'default_value') == 'default_value'
        assert config.get('system.nonexistent', 42) == 42
        
    def test_set_value(self, temp_config_file):
        """Test setting configuration values."""
        config = ConfigurationManager(temp_config_file)
        
        config.set('risk.profile', 'aggressive')
        assert config.get('risk.profile') == 'aggressive'
        
        config.set('new.nested.value', 123)
        assert config.get('new.nested.value') == 123
        
    def test_update_multiple_values(self, temp_config_file):
        """Test updating multiple values at once."""
        config = ConfigurationManager(temp_config_file)
        
        updates = {
            'risk.profile': 'conservative',
            'trading.style': 'scalping',
            'system.version': '2.0.0'
        }
        
        config.update(updates)
        
        assert config.get('risk.profile') == 'conservative'
        assert config.get('trading.style') == 'scalping'
        assert config.get('system.version') == '2.0.0'
        
    def test_watcher_callback(self, temp_config_file):
        """Test configuration watcher callbacks."""
        config = ConfigurationManager(temp_config_file)
        
        callback_data = []
        
        def on_change(key, value):
            callback_data.append((key, value))
            
        config.watch('risk.profile', on_change)
        config.set('risk.profile', 'aggressive')
        
        assert len(callback_data) == 1
        assert callback_data[0] == ('risk.profile', 'aggressive')
        
    def test_get_risk_config(self, temp_config_file):
        """Test getting risk configuration for current profile."""
        config = ConfigurationManager(temp_config_file)
        
        risk_config = config.get_risk_config()
        assert risk_config['risk_per_trade'] == 1.0  # moderate profile
        
        config.set('risk.profile', 'conservative')
        risk_config = config.get_risk_config()
        assert risk_config['risk_per_trade'] == 0.5  # conservative profile
        
    def test_get_trading_config(self, temp_config_file):
        """Test getting trading configuration for current style."""
        config = ConfigurationManager(temp_config_file)
        
        trading_config = config.get_trading_config()
        assert trading_config['close_all_by'] == '23:00'  # day_trading style
        
    def test_is_robot_enabled(self, temp_config_file):
        """Test checking if robot is enabled."""
        config = ConfigurationManager(temp_config_file)
        
        assert config.is_robot_enabled('price_bot') is True
        assert config.is_robot_enabled('structure_bot') is True
        assert config.is_robot_enabled('nonexistent_bot') is False
        
    def test_validate_valid_config(self, temp_config_file):
        """Test validation of valid configuration."""
        config = ConfigurationManager(temp_config_file)
        
        assert config.validate() is True
        
    def test_validate_invalid_risk_profile(self, temp_config_file):
        """Test validation fails with invalid risk profile."""
        config = ConfigurationManager(temp_config_file)
        config.set('risk.profile', 'invalid_profile')
        
        with pytest.raises(ValueError, match="Invalid risk profile"):
            config.validate()
            
    def test_validate_invalid_trading_style(self, temp_config_file):
        """Test validation fails with invalid trading style."""
        config = ConfigurationManager(temp_config_file)
        config.set('trading.style', 'invalid_style')
        
        with pytest.raises(ValueError, match="Invalid trading style"):
            config.validate()
            
    def test_to_dict(self, temp_config_file):
        """Test converting configuration to dictionary."""
        config = ConfigurationManager(temp_config_file)
        
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert 'system' in config_dict
        assert 'database' in config_dict
        
    def test_nested_env_var_substitution(self, temp_config_file):
        """Test environment variable substitution in nested structures."""
        os.environ['DB_HOST'] = 'remote.server.com'
        
        config = ConfigurationManager(temp_config_file)
        
        assert config.get('database.postgresql.host') == 'remote.server.com'
        
        # Cleanup
        del os.environ['DB_HOST']
        
    def test_multiple_env_vars_in_config(self, temp_config_file):
        """Test multiple environment variables in configuration."""
        os.environ['DB_USER'] = 'admin'
        os.environ['DB_PASSWORD'] = 'secret123'
        os.environ['MT5_PASSWORD'] = 'mt5secret'
        
        config = ConfigurationManager(temp_config_file)
        
        assert config.get('database.postgresql.user') == 'admin'
        assert config.get('database.postgresql.password') == 'secret123'
        assert config.get('mt5.password') == 'mt5secret'
        
        # Cleanup
        del os.environ['DB_USER']
        del os.environ['DB_PASSWORD']
        del os.environ['MT5_PASSWORD']


class TestEnvironmentVariableSubstitution:
    """Dedicated tests for environment variable substitution."""
    
    def test_simple_substitution(self):
        """Test simple ${VAR} substitution."""
        config_mgr = ConfigurationManager.__new__(ConfigurationManager)
        
        os.environ['TEST_VAR'] = 'test_value'
        result = config_mgr._substitute_string('${TEST_VAR}')
        assert result == 'test_value'
        
        del os.environ['TEST_VAR']
        
    def test_substitution_with_default(self):
        """Test ${VAR:default} substitution."""
        config_mgr = ConfigurationManager.__new__(ConfigurationManager)
        
        # Variable not set, should use default
        if 'UNSET_VAR' in os.environ:
            del os.environ['UNSET_VAR']
            
        result = config_mgr._substitute_string('${UNSET_VAR:default_value}')
        assert result == 'default_value'
        
    def test_substitution_in_middle_of_string(self):
        """Test substitution in middle of string."""
        config_mgr = ConfigurationManager.__new__(ConfigurationManager)
        
        os.environ['HOST'] = 'example.com'
        result = config_mgr._substitute_string('https://${HOST}/api')
        assert result == 'https://example.com/api'
        
        del os.environ['HOST']
        
    def test_multiple_substitutions_in_string(self):
        """Test multiple substitutions in one string."""
        config_mgr = ConfigurationManager.__new__(ConfigurationManager)
        
        os.environ['USER'] = 'admin'
        os.environ['PASS'] = 'secret'
        result = config_mgr._substitute_string('${USER}:${PASS}')
        assert result == 'admin:secret'
        
        del os.environ['USER']
        del os.environ['PASS']
        
    def test_empty_default_value(self):
        """Test substitution with empty default value."""
        config_mgr = ConfigurationManager.__new__(ConfigurationManager)
        
        if 'UNSET_VAR' in os.environ:
            del os.environ['UNSET_VAR']
            
        result = config_mgr._substitute_string('${UNSET_VAR:}')
        assert result == ''
        
    def test_no_substitution_needed(self):
        """Test string without substitution patterns."""
        config_mgr = ConfigurationManager.__new__(ConfigurationManager)
        
        result = config_mgr._substitute_string('plain string')
        assert result == 'plain string'
        
    def test_recursive_dict_substitution(self):
        """Test substitution in nested dictionaries."""
        config_mgr = ConfigurationManager.__new__(ConfigurationManager)
        
        os.environ['DB_HOST'] = 'localhost'
        os.environ['DB_PORT'] = '5432'
        
        config = {
            'database': {
                'host': '${DB_HOST}',
                'port': '${DB_PORT}',
                'nested': {
                    'value': '${DB_HOST}:${DB_PORT}'
                }
            }
        }
        
        result = config_mgr.substitute_env_vars(config)
        
        assert result['database']['host'] == 'localhost'
        assert result['database']['port'] == '5432'
        assert result['database']['nested']['value'] == 'localhost:5432'
        
        del os.environ['DB_HOST']
        del os.environ['DB_PORT']
        
    def test_list_substitution(self):
        """Test substitution in lists."""
        config_mgr = ConfigurationManager.__new__(ConfigurationManager)
        
        os.environ['SYMBOL1'] = 'XAUUSD'
        os.environ['SYMBOL2'] = 'EURUSD'
        
        config = ['${SYMBOL1}', '${SYMBOL2}', 'GBPUSD']
        result = config_mgr.substitute_env_vars(config)
        
        assert result == ['XAUUSD', 'EURUSD', 'GBPUSD']
        
        del os.environ['SYMBOL1']
        del os.environ['SYMBOL2']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
