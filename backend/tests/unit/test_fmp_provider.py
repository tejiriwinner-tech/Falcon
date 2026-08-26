"""
FMP Provider Tests (Phase 8.2.1)
Tests for the Financial Modeling Prep provider implementation.
"""
import time
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from app.core.providers.fmp_provider import FmpProvider
from app.core.config import settings
from app.schemas.provider_models import ProviderCapability, ProviderHealth, ProviderStatus


class TestFmpProviderInitialization:
    """Test FMP provider initialization."""
    
    def test_provider_metadata(self):
        """Test provider metadata is correctly set."""
        provider = FmpProvider(api_key="test_key")
        
        assert provider.PROVIDER_ID == "fmp"
        assert provider.PROVIDER_NAME == "Financial Modeling Prep"
        assert provider.PROVIDER_VERSION == "1.0.0"
        assert provider.provider_id == "fmp"
        assert provider.provider_name == "Financial Modeling Prep"
        assert provider.priority == 2
    
    def test_capabilities(self):
        """Test provider capabilities."""
        provider = FmpProvider(api_key="test_key")
        
        assert ProviderCapability.LIVE_PRICE in provider.capabilities
        assert ProviderCapability.SPREAD in provider.capabilities
        assert ProviderCapability.MARKET_SESSION in provider.capabilities
        assert ProviderCapability.SYMBOL_INFORMATION in provider.capabilities


class TestFmpProviderConnection:
    """Test FMP provider connection handling."""
    
    def test_connect_with_api_key(self):
        """Test successful connection with API key."""
        provider = FmpProvider(api_key="test_key")
        
        result = provider.connect()
        
        assert result is True
        assert provider._connected is True
    
    def test_connect_without_api_key(self, monkeypatch):
        """Test connection failure without API key.

        Phase 8.3.1 (security hardening): the test configuration is explicitly
        isolated — ``settings.FMP_API_KEY`` is cleared so that
        ``FmpProvider(api_key=None)`` deterministically represents an absent
        credential and can never consume the developer's real production key
        from ``backend/.env``. Assertions are presence-only (never print/compare
        the credential value itself).
        """
        monkeypatch.setattr(settings, "FMP_API_KEY", None)
        provider = FmpProvider(api_key=None)

        result = provider.connect()

        assert result is False
        assert provider._connected is False
        assert provider._api_key is None
    
    def test_disconnect(self):
        """Test disconnect."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        
        provider.disconnect()
        
        assert provider._connected is False


class TestFmpProviderHealthCheck:
    """Test FMP provider health check."""
    
    def test_health_check_healthy(self):
        """Test health check returns HEALTHY when connected."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        provider._cb_state = "CLOSED"
        
        health = provider.health_check()
        
        assert health == ProviderHealth.HEALTHY
    
    def test_health_check_critical_no_api_key(self):
        """Test health check returns CRITICAL without API key."""
        provider = FmpProvider(api_key=None)
        provider._connected = False
        
        health = provider.health_check()
        
        assert health == ProviderHealth.CRITICAL
    
    def test_health_check_critical_circuit_open(self):
        """Test health check returns CRITICAL when circuit is OPEN."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        provider._cb_state = "OPEN"
        
        health = provider.health_check()
        
        assert health == ProviderHealth.CRITICAL
    
    def test_health_check_warning_circuit_half_open(self):
        """Test health check returns WARNING when circuit is HALF_OPEN."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        provider._cb_state = "HALF_OPEN"
        
        health = provider.health_check()
        
        assert health == ProviderHealth.WARNING


