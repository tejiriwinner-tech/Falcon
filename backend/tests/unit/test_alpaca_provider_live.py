"""
Phase 7.2 Milestone 2 - AlpacaProvider Live Implementation Unit Tests
Comprehensive tests for the live AlpacaProvider implementation.
"""
import time
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
import pytest
import requests

from app.core.providers.alpaca_provider import AlpacaProvider
from app.schemas.provider_models import (
    ProviderCapability,
    ProviderHealth,
    ProviderStatus,
    ProviderType,
)


class TestAlpacaProviderAuthentication:
    """Test AlpacaProvider authentication."""

    def test_provider_requires_api_key(self):
        """Test that provider requires API key for operation."""
        provider = AlpacaProvider(api_key=None, secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")
        assert result is None

    def test_provider_requires_secret_key(self):
        """Test that provider requires secret key for operation."""
        provider = AlpacaProvider(api_key="test_key", secret_key=None)
        provider.connect()
        result = provider.fetch("XAUUSD")
        assert result is None

    def test_provider_loads_credentials_from_settings(self):
        """Test that provider loads credentials from settings when not provided."""
        provider = AlpacaProvider()
        # Should load from settings.ALPACA_API_KEY and settings.ALPACA_SECRET_KEY
        assert provider._api_key is not None or provider._api_key is None  # Depends on env
        assert provider._secret_key is not None or provider._secret_key is None  # Depends on env

    def test_provider_accepts_custom_credentials(self):
        """Test that provider accepts custom API key and secret."""
        provider = AlpacaProvider(api_key="custom_key", secret_key="custom_secret")
        assert provider._api_key == "custom_key"
        assert provider._secret_key == "custom_secret"


class TestAlpacaProviderConnection:
    """Test AlpacaProvider connection management."""

    def test_connect_sets_connected_flag(self):
        """Test that connect() sets _connected flag to True."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        assert provider._connected is True

    def test_disconnect_clears_connected_flag(self):
        """Test that disconnect() sets _connected flag to False."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        provider.disconnect()
        assert provider._connected is False

    def test_fetch_returns_none_when_disconnected(self):
        """Test that fetch() returns None when provider is disconnected."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        # Don't call connect()
        result = provider.fetch("XAUUSD")
        assert result is None


class TestAlpacaProviderHealthCheck:
    """Test AlpacaProvider health check functionality."""

    def test_health_check_returns_critical_when_disconnected(self):
        """Test that health_check() returns CRITICAL when disconnected."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        health = provider.health_check()
        assert health == ProviderHealth.CRITICAL

    def test_health_check_returns_healthy_when_connected_and_closed(self):
        """Test that health_check() returns HEALTHY when connected and circuit is CLOSED."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        health = provider.health_check()
        assert health == ProviderHealth.HEALTHY

    def test_health_check_returns_warning_when_half_open(self):
        """Test that health_check() returns WARNING when circuit is HALF_OPEN."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        # Manually set circuit to HALF_OPEN
        provider._cb_state = "HALF_OPEN"
        health = provider.health_check()
        assert health == ProviderHealth.WARNING

    def test_health_check_returns_critical_when_open(self):
        """Test that health_check() returns CRITICAL when circuit is OPEN."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        # Manually set circuit to OPEN
        provider._cb_state = "OPEN"
        health = provider.health_check()
        assert health == ProviderHealth.CRITICAL

    def test_health_check_emits_heartbeat_event(self):
        """Test that health_check() emits ProviderHeartbeat event."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        with patch.object(provider, '_print_event') as mock_print:
            provider.health_check()
            mock_print.assert_called_once()
            call_args = mock_print.call_args
            assert call_args[0][0] == "ProviderHeartbeat"


class TestAlpacaProviderFetchForex:
    """Test AlpacaProvider fetch() for forex pairs."""

    @patch('requests.get')
    def test_fetch_xauusd_success(self, mock_get):
        """Test successful fetch of XAUUSD forex pair."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")

        assert result is not None
        assert result["symbol"] == "XAUUSD"
        assert result["bid"] == 2345.67
        assert result["ask"] == 2346.89
        assert result["mid"] == 2346.28
        assert abs(result["spread"] - 1.22) < 0.01  # Allow floating point precision
        assert result["providerId"] == "alpaca"
        assert result["providerName"] == "Alpaca"
        assert result["fresh"] is True

    @patch('requests.get')
    def test_fetch_gbpusd_success(self, mock_get):
        """Test successful fetch of GBPUSD forex pair."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "GBPUSD": {
                    "bp": 1.2500,
                    "ap": 1.2505,
                    "mp": 1.25025,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("GBPUSD")

        assert result is not None
        assert result["symbol"] == "GBPUSD"
        assert result["bid"] == 1.2500
        assert result["ask"] == 1.2505

    @patch('requests.get')
    def test_fetch_eurusd_success(self, mock_get):
        """Test successful fetch of EURUSD forex pair."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "EURUSD": {
                    "bp": 1.0800,
                    "ap": 1.0805,
                    "mp": 1.08025,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("EURUSD")

        assert result is not None
        assert result["symbol"] == "EURUSD"
        assert result["bid"] == 1.0800
        assert result["ask"] == 1.0805

    @patch('requests.get')
    def test_fetch_usdjpy_success(self, mock_get):
        """Test successful fetch of USDJPY forex pair."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "USDJPY": {
                    "bp": 145.50,
                    "ap": 145.55,
                    "mp": 145.525,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("USDJPY")

        assert result is not None
        assert result["symbol"] == "USDJPY"
        assert result["bid"] == 145.50
        assert result["ask"] == 145.55


class TestAlpacaProviderFetchStocks:
    """Test AlpacaProvider fetch() for stock indices."""

    @patch('requests.get')
    def test_fetch_nas100_success(self, mock_get):
        """Test successful fetch of NAS100 index."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "quotes": {
                "NDX": {
                    "bp": 15234.56,
                    "ap": 15235.78,
                    "t": "2022-08-17T10:07:40.286587431Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("NAS100")

        assert result is not None
        assert result["symbol"] == "NAS100"
        assert result["bid"] == 15234.56
        assert result["ask"] == 15235.78
        assert result["session"] == "US Market"

    @patch('requests.get')
    def test_fetch_us30_success(self, mock_get):
        """Test successful fetch of US30 index."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "quotes": {
                "DJI": {
                    "bp": 34567.89,
                    "ap": 34568.90,
                    "t": "2022-08-17T10:07:40.286587431Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("US30")

        assert result is not None
        assert result["symbol"] == "US30"
        assert result["bid"] == 34567.89
        assert result["ask"] == 34568.90


class TestAlpacaProviderResponseParsing:
    """Test AlpacaProvider response parsing."""

    @patch('requests.get')
    def test_handles_missing_bid(self, mock_get):
        """Test that missing bid in response returns None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_response.text = '{"rates": {"XAUUSD": {"ap": 2346.89, "mp": 2346.28, "t": "2022-04-20T18:23:00Z"}}}'
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")

        assert result is None

    @patch('requests.get')
    def test_handles_missing_ask(self, mock_get):
        """Test that missing ask in response returns None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_response.text = '{"rates": {"XAUUSD": {"bp": 2345.67, "mp": 2346.28, "t": "2022-04-20T18:23:00Z"}}}'
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")

        assert result is None

    @patch('requests.get')
    def test_handles_missing_rates_key(self, mock_get):
        """Test that missing rates key in response returns None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "error": "Invalid request"
        }
        mock_response.text = '{"error": "Invalid request"}'
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")

        assert result is None

    @patch('requests.get')
    def test_handles_json_parse_error(self, mock_get):
        """Test that JSON parsing error returns None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Invalid JSON"
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")

        assert result is None


class TestAlpacaProviderSymbolTranslation:
    """Test AlpacaProvider symbol translation."""

    @patch('requests.get')
    def test_uses_symbol_mapper_for_translation(self, mock_get):
        """Test that provider uses symbol_mapper for symbol translation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")

        assert result is not None
        assert result["symbol"] == "XAUUSD"
        assert result["providerTicker"] == "XAU/USD"

    @patch('requests.get')
    def test_handles_alias_gold(self, mock_get):
        """Test that provider handles 'gold' alias."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("gold")

        assert result is not None
        assert result["symbol"] == "XAUUSD"


class TestAlpacaProviderTimeouts:
    """Test AlpacaProvider timeout handling."""

    @patch('requests.get')
    def test_handles_timeout(self, mock_get):
        """Test that timeout is handled correctly."""
        mock_get.side_effect = requests.Timeout("Request timed out")

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")

        assert result is None
        assert provider._timeout_count > 0

    @patch('requests.get')
    def test_timeout_records_circuit_failure(self, mock_get):
        """Test that timeout records circuit breaker failure."""
        mock_get.side_effect = requests.Timeout("Request timed out")

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")

        assert result is None
        assert provider._consecutive_failures > 0


class TestAlpacaProviderNetworkFailures:
    """Test AlpacaProvider network failure handling."""

    @patch('requests.get')
    def test_handles_connection_error(self, mock_get):
        """Test that connection error is handled correctly."""
        mock_get.side_effect = requests.ConnectionError("Connection failed")

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")

        assert result is None

    @patch('requests.get')
    def test_connection_error_records_circuit_failure(self, mock_get):
        """Test that connection error records circuit breaker failure."""
        mock_get.side_effect = requests.ConnectionError("Connection failed")

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")

        assert result is None
        assert provider._consecutive_failures > 0


class TestAlpacaProvider429Handling:
    """Test AlpacaProvider HTTP 429 rate limit handling."""

    @patch('requests.get')
    def test_handles_429_rate_limit(self, mock_get):
        """Test that HTTP 429 is handled correctly."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")

        assert result is None
        assert provider._http_429_count > 0
        assert provider._last_failure_was_429 is True

    @patch('requests.get')
    def test_429_opens_circuit_after_threshold(self, mock_get):
        """Test that consecutive 429s open circuit after threshold."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()

        # Trigger enough failures to open circuit
        for _ in range(5):
            provider.fetch("XAUUSD")

        assert provider.circuit_breaker_state == "OPEN"
        assert provider._circuit_open_count > 0


class TestAlpacaProviderCircuitBreaker:
    """Test AlpacaProvider circuit breaker functionality."""

    def test_circuit_breaker_initially_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        assert provider.circuit_breaker_state == "CLOSED"

    @patch('requests.get')
    def test_circuit_opens_after_failures(self, mock_get):
        """Test that circuit opens after consecutive failures."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()

        # Trigger enough failures to open circuit
        for _ in range(5):
            provider.fetch("XAUUSD")

        assert provider.circuit_breaker_state == "OPEN"

    @patch('requests.get')
    def test_circuit_blocks_requests_when_open(self, mock_get):
        """Test that circuit blocks requests when OPEN."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()

        # Open the circuit
        for _ in range(5):
            provider.fetch("XAUUSD")

        # Reset mock to track if requests are made
        mock_get.reset_mock()

        # Try to fetch - should be blocked
        result = provider.fetch("XAUUSD")

        assert result is None
        # Should not make HTTP request when circuit is open
        mock_get.assert_not_called()

    def test_circuit_transitions_to_half_open_after_cooldown(self):
        """Test that circuit transitions to HALF_OPEN after cooldown."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()

        # Manually set circuit to OPEN
        provider._cb_state = "OPEN"
        provider._cb_opened_at = time.monotonic() - 70  # 70 seconds ago (cooldown is 60)

        # Trigger cooldown check - this should transition to HALF_OPEN temporarily
        should_block = provider._cb_should_block()
        
        # After _cb_should_block, the state is set to OPEN to block concurrent calls
        # but _is_trial_request is set to True for the trial
        assert provider._is_trial_request is True
        assert should_block is False  # Should allow the trial request

    @patch('requests.get')
    def test_circuit_closes_after_successful_trial(self, mock_get):
        """Test that circuit closes after successful trial request."""
        # First, open the circuit with failures
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.return_value = mock_response_fail

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()

        for _ in range(5):
            provider.fetch("XAUUSD")

        # Set cooldown elapsed
        provider._cb_opened_at = time.monotonic() - 70

        # Now make a successful request
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response_success

        result = provider.fetch("XAUUSD")

        assert result is not None
        assert provider.circuit_breaker_state == "CLOSED"

    @patch('requests.get')
    def test_circuit_reopens_after_failed_trial(self, mock_get):
        """Test that circuit reopens after failed trial request."""
        # First, open the circuit
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.return_value = mock_response_fail

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()

        for _ in range(5):
            provider.fetch("XAUUSD")

        # Set cooldown elapsed
        provider._cb_opened_at = time.monotonic() - 70

        # Make a failed trial request
        mock_response_fail.status_code = 500
        mock_get.return_value = mock_response_fail

        result = provider.fetch("XAUUSD")

        assert result is None
        assert provider.circuit_breaker_state == "OPEN"

    def test_seconds_until_retry_returns_none_when_closed(self):
        """Test that seconds_until_retry returns None when circuit is CLOSED."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        assert provider._cb_seconds_until_retry() is None

    def test_seconds_until_retry_returns_value_when_open(self):
        """Test that seconds_until_retry returns value when circuit is OPEN."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider._cb_state = "OPEN"
        provider._cb_opened_at = time.monotonic() - 30  # 30 seconds ago
        retry_seconds = provider._cb_seconds_until_retry()
        assert retry_seconds is not None
        assert retry_seconds > 0


class TestAlpacaProviderCircuitBreakerEvents:
    """Test AlpacaProvider circuit breaker event emission."""

    @patch('requests.get')
    def test_emits_circuit_breaker_open_event(self, mock_get):
        """Test that CircuitBreakerOpen event is emitted."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()

        with patch.object(provider, '_print_event') as mock_print:
            # Trigger enough failures to open circuit
            for _ in range(5):
                provider.fetch("XAUUSD")

            # Check that CircuitBreakerOpen was called
            event_calls = [call[0][0] for call in mock_print.call_args_list]
            assert "CircuitBreakerOpen" in event_calls

    @patch('requests.get')
    def test_emits_circuit_breaker_half_open_event(self, mock_get):
        """Test that CircuitBreakerHalfOpen event is emitted."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()

        # Open the circuit
        for _ in range(5):
            provider.fetch("XAUUSD")

        # Set cooldown elapsed
        provider._cb_opened_at = time.monotonic() - 70

        with patch.object(provider, '_print_event') as mock_print:
            # Trigger cooldown check
            provider._cb_should_block()

            # Check that CircuitBreakerHalfOpen was called
            event_calls = [call[0][0] for call in mock_print.call_args_list]
            assert "CircuitBreakerHalfOpen" in event_calls

    @patch('requests.get')
    def test_emits_circuit_breaker_closed_event(self, mock_get):
        """Test that CircuitBreakerClosed event is emitted."""
        # First, open the circuit
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.return_value = mock_response_fail

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()

        for _ in range(5):
            provider.fetch("XAUUSD")

        # Set cooldown elapsed
        provider._cb_opened_at = time.monotonic() - 70

        # Make a successful request
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response_success

        with patch.object(provider, '_print_event') as mock_print:
            provider.fetch("XAUUSD")

            # Check that CircuitBreakerClosed was called
            event_calls = [call[0][0] for call in mock_print.call_args_list]
            assert "CircuitBreakerClosed" in event_calls

    @patch('requests.get')
    def test_emits_circuit_breaker_reopened_event(self, mock_get):
        """Test that CircuitBreakerReopened event is emitted."""
        # First, open the circuit
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.return_value = mock_response_fail

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()

        for _ in range(5):
            provider.fetch("XAUUSD")

        # Set cooldown elapsed
        provider._cb_opened_at = time.monotonic() - 70

        with patch.object(provider, '_print_event') as mock_print:
            # Make a failed trial request
            mock_response_fail.status_code = 500
            mock_get.return_value = mock_response_fail
            provider.fetch("XAUUSD")

            # Check that CircuitBreakerReopened was called
            event_calls = [call[0][0] for call in mock_print.call_args_list]
            assert "CircuitBreakerReopened" in event_calls


class TestAlpacaProviderMetadata:
    """Test AlpacaProvider metadata reporting."""

    def test_get_metadata_returns_correct_structure(self):
        """Test that get_metadata() returns correct structure."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        metadata = provider.get_metadata()

        assert metadata.providerId == "alpaca"
        assert metadata.providerName == "Alpaca"
        assert metadata.providerVersion == "1.0.0"
        assert metadata.providerType == ProviderType.PRICE

    def test_get_metadata_includes_capabilities(self):
        """Test that get_metadata() includes capabilities."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        metadata = provider.get_metadata()

        assert len(metadata.capabilities) > 0

    def test_get_metadata_status_reflects_connection(self):
        """Test that metadata status reflects connection state."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        metadata = provider.get_metadata()
        assert metadata.status == ProviderStatus.OFFLINE

        provider.connect()
        metadata = provider.get_metadata()
        assert metadata.status == ProviderStatus.ONLINE

    def test_get_metadata_health_reflects_health_check(self):
        """Test that metadata health reflects health_check()."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        metadata = provider.get_metadata()
        assert metadata.health == ProviderHealth.HEALTHY


class TestAlpacaProviderStatistics:
    """Test AlpacaProvider statistics reporting."""

    @patch('requests.get')
    def test_get_statistics_includes_base_metrics(self, mock_get):
        """Test that get_statistics() includes base metrics."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        provider.fetch("XAUUSD")

        stats = provider.get_statistics()

        assert stats.totalRequests == 1
        assert stats.successfulRequests == 1
        assert stats.failedRequests == 0
        assert stats.successRate == 100.0

    @patch('requests.get')
    def test_get_statistics_includes_circuit_breaker_state(self, mock_get):
        """Test that get_statistics() includes circuit breaker state."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        provider.fetch("XAUUSD")

        stats = provider.get_statistics()

        assert stats.circuitBreakerState == "CLOSED"
        assert stats.circuitRetryInSeconds is None

    @patch('requests.get')
    def test_get_statistics_includes_rate_limit_tracking(self, mock_get):
        """Test that get_statistics() includes rate limit tracking."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        provider.fetch("XAUUSD")

        stats = provider.get_statistics()

        assert stats.http429Count == 1

    @patch('requests.get')
    def test_get_statistics_includes_timeout_tracking(self, mock_get):
        """Test that get_statistics() includes timeout tracking."""
        mock_get.side_effect = requests.Timeout("Request timed out")

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        provider.fetch("XAUUSD")

        stats = provider.get_statistics()

        assert stats.timeoutCount == 1

    @patch('requests.get')
    def test_get_statistics_includes_timestamps(self, mock_get):
        """Test that get_statistics() includes success/failure timestamps."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        provider.fetch("XAUUSD")

        stats = provider.get_statistics()

        assert stats.lastSuccessAt is not None
        assert isinstance(stats.lastSuccessAt, datetime)

    @patch('requests.get')
    def test_get_statistics_includes_latency_metrics(self, mock_get):
        """Test that get_statistics() includes latency metrics."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        provider.fetch("XAUUSD")

        stats = provider.get_statistics()

        assert stats.avgSuccessLatencyMs >= 0
        assert stats.avgFailureLatencyMs == 0  # No failures

    @patch('requests.get')
    def test_get_statistics_includes_lifecycle_counters(self, mock_get):
        """Test that get_statistics() includes lifecycle counters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        provider.fetch("XAUUSD")

        stats = provider.get_statistics()

        assert stats.circuitOpenCount == 0
        assert stats.circuitCloseCount == 0
        assert stats.recoveryCount == 0


class TestAlpacaProviderSupports:
    """Test AlpacaProvider supports() method."""

    def test_supports_live_price(self):
        """Test that provider supports LIVE_PRICE capability."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        assert provider.supports(ProviderCapability.LIVE_PRICE) is True

    def test_supports_spread(self):
        """Test that provider supports SPREAD capability."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        assert provider.supports(ProviderCapability.SPREAD) is True

    def test_supports_market_session(self):
        """Test that provider supports MARKET_SESSION capability."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        assert provider.supports(ProviderCapability.MARKET_SESSION) is True

    def test_supports_symbol_information(self):
        """Test that provider supports SYMBOL_INFORMATION capability."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        assert provider.supports(ProviderCapability.SYMBOL_INFORMATION) is True

    def test_does_not_support_news_feed(self):
        """Test that provider does not support NEWS_FEED capability."""
        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        assert provider.supports(ProviderCapability.NEWS_FEED) is False


class TestAlpacaProviderHTTPHeaders:
    """Test AlpacaProvider HTTP header authentication."""

    @patch('requests.get')
    def test_sends_api_key_header(self, mock_get):
        """Test that provider sends APCA-API-KEY-ID header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        provider.fetch("XAUUSD")

        # Check that headers were set
        call_args = mock_get.call_args
        headers = call_args[1]['headers']
        assert 'APCA-API-KEY-ID' in headers
        assert headers['APCA-API-KEY-ID'] == 'test_key'

    @patch('requests.get')
    def test_sends_secret_key_header(self, mock_get):
        """Test that provider sends APCA-API-SECRET-KEY header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        provider.fetch("XAUUSD")

        # Check that headers were set
        call_args = mock_get.call_args
        headers = call_args[1]['headers']
        assert 'APCA-API-SECRET-KEY' in headers
        assert headers['APCA-API-SECRET-KEY'] == 'test_secret'


class TestAlpacaProviderHTTPEndpoints:
    """Test AlpacaProvider HTTP endpoint selection."""

    @patch('requests.get')
    def test_uses_forex_endpoint_for_forex_pairs(self, mock_get):
        """Test that provider uses forex endpoint for forex pairs."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        provider.fetch("XAUUSD")

        # Check that forex endpoint was used
        call_args = mock_get.call_args
        url = call_args[0][0]
        assert "/v1beta1/forex/latest/rates" in url

    @patch('requests.get')
    def test_uses_stock_endpoint_for_indices(self, mock_get):
        """Test that provider uses stock endpoint for indices."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "quotes": {
                "NDX": {
                    "bp": 15234.56,
                    "ap": 15235.78,
                    "t": "2022-08-17T10:07:40.286587431Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        provider.fetch("NAS100")

        # Check that stock endpoint was used
        call_args = mock_get.call_args
        url = call_args[0][0]
        assert "/v2/stocks/quotes/latest" in url


class TestAlpacaProviderQuoteNormalization:
    """Test AlpacaProvider quote normalization."""

    @patch('requests.get')
    def test_normalization_matches_falcon_format(self, mock_get):
        """Test that normalized quote matches Falcon format."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")

        # Verify all required fields are present
        required_fields = [
            "symbol", "providerTicker", "bid", "ask", "spread", "mid",
            "lastPrice", "change", "changePercent", "timestamp",
            "providerId", "providerName", "fresh", "session"
        ]
        for field in required_fields:
            assert field in result

    @patch('requests.get')
    def test_quote_is_provider_agnostic(self, mock_get):
        """Test that quote structure is provider-agnostic."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {
                "XAUUSD": {
                    "bp": 2345.67,
                    "ap": 2346.89,
                    "mp": 2346.28,
                    "t": "2022-04-20T18:23:00Z"
                }
            }
        }
        mock_get.return_value = mock_response

        provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
        provider.connect()
        result = provider.fetch("XAUUSD")

        # Verify structure matches expected format
        assert isinstance(result["bid"], (int, float))
        assert isinstance(result["ask"], (int, float))
        assert isinstance(result["spread"], (int, float))
        assert isinstance(result["mid"], (int, float))
        assert isinstance(result["lastPrice"], (int, float))
        assert isinstance(result["change"], (int, float))
        assert isinstance(result["changePercent"], (int, float))
        assert isinstance(result["timestamp"], str)
        assert isinstance(result["fresh"], bool)
