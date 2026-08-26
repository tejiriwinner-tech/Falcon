"""
Falcon Provider Framework — Alpaca Provider Implementation (Phase 7.2 - Milestone 2)
Live market data provider for forex and indices (priority 2 when enabled).

Alpaca serves as a secondary provider offering high-quality live pricing for:
- XAUUSD (Spot Gold) - Forex API
- GBPUSD (British Pound / US Dollar) - Forex API
- EURUSD (Euro / US Dollar) - Forex API
- USDJPY (US Dollar / Japanese Yen) - Forex API
- NAS100 (NASDAQ-100 Index) - Stock API (^NDX)
- US30 (Dow Jones Industrial Average) - Stock API (^DJI)

Circuit Breaker (finite-state machine):

  CLOSED  ──[consecutive_failures >= threshold]──►  OPEN
  OPEN    ──[cooldown elapsed]──────────────────►  HALF_OPEN
  HALF_OPEN ──[trial succeeds]──────────────────►  CLOSED
  HALF_OPEN ──[trial fails]─────────────────────►  OPEN  (restart cooldown)

While OPEN, fetch() returns None immediately without making an HTTP request,
so ProviderManager proceeds to the next provider with zero added latency.

ProviderHealth mapping:
  CLOSED  + ok   → HEALTHY  / status ONLINE
  CLOSED  + degraded → WARNING / status DEGRADED
  HALF_OPEN       → WARNING  / status DEGRADED
  OPEN (429)      → CRITICAL / status RATE_LIMITED
  OPEN (other)    → CRITICAL / status OFFLINE
  not connected   → CRITICAL / status OFFLINE

API Reference:
- Forex: https://docs.alpaca.markets/us/reference/latestrates-1
- Stocks: https://docs.alpaca.markets/us/reference/stocklatestquotes-1
"""
import logging
import time
import threading
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.core.config.provider_settings import (
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_COOLDOWN_SECONDS,
)
from app.core.providers.base_provider import BaseProvider
from app.core.providers.symbol_mapper import symbol_mapper
from app.schemas.provider_models import (
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderStatistics,
    ProviderStatus,
    ProviderType,
)

_CAPABILITIES: List[ProviderCapability] = [
    ProviderCapability.LIVE_PRICE,
    ProviderCapability.SPREAD,
    ProviderCapability.MARKET_SESSION,
    ProviderCapability.SYMBOL_INFORMATION,
]

# Circuit breaker states
_CB_CLOSED    = "CLOSED"
_CB_OPEN      = "OPEN"
_CB_HALF_OPEN = "HALF_OPEN"


