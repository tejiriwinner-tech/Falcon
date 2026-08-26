"""
Phase 7.2 Milestone 2 - Alpaca Configuration Tests
Tests that Alpaca configuration loads correctly and feature flag works.
"""
import pytest
from app.core.config.settings import Settings


class TestAlpacaConfiguration:
    """Test Alpaca configuration loading."""

    def test_alpaca_api_key_exists(self):
        """Test that ALPACA_API_KEY setting exists."""
        new_settings = Settings()
        assert hasattr(new_settings, 'ALPACA_API_KEY')

    def test_alpaca_secret_key_exists(self):
        """Test that ALPACA_SECRET_KEY setting exists."""
        new_settings = Settings()
        assert hasattr(new_settings, 'ALPACA_SECRET_KEY')

    def test_alpaca_base_url_has_default(self):
        """Test that ALPACA_BASE_URL has a default value."""
        new_settings = Settings()
        assert new_settings.ALPACA_BASE_URL == "https://data.alpaca.markets"

    def test_alpaca_base_url_exists(self):
        """Test that ALPACA_BASE_URL setting exists."""
        new_settings = Settings()
        assert hasattr(new_settings, 'ALPACA_BASE_URL')

    def test_enable_alpaca_provider_defaults_to_false(self):
        """Test that ENABLE_ALPACA_PROVIDER defaults to False."""
        new_settings = Settings()
        assert new_settings.ENABLE_ALPACA_PROVIDER is False

    def test_enable_alpaca_provider_exists(self):
        """Test that ENABLE_ALPACA_PROVIDER feature flag exists."""
        new_settings = Settings()
        assert hasattr(new_settings, 'ENABLE_ALPACA_PROVIDER')

    def test_enable_alpaca_provider_is_boolean(self):
        """Test that ENABLE_ALPACA_PROVIDER is a boolean."""
        new_settings = Settings()
        assert isinstance(new_settings.ENABLE_ALPACA_PROVIDER, bool)

    def test_existing_providers_unaffected(self):
        """Test that existing provider configurations are unaffected."""
        new_settings = Settings()
        assert new_settings.TWELVEDATA_BASE_URL == "https://api.twelvedata.com"