class TestFmpProviderCircuitBreaker:
    """Test FMP provider circuit breaker."""
    
    def test_initial_state_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        provider = FmpProvider(api_key="test_key")
        
        assert provider.circuit_breaker_state == "CLOSED"
    
    def test_circuit_opens_after_threshold_failures(self):
        """Test circuit opens after threshold consecutive failures."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        
        # Simulate failures
        for _ in range(3):
            provider._cb_record_failure()
        
        assert provider.circuit_breaker_state == "OPEN"
    
    def test_circuit_blocks_when_open(self):
        """Test circuit blocks requests when OPEN (cooldown not elapsed)."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        provider._cb_state = "OPEN"
        provider._cb_opened_at = time.monotonic()  # Set in the past (no cooldown elapsed)
        
        # Should block because cooldown has NOT elapsed
        assert provider._cb_should_block() is True
    
    def test_circuit_allows_trial_after_cooldown(self):
        """Test circuit allows trial after cooldown."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        provider._cb_state = "OPEN"
        provider._cb_opened_at = 0  # Set in the far past
        
        # Should allow trial (not block)
        assert provider._cb_should_block() is False
    
    def test_circuit_closes_after_success(self):
        """Test circuit closes after successful request."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        provider._cb_state = "OPEN"
        provider._consecutive_failures = 3
        
        provider._cb_record_success()
        
        assert provider.circuit_breaker_state == "CLOSED"
        assert provider._consecutive_failures == 0