class AlpacaProvider(BaseProvider):
    """Alpaca API provider with integrated circuit breaker.
    
    This provider fetches real-time forex and index quotes from Alpaca's
    market data API. It serves as a secondary provider (priority 2) in the
    Falcon provider hierarchy when enabled via ENABLE_ALPACA_PROVIDER feature flag.
    
    The provider implements circuit breaker protection to prevent cascading
    failures during API outages or rate limiting. Alpaca's rate limits are
    enforced via HTTP 429 responses.
    
    Supported Instruments:
    - XAUUSD: Spot gold (maps to XAU/USD via Forex API)
    - GBPUSD: British pound (maps to GBP/USD via Forex API)
    - EURUSD: Euro (maps to EUR/USD via Forex API)
    - USDJPY: US dollar / Japanese yen (maps to USD/JPY via Forex API)
    - NAS100: NASDAQ-100 (maps to ^NDX via Stock API)
    - US30: Dow Jones (maps to ^DJI via Stock API)
    
    Circuit Breaker Behavior:
    - CLOSED: Normal operation, all requests proceed
    - OPEN: Blocking mode, returns None immediately (no HTTP requests)
    - HALF_OPEN: Trial mode after cooldown, allows one test request
    
    Authentication:
    - Uses APCA-API-KEY-ID and APCA-API-SECRET-KEY headers
    - Credentials loaded from settings.ALPACA_API_KEY and settings.ALPACA_SECRET_KEY
    """

    PROVIDER_ID = "alpaca"
    PROVIDER_NAME = "Alpaca"
    PROVIDER_VERSION = "1.0.0"

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None):
        """Initialize Alpaca provider with circuit breaker protection.
        
        Args:
            api_key: Alpaca API key ID. If None, reads from settings.ALPACA_API_KEY
            secret_key: Alpaca API secret key. If None, reads from settings.ALPACA_SECRET_KEY
        """
        super().__init__(
            provider_id="alpaca",
            provider_name="Alpaca",
            provider_type="LIVE",
            priority=2,  # Secondary provider (after TwelveData priority 1)
        )
        self.capabilities = [c.value if hasattr(c, "value") else str(c) for c in _CAPABILITIES]
        
        # API configuration
        self._api_key: Optional[str] = api_key or settings.ALPACA_API_KEY
        self._secret_key: Optional[str] = secret_key or settings.ALPACA_SECRET_KEY
        self._base_url: str = getattr(settings, "ALPACA_BASE_URL", "https://data.alpaca.markets")
        self._connected: bool = False

        # ── Circuit breaker state ──────────────────────────────────────
        self._cb_state: str = _CB_CLOSED
        self._cb_lock = threading.Lock()

        # Counters reset on circuit open/close
        self._consecutive_failures: int = 0

        # Timestamp when the circuit last transitioned to OPEN
        self._cb_opened_at: Optional[float] = None

        # Whether the most recent failures were caused by 429s specifically
        self._last_failure_was_429: bool = False

        # ── Extended statistics ────────────────────────────────────────
        self._http_429_count: int = 0
        self._timeout_count: int = 0
        self._last_success_at: Optional[datetime] = None
        self._last_failure_at: Optional[datetime] = None

        # ── Circuit lifecycle counters ───────────────────────────────────
        self._circuit_open_count: int = 0    # times circuit transitioned → OPEN
        self._circuit_close_count: int = 0   # times circuit transitioned → CLOSED
        self._recovery_count: int = 0        # alias for close count (explicit recoveries)

        # Flag set in _cb_should_block() to mark that the current fetch is the
        # HALF_OPEN trial. Used by _cb_record_failure() to emit the correct
        # CircuitBreakerReopened event when the trial fails.
        self._is_trial_request: bool = False

    # ──────────────────────────────────────────────────────────────────
    # BaseProvider contract
    # ──────────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Establish connection to Alpaca API.
        
        Sets _connected flag to True. No actual connection is established
        since we use stateless HTTP requests.
        
        Returns:
            True (always succeeds)
        """
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Gracefully close connection.
        
        Sets _connected flag to False. Prevents further requests until
        connect() is called again.
        """
        self._connected = False

    # ──────────────────────────────────────────────────────────────────
    # Circuit breaker helpers
    # ──────────────────────────────────────────────────────────────────

    @property
    def circuit_breaker_state(self) -> str:
        """Return current circuit breaker state string (CLOSED | OPEN | HALF_OPEN)."""
        with self._cb_lock:
            return self._cb_state

    def _cb_seconds_until_retry(self) -> Optional[float]:
        """Calculate seconds remaining until HALF_OPEN transition.
        
        Returns:
            Seconds until retry if circuit is OPEN, None otherwise
        """
        with self._cb_lock:
            if self._cb_state != _CB_OPEN or self._cb_opened_at is None:
                return None
            elapsed = time.monotonic() - self._cb_opened_at
            remaining = CIRCUIT_BREAKER_COOLDOWN_SECONDS - elapsed
            return max(0.0, round(remaining, 1))

    def _cb_should_block(self) -> bool:
        """Determine if request should be blocked by circuit breaker.
        
        Side effect: Transitions OPEN → HALF_OPEN when cooldown elapses.
        
        Returns:
            True if circuit is OPEN and cooldown has not elapsed
            False if request should proceed (CLOSED or trial request)
        """
        with self._cb_lock:
            if self._cb_state == _CB_CLOSED:
                self._is_trial_request = False
                return False
            if self._cb_state == _CB_HALF_OPEN:
                # Allow exactly one trial; set state back to OPEN to block
                # concurrent callers until the trial resolves.
                self._cb_state = _CB_OPEN
                self._is_trial_request = True
                return False   # let this caller through as the trial
            # _CB_OPEN — check cooldown
            if self._cb_opened_at is None:
                self._is_trial_request = False
                return True
            elapsed = time.monotonic() - self._cb_opened_at
            if elapsed >= CIRCUIT_BREAKER_COOLDOWN_SECONDS:
                # Cooldown elapsed — grant one trial
                self._cb_state = _CB_HALF_OPEN
                self._cb_state = _CB_OPEN   # lock the door for concurrent callers
                self._is_trial_request = True
                # Emit CircuitBreakerHalfOpen event
                self._print_event("CircuitBreakerHalfOpen",
                                  "Cooldown elapsed — allowing trial request")
                return False   # this caller is the trial
            self._is_trial_request = False
            return True        # still cooling down

    def _cb_record_success(self) -> None:
        """Reset circuit breaker after successful request.
        
        Transitions to CLOSED state, resets failure counters, emits
        CircuitBreakerClosed event if recovering from OPEN/HALF_OPEN.
        Updates last_success_at timestamp.
        """
        with self._cb_lock:
            was_open = self._cb_state in (_CB_OPEN, _CB_HALF_OPEN)
            self._cb_state = _CB_CLOSED
            self._consecutive_failures = 0
            self._cb_opened_at = None
            self._last_failure_was_429 = False
            self._is_trial_request = False
            # Update last success timestamp
            self._last_success_at = datetime.now(timezone.utc)
            if was_open:
                self._circuit_close_count += 1
                self._recovery_count += 1
        if was_open:
            # Emit CircuitBreakerClosed event when recovering
            self._print_event("CircuitBreakerClosed", "Trial request succeeded — circuit reset")

    def _cb_record_failure(self, is_429: bool = False, is_timeout: bool = False) -> None:
        """Record request failure and potentially open circuit.
        
        Args:
            is_429: Whether failure was HTTP 429 rate limit
            is_timeout: Whether failure was network timeout
        
        Side effects:
            - Increments consecutive_failures
            - Opens circuit if threshold reached
            - Emits CircuitBreakerOpen or CircuitBreakerReopened event
        """
        with self._cb_lock:
            self._consecutive_failures += 1
            if is_429:
                self._http_429_count += 1
                self._last_failure_was_429 = True
            if is_timeout:
                self._timeout_count += 1
                if not is_429:
                    self._last_failure_was_429 = False

            was_trial = self._is_trial_request
            self._is_trial_request = False   # consume the flag

            if self._consecutive_failures >= CIRCUIT_BREAKER_FAILURE_THRESHOLD:
                if self._cb_state != _CB_OPEN:
                    # Fresh transition to OPEN
                    self._cb_state = _CB_OPEN
                    self._cb_opened_at = time.monotonic()
                    self._circuit_open_count += 1
                    # Determine failure reason
                    if is_429:
                        reason = "HTTP 429 rate limit"
                    elif is_timeout:
                        reason = "timeout"
                    else:
                        reason = "other"
                    # Include failure count and cooldown duration
                    self._print_event(
                        "CircuitBreakerOpen",
                        f"Circuit opened after {self._consecutive_failures} consecutive "
                        f"failures ({reason}). Cooldown: {CIRCUIT_BREAKER_COOLDOWN_SECONDS}s",
                    )
                elif was_trial:
                    # Already OPEN, and this failure was the HALF_OPEN trial
                    self._cb_opened_at = time.monotonic()   # restart cooldown
                    self._circuit_open_count += 1
                    # Determine failure reason
                    if is_429:
                        reason = "HTTP 429 rate limit"
                    elif is_timeout:
                        reason = "timeout"
                    else:
                        reason = "upstream failure"
                    self._print_event(
                        "CircuitBreakerReopened",
                        f"Trial request failed — circuit reopened ({reason}). "
                        f"Cooldown: {CIRCUIT_BREAKER_COOLDOWN_SECONDS}s",
                    )
                else:
                    # Already open, normal blocked-but-leaked failure — restart cooldown
                    self._cb_opened_at = time.monotonic()

    def _print_event(self, event: str, detail: str) -> None:
        """Emit structured event to EventBus.
        
        Emits structured events for observability. All events include:
        - eventName: Type of event
        - providerId: "alpaca"
        - providerName: "Alpaca"
        - detail: Human-readable event description with context
        - timestamp: ISO 8601 format
        
        Args:
            event: Event name (e.g., "CircuitBreakerOpen", "ProviderHeartbeat")
            detail: Human-readable event description
        """
        import json as _json
        payload = {
            "eventName": event,
            "providerId": self.PROVIDER_ID,
            "providerName": self.PROVIDER_NAME,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"[EVENT BUS] {_json.dumps(payload)}")

    # ──────────────────────────────────────────────────────────────────
    # Health / metadata
    # ──────────────────────────────────────────────────────────────────

    def health_check(self) -> ProviderHealth:
        """Return current health status based on circuit breaker state.
        
        Emits a ProviderHeartbeat event with alive status and health level.
        
        Returns:
            HEALTHY: Circuit is CLOSED and provider is connected
            WARNING: Circuit is HALF_OPEN (trial mode)
            CRITICAL: Circuit is OPEN or provider is not connected
        """
        if not self._connected:
            health = ProviderHealth.CRITICAL
        else:
            cb = self.circuit_breaker_state
            if cb == _CB_OPEN:
                health = ProviderHealth.CRITICAL
            elif cb == _CB_HALF_OPEN:
                health = ProviderHealth.WARNING
            else:
                # CLOSED — healthy
                health = ProviderHealth.HEALTHY
        
        # Emit ProviderHeartbeat event
        self._print_event("ProviderHeartbeat",
                          f"Alive: {self._connected}, Health: {health.value if hasattr(health, 'value') else str(health)}")
        return health

    def _provider_status(self) -> ProviderStatus:
        """Return provider status based on circuit breaker state.
        
        Returns:
            ONLINE: Circuit is CLOSED
            RATE_LIMITED: Circuit is OPEN due to 429
            OFFLINE: Circuit is OPEN for other reasons or not connected
            DEGRADED: Circuit is HALF_OPEN
        """
        if not self._connected:
            return ProviderStatus.OFFLINE
        cb = self.circuit_breaker_state
        if cb == _CB_OPEN:
            return ProviderStatus.RATE_LIMITED if self._last_failure_was_429 else ProviderStatus.OFFLINE
        if cb == _CB_HALF_OPEN:
            return ProviderStatus.DEGRADED
        # CLOSED
        return ProviderStatus.ONLINE

    def get_statistics(self) -> ProviderStatistics:
        """Return comprehensive provider statistics.
        
        Extends BaseProvider.get_statistics() with circuit breaker fields.
        
        Includes:
        - Base metrics: totalRequests, successfulRequests, failedRequests, successRate
        - Circuit breaker state: circuitBreakerState, circuitRetryInSeconds
        - Rate limit tracking: http429Count, timeoutCount
        - Consecutive counters: consecutiveFailures, consecutiveSuccesses
        - Timestamps: lastSuccessAt, lastFailureAt
        - Lifecycle counters: circuitOpenCount, circuitCloseCount, recoveryCount
        - Latency metrics: avgSuccessLatencyMs, avgFailureLatencyMs
        """
        # Calculate success rate from total and successful requests
        success_rate = (
            (self._success_count / self._request_count * 100)
            if self._request_count > 0
            else 100.0
        )
        
        # Calculate avgSuccessLatencyMs from successful requests only
        avg_success_latency = (
            self._success_total_latency_ms / self._success_count
            if self._success_count > 0
            else 0.0
        )
        
        # Calculate avgFailureLatencyMs from failed requests only
        avg_failure_latency = (
            self._failure_total_latency_ms / self._fail_count
            if self._fail_count > 0
            else 0.0
        )
        
        # Build statistics object with all required fields
        return ProviderStatistics(
            # Base metrics
            totalRequests=self._request_count,
            successfulRequests=self._success_count,
            failedRequests=self._fail_count,
            successRate=round(success_rate, 2),
            
            # Circuit breaker state and retry calculation
            consecutiveFailures=self._consecutive_failures,
            circuitBreakerState=self.circuit_breaker_state,
            circuitRetryInSeconds=self._cb_seconds_until_retry(),
            
            # Rate limit and timeout tracking
            http429Count=self._http_429_count,
            timeoutCount=self._timeout_count,
            
            # Success/failure timestamps
            lastSuccessAt=self._last_success_at,
            lastFailureAt=self._last_failure_at,
            
            # Health metrics
            uptimePercent=round(success_rate, 2),
            avgSuccessLatencyMs=round(avg_success_latency, 2),
            avgFailureLatencyMs=round(avg_failure_latency, 2),
            consecutiveSuccesses=self._consecutive_successes,
            recoveryCount=self._recovery_count,
            circuitOpenCount=self._circuit_open_count,
            circuitCloseCount=self._circuit_close_count,
            lastSuccessfulQuoteAt=self._last_success_at,
            lastFailedRequestAt=self._last_failure_at,
        )

    def get_metadata(self) -> ProviderMetadata:
        """Return static provider metadata.
        
        Returns:
            ProviderMetadata with providerId, name, version, type, capabilities,
            status, and health
        """
        return ProviderMetadata(
            providerId=self.PROVIDER_ID,
            providerName=self.PROVIDER_NAME,
            providerVersion=self.PROVIDER_VERSION,
            providerType=ProviderType.PRICE,
            capabilities=_CAPABILITIES,
            status=self._provider_status(),
            health=self.health_check(),
        )

    def supports(self, capability: ProviderCapability) -> bool:
        """Check if provider supports the given capability.
        
        Args:
            capability: ProviderCapability enum value
        
        Returns:
            True if capability in [LIVE_PRICE, SPREAD, MARKET_SESSION, SYMBOL_INFORMATION]
        """
        return capability in _CAPABILITIES

    # ──────────────────────────────────────────────────────────────────
    # Core fetch — guarded by circuit breaker
    # ──────────────────────────────────────────────────────────────────

    def fetch(self, symbol: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetch real-time market quote for the given symbol.
        
        Implements circuit breaker gating. If circuit is OPEN and cooldown
        has not elapsed, returns None immediately without making HTTP request.
        
        Args:
            symbol: Canonical symbol (e.g., "XAUUSD", "NASDAQ")
            **kwargs: Unused, for interface compatibility
        
        Returns:
            Normalized quote dictionary on success, None on failure
            
        Quote Structure:
            {
                "symbol": str,           # Canonical symbol
                "providerTicker": str,   # Provider-specific symbol
                "bid": float,
                "ask": float,
                "spread": float,
                "mid": float,
                "lastPrice": float,
                "change": float,
                "changePercent": float,
                "timestamp": str,        # ISO 8601 format
                "providerId": str,
                "providerName": str,
                "fresh": bool,
                "session": str,
            }
        """
        # ── Pre-flight checks ──────────────────────────────────────────
        
        # Check if API key is configured
        if not self._api_key or not self._secret_key:
            logger.warning(f"[{self.PROVIDER_NAME}] API key or secret not configured. Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables.")
            return None
        
        # Check if provider is connected
        if not self._connected:
            return None
        
        # Check circuit breaker state
        if self._cb_should_block():
            return None
        
        # ── Symbol Translation Logic ──────────────────────────────────
        
        # Step 1: Normalize the input symbol to canonical format
        canonical = symbol_mapper.normalize(symbol)
        
        # Step 2: Fallback to uppercase if symbol_mapper returns None
        if canonical is None:
            canonical = symbol.upper()
        
        # Step 3: Convert canonical symbol to Alpaca provider-specific format
        provider_ticker = symbol_mapper.to_provider_symbol(canonical, self.PROVIDER_ID)
        
        # Step 4: Determine if this is a forex pair or stock/index
        # Forex pairs: XAUUSD, GBPUSD, EURUSD, USDJPY
        # Stocks/Indices: NAS100 (^NDX), US30 (^DJI)
        forex_pairs = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY"]
        is_forex = canonical in forex_pairs
        
        # ── API Request Construction ───────────────────────────────────
        
        if is_forex:
            # Use Forex API endpoint
            # Convert canonical symbol to Alpaca forex format (e.g., XAUUSD → XAU/USD)
            # Alpaca forex format uses slash separator
            forex_pair = provider_ticker.replace("/", "")  # Remove slash for API
            url = f"{self._base_url}/v1beta1/forex/latest/rates"
            params = {
                "currency_pairs": forex_pair
            }
        else:
            # Use Stock API endpoint for indices
            # Remove caret (^) from index symbols
            stock_symbol = provider_ticker.replace("^", "")
            url = f"{self._base_url}/v2/stocks/quotes/latest"
            params = {
                "symbols": stock_symbol,
                "feed": "iex"  # Use IEX feed for broader data access
            }
        
        # Step 2: Set 5-second timeout for HTTP requests
        timeout = 5.0
        
        # ── Request Execution with Timing ─────────────────────────────
        
        # Prepare authentication headers
        headers = {
            "APCA-API-KEY-ID": self._api_key,
            "APCA-API-SECRET-KEY": self._secret_key,
        }
        
        start = time.perf_counter()
        try:
            # Make HTTP GET request with constructed URL, params, headers, and timeout
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            latency_ms = (time.perf_counter() - start) * 1000
            
            # ── Error Handling ────────────────────────────────────────
            
            # Handle HTTP 429 rate limit
            if response.status_code == 429:
                self._record_request(success=False, latency_ms=latency_ms)
                self._last_failure_at = datetime.now(timezone.utc)
                self._cb_record_failure(is_429=True)
                return None
            
            # Handle other non-200 HTTP errors
            if response.status_code != 200:
                logger.error(f"[{self.PROVIDER_NAME}] HTTP {response.status_code} error: {response.text[:200]}")
                self._record_request(success=False, latency_ms=latency_ms)
                self._last_failure_at = datetime.now(timezone.utc)
                self._cb_record_failure()
                return None
            
            # ── Success Path with Quote Normalization ────────────────
            
            # Parse JSON response
            try:
                data = response.json()
            except ValueError as e:
                # JSON parsing error
                logger.error(f"[{self.PROVIDER_NAME}] JSON parsing error: {e}")
                self._record_request(success=False, latency_ms=latency_ms)
                self._last_failure_at = datetime.now(timezone.utc)
                self._cb_record_failure()
                return None
            
            # ── API Response Parsing ─────────────────────────────────
            
            if is_forex:
                # Parse Forex API response
                # Response format: {"rates": {"XAUUSD": {"bp": 2345.67, "ap": 2346.89, "mp": 2346.28, "t": "2022-04-20T18:23:00Z"}}}
                try:
                    rates = data.get("rates", {})
                    # Try to get rate by the forex pair key
                    rate_data = rates.get(forex_pair)
                    
                    if rate_data is None:
                        # Try with slash format
                        rate_data = rates.get(provider_ticker)
                    
                    if rate_data is None:
                        logger.warning(f"[{self.PROVIDER_NAME}] Missing rate data in response: {data}")
                        self._record_request(success=False, latency_ms=latency_ms)
                        self._last_failure_at = datetime.now(timezone.utc)
                        self._cb_record_failure()
                        return None
                    
                    # Extract bid, ask, mid, and timestamp
                    bid = rate_data.get("bp")
                    ask = rate_data.get("ap")
                    mid = rate_data.get("mp")
                    timestamp_str = rate_data.get("t")
                    
                    if bid is None or ask is None:
                        logger.warning(f"[{self.PROVIDER_NAME}] Missing bid/ask in rate data: {rate_data}")
                        self._record_request(success=False, latency_ms=latency_ms)
                        self._last_failure_at = datetime.now(timezone.utc)
                        self._cb_record_failure()
                        return None
                    
                    # Calculate spread
                    spread = ask - bid if ask and bid else 0.0
                    
                    # Use mid as lastPrice
                    last_price = mid if mid else (bid + ask) / 2.0
                    
                    # Parse timestamp
                    timestamp = timestamp_str if timestamp_str else datetime.now(timezone.utc).isoformat()
                    
                except (KeyError, TypeError, ValueError) as e:
                    logger.error(f"[{self.PROVIDER_NAME}] Error parsing forex API response: {e}")
                    self._record_request(success=False, latency_ms=latency_ms)
                    self._last_failure_at = datetime.now(timezone.utc)
                    self._cb_record_failure()
                    return None
            else:
                # Parse Stock API response
                # Response format: {"quotes": {"NDX": {"bp": 12345.67, "ap": 12346.89, "t": "2022-08-17T10:07:40.286587431Z"}}}
                try:
                    quotes = data.get("quotes", {})
                    # Try to get quote by the stock symbol key
                    quote_data = quotes.get(stock_symbol)
                    
                    if quote_data is None:
                        logger.warning(f"[{self.PROVIDER_NAME}] Missing quote data in response: {data}")
                        self._record_request(success=False, latency_ms=latency_ms)
                        self._last_failure_at = datetime.now(timezone.utc)
                        self._cb_record_failure()
                        return None
                    
                    # Extract bid, ask, and timestamp
                    bid = quote_data.get("bp")
                    ask = quote_data.get("ap")
                    timestamp_str = quote_data.get("t")
                    
                    if bid is None or ask is None:
                        logger.warning(f"[{self.PROVIDER_NAME}] Missing bid/ask in quote data: {quote_data}")
                        self._record_request(success=False, latency_ms=latency_ms)
                        self._last_failure_at = datetime.now(timezone.utc)
                        self._cb_record_failure()
                        return None
                    
                    # Calculate spread
                    spread = ask - bid if ask and bid else 0.0
                    
                    # Calculate mid and lastPrice
                    mid = (bid + ask) / 2.0 if bid and ask else 0.0
                    last_price = mid
                    
                    # Parse timestamp
                    timestamp = timestamp_str if timestamp_str else datetime.now(timezone.utc).isoformat()
                    
                except (KeyError, TypeError, ValueError) as e:
                    logger.error(f"[{self.PROVIDER_NAME}] Error parsing stock API response: {e}")
                    self._record_request(success=False, latency_ms=latency_ms)
                    self._last_failure_at = datetime.now(timezone.utc)
                    self._cb_record_failure()
                    return None
            
            # ── Quote Normalization ─────────────────────────────────────
            
            # Build normalized quote dictionary with all required fields
            normalized_quote = {
                "symbol": canonical,                    # Canonical symbol
                "providerTicker": provider_ticker,      # Provider-specific symbol
                "bid": bid,
                "ask": ask,
                "spread": spread,
                "mid": mid,
                "lastPrice": last_price,
                "change": 0.0,                          # Not available from Alpaca
                "changePercent": 0.0,                   # Not available from Alpaca
                "timestamp": timestamp,                 # ISO 8601 format
                "providerId": self.PROVIDER_ID,
                "providerName": self.PROVIDER_NAME,
                "fresh": True,                          # Direct from API, not cached
                "session": "Global" if is_forex else "US Market",  # Session indication
            }
            
            # Record successful request and update circuit breaker
            self._record_request(success=True, latency_ms=latency_ms)
            self._last_success_at = datetime.now(timezone.utc)
            self._cb_record_success()
            return normalized_quote
            
        except requests.Timeout:
            # Network timeout
            latency_ms = (time.perf_counter() - start) * 1000
            self._record_request(success=False, latency_ms=latency_ms)
            self._last_failure_at = datetime.now(timezone.utc)
            self._cb_record_failure(is_timeout=True)
            return None
        
        except requests.RequestException as e:
            # Other HTTP errors
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error(f"[{self.PROVIDER_NAME}] Request error: {e}")
            self._record_request(success=False, latency_ms=latency_ms)
            self._last_failure_at = datetime.now(timezone.utc)
            self._cb_record_failure()
            return None
        
        except Exception as e:
            # Catch-all for unexpected errors
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error(f"[{self.PROVIDER_NAME}] Unexpected error: {e}")
            self._record_request(success=False, latency_ms=latency_ms)
            self._last_failure_at = datetime.now(timezone.utc)
            self._cb_record_failure()
            return None

    # ──────────────────────────────────────────────────────────────────
    # BaseProvider._record_request override to sync .healthy flag
    # ──────────────────────────────────────────────────────────────────

    def _record_request(self, success: bool, latency_ms: float) -> None:
        """Record request metrics and sync healthy flag.
        
        Extends BaseProvider._record_request() to keep .healthy attribute
        consistent with circuit breaker state. Updates consecutive success/failure
        counters synchronized with the circuit breaker logic.
        
        Args:
            success: Whether the request succeeded
            latency_ms: Request latency in milliseconds
        """
        # Call parent implementation to update base metrics
        super()._record_request(success, latency_ms)
        
        # Keep the public .healthy attribute consistent with circuit state
        self.healthy = self.health_check() != ProviderHealth.CRITICAL
