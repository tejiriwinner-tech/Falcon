"""
Alpha Vantage Provider Tests (Phase 8.1)
Tests for the Alpha Vantage provider implementation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from app.core.providers.alpha_vantage_provider import AlphaVantageProvider
from app.schemas.provider_models import ProviderCapability, ProviderHealth, ProviderStatus


class TestAlphaVantageProviderInitialization:
    """Test Alpha Vantage provider initialization."""
    
    def test_provider_metadata(self):
        """Test provider metadata is correctly set."""
        provider = AlphaVantageProvider()
        
        assert provider.PROVIDER_ID == "alpha_vantage"
        assert provider.PROVIDER_NAME == "Alpha Vantage"
        assert provider.PROVIDER_VERSION == "1.0.0"
        assert provider.provider_id == "alpha_vantage"
        assert provider.provider_name == "Alpha Vantage"
        assert provider.priority == 2
    
    def test_capabilities(self):
        """Test provider capabilities."""
        provider = AlphaVantageProvider()
        
        assert ProviderCapability.LIVE_PRICE in provider.capabilities
        assert ProviderCapability.MARKET_SESSION in provider.capabilities
        assert ProviderCapability.SYMBOL_INFORMATION in provider.capabilities


class TestAlphaVantageProviderConnection:
    """Test Alpha Vantage provider connection handling."""
    
    def test_connect_with_api_key(self):
        """Test successful connection with API key."""
        provider = AlphaVantageProvider()
        provider._api_key = "test_key"
        
        result = provider.connect()
        
        assert result is True
        assert provider._connected is True
        assert provider._is_healthy is True
    
    def test_connect_without_api_key(self):
        """Test connection failure without API key."""
        provider = AlphaVantageProvider()
        provider._api_key = None
        
        result = provider.connect()
        
        assert result is False
        assert provider._connected is False
        assert provider._is_healthy is False
    
    def test_disconnect(self):
        """Test disconnect."""
        provider = AlphaVantageProvider()
        provider._connected = True
        
        provider.disconnect()
        
        assert provider._connected is False
    
    def test_set_healthy(self):
        """Test force health status."""
        provider = AlphaVantageProvider()
        
        provider.set_healthy(False)
        assert provider._is_healthy is False
        
        provider.set_healthy(True)
        assert provider._is_healthy is True


class TestAlphaVantageProviderHealthCheck:
    """Test Alpha Vantage provider health check."""
    
    def test_health_check_healthy(self):
        """Test health check returns HEALTHY when everything is good."""
        provider = AlphaVantageProvider()
        provider._connected = True
        provider._is_healthy = True
        provider._api_key = "test_key"
        provider._cb_state = "CLOSED"
        
        health = provider.health_check()
        
        assert health == ProviderHealth.HEALTHY
    
    def test_health_check_critical_no_api_key(self):
        """Test health check returns CRITICAL without API key."""
        provider = AlphaVantageProvider()
        provider._api_key = None
        
        health = provider.health_check()
        
        assert health == ProviderHealth.CRITICAL
    
    def test_health_check_critical_not_connected(self):
        """Test health check returns CRITICAL when not connected."""
        provider = AlphaVantageProvider()
        provider._connected = False
        
        health = provider.health_check()
        
        assert health == ProviderHealth.CRITICAL
    
    def test_health_check_warning_half_open(self):
        """Test health check returns WARNING in HALF_OPEN state."""
        provider = AlphaVantageProvider()
        provider._connected = True
        provider._is_healthy = True
        provider._api_key = "test_key"
        provider._cb_state = "HALF_OPEN"
        
        health = provider.health_check()
        
        assert health == ProviderHealth.WARNING
    
    def test_health_check_critical_open(self):
        """Test health check returns CRITICAL in OPEN state."""
        provider = AlphaVantageProvider()
        provider._connected = True
        provider._is_healthy = True
        provider._api_key = "test_key"
        provider._cb_state = "OPEN"
        
        health = provider.health_check()
        
        assert health == ProviderHealth.CRITICAL


class TestAlphaVantageProviderFetchXAU:
    """Test Alpha Vantage provider XAU/USD fetching."""
    
    @patch('app.core.providers.alpha_vantage_provider.requests.Session.get')
    def test_fetch_xau_success(self, mock_get):
        """Test successful XAU/USD fetch."""
        provider = AlphaVantageProvider()
        provider._connected = True
        provider._is_healthy = True
        provider._api_key = "test_key"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "price": "2345.67",
            "timestamp": "2026-08-08 20:00:00"
        }
        mock_get.return_value = mock_response
        
        result = provider.fetch("XAUUSD")
        
        assert result is not None
        assert result["symbol"] == "XAUUSD"
        assert result["providerId"] == "alpha_vantage"
        assert result["mid"] == 2345.67
        assert result["bid"] == 2345.67
        assert result["ask"] == 2345.67
    
    @patch('app.core.providers.alpha_vantage_provider.requests.Session.get')
    def test_fetch_xau_error_response(self, mock_get):
        """Test XAU/USD fetch with API error."""
        provider = AlphaVantageProvider()
        provider._connected = True
        provider._is_healthy = True
        provider._api_key = "test_key"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Error Message": "Invalid API key"
        }
        mock_get.return_value = mock_response
        
        result = provider.fetch("XAUUSD")
        
        assert result is None
    
    @patch('app.core.providers.alpha_vantage_provider.requests.Session.get')
    def test_fetch_xau_http_error(self, mock_get):
        """Test XAU/USD fetch with HTTP error."""
        provider = AlphaVantageProvider()
        provider._connected = True
        provider._is_healthy = True
        provider._api_key = "test_key"
        
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        result = provider.fetch("XAUUSD")
        
        assert result is None


class TestAlphaVantageProviderFetchGBP:
    """Test Alpha Vantage provider GBP/USD fetching."""
    
    @patch('app.core.providers.alpha_vantage_provider.requests.Session.get')
    def test_fetch_gbp_success(self, mock_get):
        """Test successful GBP/USD fetch."""
        provider = AlphaVantageProvider()
        provider._connected = True
        provider._is_healthy = True
        provider._api_key = "test_key"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Meta Data": {},
            "Time Series FX (Daily)": {
                "2026-08-07": {
                    "1. open": "1.34510",
                    "2. high": "1.35080",
                    "3. low": "1.34310",
                    "4. close": "1.34880"
                }
            }
        }
        mock_get.return_value = mock_response
        
        result = provider.fetch("GBPUSD")
        
        assert result is not None
        assert result["symbol"] == "GBPUSD"
        assert result["providerId"] == "alpha_vantage"
        assert result["mid"] == 1.3488
        assert result["change"] != 0.0
    
    @patch('app.core.providers.alpha_vantage_provider.requests.Session.get')
    def test_fetch_gbp_no_data(self, mock_get):
        """Test GBP/USD fetch with no time series data."""
        provider = AlphaVantageProvider()
        provider._connected = True
        provider._is_healthy = True
        provider._api_key = "test_key"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Meta Data": {},
            "Time Series FX (Daily)": {}
        }
        mock_get.return_value = mock_response
        
        result = provider.fetch("GBPUSD")
        
        assert result is None


class TestAlphaVantageProviderUnsupportedSymbol:
    """Test Alpha Vantage provider with unsupported symbols."""
    
    def test_fetch_unsupported_symbol(self):
        """Test fetch with unsupported symbol."""
        provider = AlphaVantageProvider()
        provider._connected = True
        provider._is_healthy = True
        provider._api_key = "test_key"
        
        result = provider.fetch("UNKNOWN")
        
        assert result is None


class TestAlphaVantageProviderCircuitBreaker:
    """Test Alpha Vantage provider circuit breaker."""
    
    def test_circuit_breaker_transitions(self):
        """Test circuit breaker state transitions."""
        provider = AlphaVantageProvider()
        
        # Initially CLOSED
        assert provider._cb_state == "CLOSED"
        
        # Transition to OPEN
        provider._transition_to_open("test")
        assert provider._cb_state == "OPEN"
        assert provider._cb_opened_at is not None
        
        # Transition to HALF_OPEN
        provider._transition_to_half_open()
        assert provider._cb_state == "HALF_OPEN"
        
        # Transition to CLOSED
        provider._transition_to_closed("test")
        assert provider._cb_state == "CLOSED"
        assert provider._consecutive_failures == 0
    
    def test_increment_failure_opens_circuit(self):
        """Test that consecutive failures open the circuit."""
        provider = AlphaVantageProvider()
        provider._consecutive_failures = 2  # Below threshold
        
        # Increment to threshold
        provider._increment_failure()
        
        assert provider._consecutive_failures == 3
        assert provider._cb_state == "OPEN"


class TestAlphaVantageProviderSupports:
    """Test Alpha Vantage provider capability checks."""
    
    def test_supports_live_price(self):
        """Test provider supports LIVE_PRICE."""
        provider = AlphaVantageProvider()
        
        assert provider.supports(ProviderCapability.LIVE_PRICE) is True
    
    def test_supports_market_session(self):
        """Test provider supports MARKET_SESSION."""
        provider = AlphaVantageProvider()
        
        assert provider.supports(ProviderCapability.MARKET_SESSION) is True
    
    def test_does_not_support_historical_candles(self):
        """Test provider does not support HISTORICAL_CANDLES."""
        provider = AlphaVantageProvider()
        
        assert provider.supports(ProviderCapability.HISTORICAL_CANDLES) is False


class TestAlphaVantageProviderGetMetadata:
    """Test Alpha Vantage provider metadata."""
    
    def test_get_metadata_online(self):
        """Test metadata when provider is online."""
        provider = AlphaVantageProvider()
        provider._connected = True
        provider._is_healthy = True
        provider._api_key = "test_key"
        
        metadata = provider.get_metadata()
        
        assert metadata.providerId == "alpha_vantage"
        assert metadata.providerName == "Alpha Vantage"
        assert metadata.providerVersion == "1.0.0"
        assert metadata.status == ProviderStatus.ONLINE
        assert metadata.health == ProviderHealth.HEALTHY
    
    def test_get_metadata_offline(self):
        """Test metadata when provider is offline."""
        provider = AlphaVantageProvider()
        provider._connected = False
        
        metadata = provider.get_metadata()
        
        assert metadata.status == ProviderStatus.OFFLINE
        assert metadata.health == ProviderHealth.CRITICAL
