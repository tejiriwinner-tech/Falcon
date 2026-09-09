"""
Falcon Provider Framework — Financial Modeling Prep (FMP) Provider Implementation
Secondary live market data provider (priority 2, between TwelveData and Alpha Vantage).

FMP serves as a secondary provider offering real-time pricing for:
- XAUUSD (Spot Gold)
- GBPUSD (British Pound / US Dollar)
- EURUSD (Euro / US Dollar)
- USDJPY (US Dollar / Japanese Yen)
- BTCUSD (Bitcoin)
- ETHUSD (Ethereum)

Circuit Breaker (finite-state machine):
  CLOSED  --[consecutive_failures >= threshold]-->  OPEN
  OPEN    --[cooldown elapsed]------------------->  HALF_OPEN
  HALF_OPEN --[trial succeeds]------------------->  CLOSED
  HALF_OPEN --[trial fails]---------------------->  OPEN  (restart cooldown)

While OPEN, fetch() returns None immediately without making an HTTP request,
so ProviderManager proceeds to the next provider with zero added latency.

ProviderHealth mapping:
  CLOSED  + ok            → HEALTHY  / status ONLINE
  CLOSED  + degraded      → WARNING / status DEGRADED
  HALF_OPEN               → WARNING  / status DEGRADED
  OPEN (429)              → CRITICAL / status RATE_LIMITED
  OPEN (other)            → CRITICAL / status OFFLINE
  not connected           → CRITICAL / status OFFLINE

API Reference:
- Quote: https://financialmodelingprep.com/developer/docs/#real-time-quote
        https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={key}

FMP API response format (verified via FMP official documentation):
  [
    {
      "symbol": "XAUUSD",
      "price": 318.73,
      "changesPercentage": 1.11,
      "change": 3.49,
      "dayLow": 315.06,
      "dayHigh": 318.74,
      "volume": 34454117,
      "timestamp": 1699123200
    }
  ]

FMP's quote endpoint does not always include bid/ask for forex pairs.
Falcon's established approximation policy (from AlphaVantageProvider) is used:
  bid = ask = mid = price, spread = 0.0
"""
import logging
import re
import time
import threading
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.providers.base_provider import BaseProvider
from app.core.providers.symbol_mapper import symbol_mapper
from app.core.config import settings
from app.core.config.provider_settings import (
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_COOLDOWN_SECONDS,
)
from app.schemas.provider_models import (
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderStatistics,
    ProviderStatus,
    ProviderType,
)

logger = logging.getLogger("falcon.providers.fmp")

# ── Phase 8.3.1 — credential redaction helpers ─────────────────────────────────
# The FMP key must NEVER appear in logs, exceptions, assertion output, reports,
# analytics events, repr(), str(), or any URL fragment that gets printed.
_REDACTED = "[REDACTED]"

_APIKEY_QUERY_RE = re.compile(r"(apikey=)([^&\s\"']*)", re.IGNORECASE)


def redact_fmp_url(text: str) -> str:
    """Replace any ``apikey=...`` query fragment with ``apikey=[REDACTED]``.

    Used for any URL / request text that may need to be logged or surfaced so a
    credential in the query string can never be displayed.
    """
    if not text:
        return text
    return _APIKEY_QUERY_RE.sub(lambda m: m.group(1) + _REDACTED, text)


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


