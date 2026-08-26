"""
Phase 7.2 Milestone 1 - Alpaca Provider Registry Tests
Tests that AlpacaProvider registration works correctly with feature flag.
"""
import pytest
from app.core.providers.provider_registry import provider_registry


class TestExistingProvidersRegistration:
    """Test that existing providers remain registered."""

    def test_twelve_data_registered(self):
        """Test that TwelveData is still registered."""
        twelve_data = provider_registry.get("twelve_data")
        assert twelve_data is not None
        assert twelve_data.provider_id == "twelve_data"

    def test_alpha_vantage_registered(self):
        """Test that Alpha Vantage (current secondary/fallback) is registered."""
        alpha_vantage = provider_registry.get("alpha_vantage")
        assert alpha_vantage is not None
        assert alpha_vantage.provider_id == "alpha_vantage"
        # Yahoo Finance has been completely removed from the registry
        assert provider_registry.get("yahoo_finance") is None

    def test_mock_price_registered(self):
        """Test that Mock Price is still registered."""
        mock = provider_registry.get("mock_provider")
        assert mock is not None
        assert mock.provider_id == "mock_provider"

    def test_all_existing_providers_registered(self):
        """Test that all current production providers are registered."""
        providers = provider_registry.all_providers()
        provider_ids = [p.provider_id for p in providers]

        # Current architecture: TwelveData (primary) → Alpha Vantage (fallback) → Mock (final)
        expected_providers = ["twelve_data", "alpha_vantage", "mock_provider"]
        for provider_id in expected_providers:
            assert provider_id in provider_ids

        # Yahoo Finance has been completely removed
        assert "yahoo_finance" not in provider_ids


class TestProviderPriority:
    """Test provider priority ordering."""

    def test_twelve_data_is_priority_1(self):
        """Test that TwelveData has priority 1."""
        twelve_data = provider_registry.get("twelve_data")
        assert twelve_data.priority == 1

    def test_alpha_vantage_is_fallback_priority(self):
        """Test that Alpha Vantage is prioritized below Twelve Data."""
        from app.core.config import settings

        twelve_data = provider_registry.get("twelve_data")
        alpha_vantage = provider_registry.get("alpha_vantage")
        assert twelve_data is not None and twelve_data.priority == 1
        assert alpha_vantage is not None

        # Current fallback wiring in app/core/providers/__init__.py:
        #   Alpaca disabled → twelve_data(1), alpha_vantage(2), mock(3)
        #   Alpaca enabled  → twelve_data(1), alpaca(2), alpha_vantage(3), mock(4)
        expected_priority = 3 if settings.ENABLE_ALPACA_PROVIDER else 2
        assert alpha_vantage.priority == expected_priority
        assert alpha_vantage.priority > twelve_data.priority  # never outranks the primary


class TestAlpacaProviderNotRegisteredWhenDisabled:
    """Test that AlpacaProvider is not registered when feature flag is disabled."""

    def test_alpaca_not_registered_when_disabled(self):
        """Test that AlpacaProvider is not registered when ENABLE_ALPACA_PROVIDER is false."""
        # Current state: ENABLE_ALPACA_PROVIDER should be false by default
        alpaca = provider_registry.get("alpaca")
        assert alpaca is None

    def test_provider_order_without_alpaca(self):
        """Test that provider order is correct when Alpaca is disabled."""
        from app.core.config import settings

        providers = provider_registry.all_providers()
        provider_ids = [p.provider_id for p in providers]

        # Current architecture order (see app/core/providers/__init__.py wiring):
        #   Alpaca disabled → twelve_data, alpha_vantage, mock_provider
        #   Alpaca enabled  → twelve_data, alpaca, alpha_vantage, mock_provider
        assert provider_ids[0] == "twelve_data"
        assert provider_ids[-1] == "mock_provider"
        assert "alpha_vantage" in provider_ids
        # Yahoo Finance has been completely removed
        assert "yahoo_finance" not in provider_ids

        if settings.ENABLE_ALPACA_PROVIDER:
            expected_order = ["twelve_data", "alpaca", "alpha_vantage", "mock_provider"]
        else:
            expected_order = ["twelve_data", "alpha_vantage", "mock_provider"]
            # Alpaca should not be in the list
            assert "alpaca" not in provider_ids
        assert provider_ids == expected_order