class TestFmpProviderFetch:
    """Test FMP provider fetch functionality."""
    
    @patch('app.core.providers.fmp_provider.requests.Session.get')
    def test_fetch_xau_success(self, mock_get):
        """Test successful XAU/USD fetch."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "symbol": "XAUUSD",
                "price": 2345.67,
                "changesPercentage": 1.25,
                "change": 28.90,
                "timestamp": 1699123200
            }
        ]
        mock_get.return_value = mock_response
        
        result = provider.fetch("XAUUSD")
        
        assert result is not None
        assert result["symbol"] == "XAUUSD"
        assert result["providerId"] == "fmp"
        assert result["lastPrice"] == 2345.67
        assert result["mid"] == 2345.67

    @patch('app.core.providers.fmp_provider.requests.Session.get')
    def test_fetch_gbp_success(self, mock_get):
        """Test successful GBP/USD fetch."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "symbol": "GBPUSD",
                "price": 1.34880,
                "changesPercentage": -0.15,
                "change": -0.00203,
                "timestamp": 1699123200
            }
        ]
        mock_get.return_value = mock_response
        
        result = provider.fetch("GBPUSD")
        
        assert result is not None
        assert result["symbol"] == "GBPUSD"
        assert result["providerId"] == "fmp"

    @patch('app.core.providers.fmp_provider.requests.Session.get')
    def test_fetch_with_bid_ask(self, mock_get):
        """Test fetch when FMP returns bid/ask fields."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "symbol": "EURUSD",
                "price": 1.08560,
                "bid": 1.08555,
                "ask": 1.08565,
                "changesPercentage": 0.30,
                "change": 0.00325,
                "timestamp": 1699123200
            }
        ]
        mock_get.return_value = mock_response
        
        result = provider.fetch("EURUSD")
        
        assert result is not None
        assert result["bid"] == 1.08555
        assert result["ask"] == 1.08565
        assert result["spread"] == 0.0001

    @patch('app.core.providers.fmp_provider.requests.Session.get')
    def test_fetch_no_api_key(self, mock_get, monkeypatch):
        """Test fetch returns None without API key.

        Phase 8.3.1 (security hardening): the test configuration is explicitly
        isolated — ``settings.FMP_API_KEY`` is cleared so the test
        deterministically represents ``FMP_API_KEY = absent`` without reading the
        developer's real production credential, and no HTTP call may be made.
        """
        monkeypatch.setattr(settings, "FMP_API_KEY", None)
        provider = FmpProvider(api_key=None)
        provider._connected = True
        
        result = provider.fetch("XAUUSD")
        
        assert result is None
        assert provider._api_key is None
        mock_get.assert_not_called()

    @patch('app.core.providers.fmp_provider.requests.Session.get')
    def test_fetch_not_connected(self, mock_get):
        """Test fetch returns None when not connected."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = False
        
        result = provider.fetch("XAUUSD")
        
        assert result is None
        mock_get.assert_not_called()

    @patch('app.core.providers.fmp_provider.requests.Session.get')
    def test_fetch_circuit_open(self, mock_get):
        """Test fetch returns None when circuit is OPEN (cooldown not elapsed)."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        provider._cb_state = "OPEN"
        provider._cb_opened_at = time.monotonic()  # Cooldown has NOT elapsed
        
        result = provider.fetch("XAUUSD")
        
        assert result is None
        mock_get.assert_not_called()

    @patch('app.core.providers.fmp_provider.requests.Session.get')
    def test_fetch_rate_limit_429(self, mock_get):
        """Test fetch handles HTTP 429 rate limit and opens circuit after threshold."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        
        # Simulate 3 consecutive 429s to trigger circuit open
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response
        
        for _ in range(3):
            provider.fetch("XAUUSD")
        
        assert provider.circuit_breaker_state == "OPEN"
        assert provider.circuit_breaker_state == "OPEN"

    @patch('app.core.providers.fmp_provider.requests.Session.get')
    def test_fetch_http_error(self, mock_get):
        """Test fetch handles HTTP error."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response
        
        result = provider.fetch("XAUUSD")
        
        assert result is None

    @patch('app.core.providers.fmp_provider.requests.Session.get')
    def test_fetch_api_error_message(self, mock_get):
        """Test fetch handles API error message in response."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Error Message": "Invalid API key"
        }
        mock_get.return_value = mock_response
        
        result = provider.fetch("XAUUSD")
        
        assert result is None

    @patch('app.core.providers.fmp_provider.requests.Session.get')
    def test_fetch_empty_response(self, mock_get):
        """Test fetch handles empty response array."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response
        
        result = provider.fetch("XAUUSD")
        
        assert result is None

    @patch('app.core.providers.fmp_provider.requests.Session.get')
    def test_fetch_timeout(self, mock_get):
        """Test fetch handles timeout."""
        import requests
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        
        mock_get.side_effect = requests.Timeout("Request timed out")
        
        result = provider.fetch("XAUUSD")
        
        assert result is None

    @patch('app.core.providers.fmp_provider.requests.Session.get')
    def test_fetch_connection_error(self, mock_get):
        """Test fetch handles connection error."""
        import requests
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        
        mock_get.side_effect = requests.ConnectionError("Connection failed")
        
        result = provider.fetch("XAUUSD")
        
        assert result is None


class TestFmpProviderMetadata:
    """Test FMP provider metadata."""
    
    def test_get_metadata(self):
        """Test get_metadata returns correct metadata."""
        provider = FmpProvider(api_key="test_key")
        provider._connected = True
        
        metadata = provider.get_metadata()
        
        assert metadata.providerId == "fmp"
        assert metadata.providerName == "Financial Modeling Prep"
        assert metadata.providerVersion == "1.0.0"
        assert metadata.status == ProviderStatus.ONLINE
        assert metadata.health == ProviderHealth.HEALTHY

    def test_supports_capability(self):
        """Test supports method."""
        provider = FmpProvider(api_key="test_key")
        
        assert provider.supports(ProviderCapability.LIVE_PRICE) is True
        assert provider.supports(ProviderCapability.SPREAD) is True
        assert provider.supports(ProviderCapability.MARKET_SESSION) is True
        assert provider.supports(ProviderCapability.SYMBOL_INFORMATION) is True

    def test_get_statistics(self):
        """Test get_statistics returns statistics."""
        provider = FmpProvider(api_key="test_key")
        
        stats = provider.get_statistics()
        
        assert stats.totalRequests == 0
        assert stats.successfulRequests == 0
        assert stats.failedRequests == 0
        assert stats.successRate == 100.0
        assert stats.circuitBreakerState == "CLOSED"