class FmpProvider(BaseProvider):
    """Financial Modeling Prep (FMP) API provider with integrated circuit breaker.

    Serves as a secondary provider (priority 2) between TwelveData (priority 1)
    and AlphaVantage (priority 3). Uses query-parameter authentication (apikey=).

    Circuit Breaker Behavior:
    - CLOSED: Normal operation, all requests proceed
    - OPEN: Blocking mode, returns None immediately (no HTTP requests)
    - HALF_OPEN: Trial mode after cooldown, allows one test request
    """

    PROVIDER_ID = "fmp"
    PROVIDER_NAME = "Financial Modeling Prep"
    PROVIDER_VERSION = "1.0.0"

    # Sentinel distinguishing "constructor arg omitted" from "explicitly passed None".
    # Omitted → use the configured settings.FMP_API_KEY (production default).
    # Explicitly passed (None / "" / literal) → used exactly as given, with NO
    # silent environment fallback in explicit-key contexts (Phase 8.3.1).
    _UNSET = object()

    def __init__(self, api_key: Optional[str] = _UNSET):
        """Initialize FMP provider with circuit breaker protection.

        Args:
            api_key: FMP API key.
                - Omitted entirely → falls back to ``settings.FMP_API_KEY``
                  (the normal production configuration path).
                - Passed explicitly (including ``None`` or ``""``) → used exactly
                  as given. No environment fallback is performed: an explicit
                  absence of a credential stays an absence, so tests/
                  diagnostics/internal explicit-key callers can never silently
                  consume the configured production credential.
        """
        super().__init__(
            provider_id="fmp",
            provider_name="Financial Modeling Prep",
            provider_type="LIVE",
            priority=3,  # Priority 3 (after TwelveData priority 1 and AlphaVantage priority 2)
        )
        self.capabilities = [c.value if hasattr(c, "value") else str(c) for c in _CAPABILITIES]

        # API configuration
        if api_key is self._UNSET:
            effective_key: Optional[str] = settings.FMP_API_KEY or None
        else:
            effective_key = api_key or None
        self._api_key: Optional[str] = effective_key
        self._api_key_configured: bool = self._api_key is not None
        # Phase 8.3.2 — use FMP Stable API base.
        # The legacy /api/v3 endpoint is deprecated and returns HTTP 403 for
        # non-legacy accounts. /stable/quote works for GBPUSD/EURUSD but NOT
        # XAUUSD (plan restriction HTTP 402). The routing matrix already excludes
        # FMP from XAUUSD.
        self._base_url: str = getattr(
            settings, "FMP_BASE_URL", "https://financialmodelingprep.com/stable"
        )
        self._connected: bool = False

        # ── Circuit breaker state ──────────────────────────────────────
        self._cb_state: str = _CB_CLOSED
        self._cb_lock = threading.Lock()

        # Daily budget and rate limiting protections
        self._daily_budget: int = 200  # Hard cap below FMP 250 calls/day free limit
        self._daily_date: str = ""
        self._daily_calls: int = 0
        self._last_call_ts: float = 0.0
        self._quote_cache: Dict[str, tuple] = {}

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

        # ── Circuit lifecycle counters ─────────────────────────────────
        self._circuit_open_count: int = 0    # times circuit transitioned → OPEN
        self._circuit_close_count: int = 0   # times circuit transitioned → CLOSED
        self._recovery_count: int = 0        # alias for close count (explicit recoveries)

        # Flag set in _cb_should_block() to mark that the current fetch is
        # the HALF_OPEN trial. Used by _cb_record_failure() to emit the
        # correct CircuitBreakerReopened event when the trial fails.
        self._is_trial_request: bool = False

                # HTTP session for connection pooling
        self._session = requests.Session()

    def __repr__(self) -> str:
        """Human/debug representation — MUST never include the credential.

        Phase 8.3.1: only a boolean presence flag is surfaced.
        """
        return (
            f"<FmpProvider provider_id={self.PROVIDER_ID!r} "
            f"provider_name={self.PROVIDER_NAME!r} "
            f"priority={self.priority} "
            f"api_key_configured={self._api_key_configured}>"
        )

    def __str__(self) -> str:
        """String representation — MUST never include the credential."""
        return (
            f"FmpProvider(provider_id={self.PROVIDER_ID!r}, "
            f"api_key_configured={self._api_key_configured})"
        )

    def _redact_private(self, text: Any) -> str:
        """Sanitize text before it can reach logs/exceptions/analytics.

        Redacts any ``apikey=...`` query fragment and any occurrence of the
        stored credential itself, replacing it with ``[REDACTED]``.
        """
        if not text:
            return str(text) if text == 0 else ""
        safe = redact_fmp_url(str(text))
        if self._api_key:
            safe = safe.replace(self._api_key, _REDACTED)
        return safe

    # ──────────────────────────────────────────────────────────────────
    # BaseProvider contract
    # ──────────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Establish connection to FMP API.

        Sets _connected flag to True. No actual connection is established
        since we use stateless HTTP requests.

        Returns:
            True if API key is configured, False otherwise
        """
        if not self._api_key:
            logger.warning(
                f"[{self.PROVIDER_NAME}] API key not configured. "
                f"Set FMP_API_KEY environment variable."
            )
            self._connected = False
            return False

        self._connected = True
        logger.info(f"[{self.PROVIDER_NAME}] Connected (api_key configured)")
        return True

    def disconnect(self) -> None:
        """Gracefully close connection."""
        self._connected = False

    @property
    def circuit_breaker_state(self) -> str:
        """Return current circuit breaker state string."""
        with self._cb_lock:
            return self._cb_state

    def _cb_seconds_until_retry(self) -> Optional[float]:
        """Calculate seconds remaining until HALF_OPEN transition."""
        with self._cb_lock:
            if self._cb_state != _CB_OPEN or self._cb_opened_at is None:
                return None
            elapsed = time.monotonic() - self._cb_opened_at
            remaining = CIRCUIT_BREAKER_COOLDOWN_SECONDS - elapsed
            return max(0.0, round(remaining, 1))

    def _cb_should_block(self) -> bool:
        """Determine if request should be blocked by circuit breaker.

        Side effect: Transitions OPEN -> HALF_OPEN when cooldown elapses.

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
                return False  # let this caller through as the trial
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
                self._print_event("CircuitBreakerHalfOpen",
                                  "Cooldown elapsed — allowing trial request")
                return False  # this caller is the trial
            self._is_trial_request = False
            return True  # still cooling down

    def _cb_record_success(self) -> None:
        """Reset circuit breaker after successful request."""
        with self._cb_lock:
            was_open = self._cb_state in (_CB_OPEN, _CB_HALF_OPEN)
            self._cb_state = _CB_CLOSED
            self._consecutive_failures = 0
            self._cb_opened_at = None
            self._last_failure_was_429 = False
            self._is_trial_request = False
            self._last_success_at = datetime.now(timezone.utc)
            if was_open:
                self._circuit_close_count += 1
                self._recovery_count += 1
        if was_open:
            self._print_event("CircuitBreakerClosed", "Trial request succeeded — circuit reset")

    def _print_event(self, event: str, detail: str) -> None:
        """Emit structured event to EventBus.

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

    def health_check(self) -> ProviderHealth:
        """Return current health status based on circuit breaker state."""
        if not self._connected:
            health = ProviderHealth.CRITICAL
        else:
            cb = self.circuit_breaker_state
            if cb == _CB_OPEN:
                health = ProviderHealth.CRITICAL
            elif cb == _CB_HALF_OPEN:
                health = ProviderHealth.WARNING
            else:
                health = ProviderHealth.HEALTHY

        self._print_event("ProviderHeartbeat",
                          f"Alive: {self._connected}, Health: {health.value if hasattr(health, 'value') else str(health)}")
        return health

    def _provider_status(self) -> ProviderStatus:
        """Return provider status based on circuit breaker state."""
        if not self._connected:
            return ProviderStatus.OFFLINE
        cb = self.circuit_breaker_state
        if cb == _CB_OPEN:
            return ProviderStatus.RATE_LIMITED if self._last_failure_was_429 else ProviderStatus.OFFLINE
        if cb == _CB_HALF_OPEN:
            return ProviderStatus.DEGRADED
        return ProviderStatus.ONLINE

    def get_metadata(self) -> ProviderMetadata:
        """Return static provider metadata."""
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
        """Check if provider supports the given capability."""
        return capability in _CAPABILITIES

    def get_statistics(self) -> ProviderStatistics:
        """Return comprehensive provider statistics."""
        total = self._request_count
        success_count = self._success_count
        fail_count = self._fail_count

        success_rate = (success_count / total * 100) if total > 0 else 100.0
        avg_success_latency = (
            self._success_total_latency_ms / success_count
            if success_count > 0
            else 0.0
        )
        avg_failure_latency = (
            self._failure_total_latency_ms / fail_count
            if fail_count > 0
            else 0.0
        )

        return ProviderStatistics(
            totalRequests=total,
            successfulRequests=success_count,
            failedRequests=fail_count,
            successRate=round(success_rate, 2),
            consecutiveFailures=self._consecutive_failures,
            circuitBreakerState=self.circuit_breaker_state,
            circuitRetryInSeconds=self._cb_seconds_until_retry(),
            http429Count=self._http_429_count,
            timeoutCount=self._timeout_count,
            lastSuccessAt=self._last_success_at,
            lastFailureAt=self._last_failure_at,
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

    def _cb_record_failure(self, is_429: bool = False, is_timeout: bool = False) -> None:
        """Record request failure and potentially open circuit."""
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
            self._is_trial_request = False

            if self._consecutive_failures >= CIRCUIT_BREAKER_FAILURE_THRESHOLD:
                if self._cb_state != _CB_OPEN:
                    self._cb_state = _CB_OPEN
                    self._cb_opened_at = time.monotonic()
                    self._circuit_open_count += 1
                    if is_429:
                        reason = "HTTP 429 rate limit"
                    elif is_timeout:
                        reason = "timeout"
                    else:
                        reason = "other"
                    self._print_event(
                        "CircuitBreakerOpen",
                        f"Circuit opened after {self._consecutive_failures} consecutive "
                        f"failures ({reason}). Cooldown: {CIRCUIT_BREAKER_COOLDOWN_SECONDS}s",
                    )
                elif was_trial:
                    self._cb_opened_at = time.monotonic()
                    self._circuit_open_count += 1
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
                    self._cb_opened_at = time.monotonic()

    def fetch(self, symbol: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetch real-time market quote for the given symbol.

        Credential contract (Phase 8.3.1): this method has NO runtime
        ``api_key`` parameter. It always authenticates with the credential fixed
        at construction time. An ``api_key`` keyword supplied at runtime is
        intentionally ignored (never echoed, never substituted), so there is no
        path by which a per-call key — explicit or fallback — can leak or be
        silently swapped for the configured production credential.
        """
        t0 = time.time()

        canonical = symbol_mapper.normalize(symbol)
        if canonical is None:
            canonical = symbol.upper()

        now_ts = time.time()
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Daily budget reset at 00:00 UTC
        if self._daily_date != today_utc:
            self._daily_date = today_utc
            self._daily_calls = 0

        # Check in-memory 60s cache first to protect FMP free API quota
        cached = self._quote_cache.get(canonical)
        if cached:
            cached_time, cached_data = cached
            if now_ts - cached_time < 60.0:
                self._record_request(True, 1.0)
                return cached_data

        # Session budget gate: in STANDBY mode (night or weekend), permit zero external network calls
        from app.core.services.session_budget_manager import session_budget_manager
        if not session_budget_manager.is_active():
            if cached and (now_ts - cached[0]) < 3600.0:
                return cached[1]
            return None

        # Daily budget protection gate
        if self._daily_calls >= self._daily_budget:
            logger.warning(f"[{self.PROVIDER_NAME}] Daily budget of {self._daily_budget} calls reached for {today_utc}. Skipping fetch.")
            self._record_request(False, 0.0)
            return None

        # Pre-flight checks
        if not self._api_key:
            logger.warning(f"[{self.PROVIDER_NAME}] API key not configured")
            self._record_request(False, (time.time() - t0) * 1000)
            return None

        if not self._connected:
            return None

        if self._cb_should_block():
            self._record_request(False, (time.time() - t0) * 1000)
            return None

        self._last_call_ts = time.time()
        self._daily_calls += 1

        provider_ticker = symbol_mapper.to_provider_symbol(canonical, self.PROVIDER_ID)

        # API request — Phase 8.3.2: FMP Stable API uses /stable/quote with
        # `symbol` as a query parameter, not a path segment.
        url = f"{self._base_url}/quote"
        params = {"symbol": provider_ticker, "apikey": self._api_key}
        timeout = 10.0

        start = time.perf_counter()
        try:
            response = self._session.get(url, params=params, timeout=timeout)
            latency_ms = (time.perf_counter() - start) * 1000

            if response.status_code == 429:
                logger.warning(f"[{self.PROVIDER_NAME}] Rate limited (HTTP 429)")
                self._record_request(False, latency_ms)
                self._last_failure_at = datetime.now(timezone.utc)
                self._cb_record_failure(is_429=True)
                return None

            if response.status_code != 200:
                logger.error(f"[{self.PROVIDER_NAME}] HTTP {response.status_code}")
                self._record_request(False, latency_ms)
                self._last_failure_at = datetime.now(timezone.utc)
                self._cb_record_failure()
                return None

            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"[{self.PROVIDER_NAME}] JSON error: {self._redact_private(e)}")
                self._record_request(False, latency_ms)
                self._last_failure_at = datetime.now(timezone.utc)
                self._cb_record_failure()
                return None

            if isinstance(data, dict) and "Error Message" in data:
                logger.error(
                    f"[{self.PROVIDER_NAME}] API error: "
                    f"{self._redact_private(data['Error Message'])}"
                )
                self._record_request(False, latency_ms)
                self._last_failure_at = datetime.now(timezone.utc)
                self._cb_record_failure()
                return None

            if not isinstance(data, list) or len(data) == 0:
                logger.warning(f"[{self.PROVIDER_NAME}] Empty response for {canonical}")
                self._record_request(False, latency_ms)
                self._last_failure_at = datetime.now(timezone.utc)
                self._cb_record_failure()
                return None

            quote_data = data[0]
            resp_symbol = quote_data.get("symbol", "")
            if resp_symbol and resp_symbol.upper() != canonical.upper():
                logger.warning(f"[{self.PROVIDER_NAME}] Symbol mismatch")
                self._record_request(False, latency_ms)
                self._last_failure_at = datetime.now(timezone.utc)
                self._cb_record_failure()
                return None

            price = quote_data.get("price")
            if price is None:
                logger.error(f"[{self.PROVIDER_NAME}] Price not found for {canonical}")
                self._record_request(False, latency_ms)
                self._last_failure_at = datetime.now(timezone.utc)
                self._cb_record_failure()
                return None

            price = float(price)
            if price <= 0:
                logger.error(f"[{self.PROVIDER_NAME}] Invalid price {price}")
                self._record_request(False, latency_ms)
                self._last_failure_at = datetime.now(timezone.utc)
                self._cb_record_failure()
                return None

            # Extract change data
            change = float(quote_data.get("change", 0) or 0)
            change_percent = float(quote_data.get("changesPercentage", 0) or 0)

            # Bid/ask handling
            bid = quote_data.get("bid")
            ask = quote_data.get("ask")
            if bid is not None and ask is not None:
                bid = float(bid)
                ask = float(ask)
                if bid <= 0 or ask <= 0:
                    bid = round(price, 5)
                    ask = round(price, 5)
            else:
                bid = round(price, 5)
                ask = round(price, 5)

            spread = ask - bid if ask > bid else 0.0
            mid = round((bid + ask) / 2.0, 5)
            last_price = round(price, 5)

            # Parse timestamp — Phase 8.3: never fabricate a server timestamp
            # just to make the quote appear fresh. A missing/unparseable server
            # timestamp is invalid provider data → allow fallback.
            ts_raw = quote_data.get("timestamp")
            if ts_raw is None:
                logger.warning(f"[{self.PROVIDER_NAME}] Missing server timestamp for {canonical}")
                self._record_request(False, latency_ms)
                self._last_failure_at = datetime.now(timezone.utc)
                self._cb_record_failure()
                return None
            try:
                ts = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)
                timestamp = ts.isoformat()
            except (ValueError, TypeError, OSError):
                logger.warning(f"[{self.PROVIDER_NAME}] Unparseable server timestamp for {canonical}")
                self._record_request(False, latency_ms)
                self._last_failure_at = datetime.now(timezone.utc)
                self._cb_record_failure()
                return None

            # Build normalized quote
            result = {
                "symbol": canonical,
                "providerTicker": provider_ticker,
                "bid": bid,
                "ask": ask,
                "spread": round(spread, 5),
                "mid": mid,
                "lastPrice": last_price,
                "change": round(change, 5),
                "changePercent": round(change_percent, 5),
                "timestamp": timestamp,
                "providerId": self.PROVIDER_ID,
                "providerName": self.PROVIDER_NAME,
                "fresh": True,
                "session": "London-NY",
                "_instrumentType": "FOREX" if "USD" in canonical else "UNKNOWN",
                "_dataSource": "FMP",
            }

            logger.info(f"[{self.PROVIDER_NAME}] {canonical} Quote: {last_price}")
            self._quote_cache[canonical] = (now_ts, result)
            self._record_request(True, latency_ms)
            self._cb_record_success()
            return result

        except requests.Timeout:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.warning(f"[{self.PROVIDER_NAME}] Timeout for {canonical}")
            self._record_request(False, latency_ms)
            self._last_failure_at = datetime.now(timezone.utc)
            self._cb_record_failure(is_timeout=True)
            return None

        except requests.ConnectionError as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error(f"[{self.PROVIDER_NAME}] Connection error: {self._redact_private(e)}")
            self._record_request(False, latency_ms)
            self._last_failure_at = datetime.now(timezone.utc)
            self._cb_record_failure()
            return None

        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error(f"[{self.PROVIDER_NAME}] Unexpected error: {self._redact_private(e)}")
            self._record_request(False, latency_ms)
            self._last_failure_at = datetime.now(timezone.utc)
            self._cb_record_failure()
            return None