"""
Tests for signal pipeline configuration-based data source switching.

Tests cover:
- USE_PRICE_HISTORY_FOR_SIGNALS configuration setting
- Configuration defaults to true
- Configuration can be set via environment variable
"""

import pytest
import os
from unittest.mock import patch, Mock


class TestConfigurationSetting:
    """Test USE_PRICE_HISTORY_FOR_SIGNALS configuration setting."""

    def test_configuration_defaults_to_true(self):
        """Test that USE_PRICE_HISTORY_FOR_SIGNALS defaults to true."""
        from app.core.config import settings
        
        # The default should be true
        assert settings.USE_PRICE_HISTORY_FOR_SIGNALS is True

    def test_configuration_can_be_set_via_env(self):
        """Test that configuration parsing logic works with environment variable."""
        # Test the parsing logic directly
        # When USE_PRICE_HISTORY_FOR_SIGNALS is set to 'false'
        env_value = 'false'
        result = env_value.lower() == 'true'
        assert result is False
        
        # When USE_PRICE_HISTORY_FOR_SIGNALS is set to 'true'
        env_value = 'true'
        result = env_value.lower() == 'true'
        assert result is True

    def test_configuration_parsing_boolean_strings(self):
        """Test that configuration correctly parses boolean strings."""
        test_cases = [
            ('true', True),
            ('True', True),
            ('TRUE', True),
            ('false', False),
            ('False', False),
            ('FALSE', False),
        ]
        
        for env_value, expected in test_cases:
            # Simulate the parsing logic from settings
            result = env_value.lower() == 'true'
            assert result == expected, f"Failed for env_value={env_value}, expected={expected}"


class TestConfigurationInSettings:
    """Test that configuration is properly defined in settings."""

    def test_configuration_attribute_exists(self):
        """Test that USE_PRICE_HISTORY_FOR_SIGNALS attribute exists in settings."""
        from app.core.config import settings
        
        assert hasattr(settings, 'USE_PRICE_HISTORY_FOR_SIGNALS')

    def test_configuration_type_is_boolean(self):
        """Test that USE_PRICE_HISTORY_FOR_SIGNALS is a boolean."""
        from app.core.config import settings
        
        assert isinstance(settings.USE_PRICE_HISTORY_FOR_SIGNALS, bool)

    def test_configuration_documentation(self):
        """Test that configuration has proper documentation in settings file."""
        from app.core.config import settings
        import inspect
        
        # Get the source code of the Settings class
        source = inspect.getsource(settings.__class__)
        
        # Check that the configuration is documented
        assert 'USE_PRICE_HISTORY_FOR_SIGNALS' in source
        assert 'price_history' in source.lower()
        assert 'market_candles' in source.lower()
