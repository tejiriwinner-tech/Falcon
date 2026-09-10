"""
Falcon Provider Framework — Twelve Data Provider Implementation
Primary live market data provider abstraction.

Phase 4.3.7 additions
─────────────────────
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
"""
import time
import threading
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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


class TwelveDataProvider(BaseProvider):
    """Twelve Data API provider with an integrated circuit breaker."""

    PROVIDER_ID = "twelve_data"
    PROVIDER_NAME = "TwelveData"
    PROVIDER_VERSION = "1.1.0"   # bumped for Phase 4.3.7

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            provider_id="twelve_data",
            provider_name="TwelveData",
            provider_type="LIVE",
            priority=1,
        )
        self.capabilities = [c.value if hasattr(c, "value") else str(c) for c in _CAPABILITIES]
        self._api_key: Optional[str] = (
            api_key
            or settings.TWELVEDATA_API_KEY
            or os.getenv("TWELVE_DATA_API_KEY")
            or os.getenv("TWELVEDATA_API_KEY")
        )
        self._base_url: str = settings.TWELVEDATA_BASE_URL
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
        self._quote_cache: Dict[str, Dict[str, Any]] = {}
        self._daily_budget: int = 700  # Hard cap below TwelveData 800/day free limit
        self._daily_date: str = ""
        self._daily_calls: int = 0
        self._last_call_ts: float = 0.0

        # ── Extended statistics ────────────────────────────────────────
        self._http_429_count: int = 0
        self._timeout_count: int = 0
        self._last_success_at: Optional[datetime] = None
        self._last_failure_at: Optional[datetime] = None

        # ── Phase 4.3.8 circuit lifecycle counters ────────────────────
        self._circuit_open_count: int = 0    # times circuit transitioned → OPEN
        self._circuit_close_count: int = 0   # times circuit transitioned → CLOSED
        self._recovery_count: int = 0        # alias for close count (explicit recoveries)

        # Flag set in _cb_should_block() to mark that the current fetch is the
        # HALF_OPEN trial.  Used by _cb_record_failure() to emit the correct
        # CircuitBreakerReopened event when the trial fails.
        self._is_trial_request: bool = False

    # ──────────────────────────────────────────────────────────────────
    # BaseProvider contract
    # ──────────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    # ──────────────────────────────────────────────────────────────────
    # Circuit breaker helpers
    # ──────────────────────────────────────────────────────────────────

    @property
    def circuit_breaker_state(self) -> str:
        """Return current circuit breaker state string (CLOSED | OPEN | HALF_OPEN)."""
        with self._cb_lock:
            if self._cb_state == _CB_OPEN and self._cb_opened_at is not None:
                elapsed = time.monotonic() - self._cb_opened_at
                if elapsed >= CIRCUIT_BREAKER_COOLDOWN_SECONDS:
                    self._cb_state = _CB_HALF_OPEN
            return self._cb_state

    def _cb_seconds_until_retry(self) -> Optional[float]:
        """Return seconds remaining until OPEN → HALF_OPEN transition, or None."""
        with self._cb_lock:
            if self._cb_state != _CB_OPEN or self._cb_opened_at is None:
                return None
            elapsed = time.monotonic() - self._cb_opened_at
            remaining = CIRCUIT_BREAKER_COOLDOWN_SECONDS - elapsed
            return max(0.0, round(remaining, 1))

    def _cb_should_block(self) -> bool:
        """Return True if the circuit is OPEN and the cooldown has NOT yet expired.

        Side-effect: transitions OPEN → HALF_OPEN when the cooldown has elapsed.
        Must be called while NOT holding _cb_lock (acquires it internally).
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
                self._print_event("CircuitBreakerHalfOpen",
                                  "Cooldown elapsed — allowing trial request")
                return False   # this caller is the trial
            self._is_trial_request = False
            return True        # still cooling down

    def _cb_record_success(self) -> None:
        """Reset circuit breaker after a successful request."""
        with self._cb_lock:
            was_open = self._cb_state in (_CB_OPEN, _CB_HALF_OPEN)
            self._cb_state = _CB_CLOSED
            self._consecutive_failures = 0
            self._cb_opened_at = None
            self._last_failure_was_429 = False
            self._is_trial_request = False
            if was_open:
                self._circuit_close_count += 1
                self._recovery_count += 1
        if was_open:
            self._print_event("CircuitBreakerClosed", "Trial request succeeded — circuit reset")

    def _cb_record_failure(self, is_429: bool = False, is_timeout: bool = False) -> None:
        """Increment failure counter and open the circuit when threshold is reached."""
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
                    reason = "HTTP 429 rate limit" if is_429 else "repeated upstream failures"
                    self._print_event(
                        "CircuitBreakerOpen",
                        f"Circuit opened after {self._consecutive_failures} consecutive "
                        f"failures ({reason}). Cooldown: {CIRCUIT_BREAKER_COOLDOWN_SECONDS}s",
                    )
                elif was_trial:
                    # Already OPEN, and this failure was the HALF_OPEN trial
                    self._cb_opened_at = time.monotonic()   # restart cooldown
                    self._circuit_open_count += 1
                    reason = "HTTP 429 rate limit" if is_429 else "upstream failure"
                    self._print_event(
                        "CircuitBreakerReopened",
                        f"Trial request failed — circuit reopened ({reason}). "
                        f"Cooldown: {CIRCUIT_BREAKER_COOLDOWN_SECONDS}s",
                    )
                else:
                    # Already open, normal blocked-but-leaked failure — restart cooldown
                    self._cb_opened_at = time.monotonic()

    def _print_event(self, event: str, detail: str) -> None:
        import json as _json
        payload = {
            "eventName": event,
            "providerId": self.PROVIDER_ID,
            "providerName": self.PROVIDER_NAME,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(f"[EVENT BUS] {_json.dumps(payload)}")

    # ──────────────────────────────────────────────────────────────────
    # Health / metadata
    # ──────────────────────────────────────────────────────────────────

    def health_check(self) -> ProviderHealth:
        if not self._connected:
            return ProviderHealth.CRITICAL
        cb = self.circuit_breaker_state
        if cb == _CB_OPEN:
            return ProviderHealth.CRITICAL
        if cb == _CB_HALF_OPEN:
            return ProviderHealth.WARNING
        # CLOSED — healthy
        return ProviderHealth.HEALTHY

    def _provider_status(self) -> ProviderStatus:
        """Map circuit breaker state to a meaningful ProviderStatus."""
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
        """Return enriched statistics including circuit breaker state and health scores."""
        sr = (
            (self._success_count / self._request_count * 100)
            if self._request_count > 0
            else 100.0
        )
        avg_success_lat = (
            self._success_total_latency_ms / self._success_count
            if self._success_count > 0
            else 0.0
        )
        avg_fail_lat = (
            self._failure_total_latency_ms / self._fail_count
            if self._fail_count > 0
            else 0.0
        )
        return ProviderStatistics(
            totalRequests=self._request_count,
            successfulRequests=self._success_count,
            failedRequests=self._fail_count,
            successRate=round(sr, 2),
            # Phase 4.3.7
            consecutiveFailures=self._consecutive_failures,
            http429Count=self._http_429_count,
            timeoutCount=self._timeout_count,
            lastSuccessAt=self._last_success_at,
            lastFailureAt=self._last_failure_at,
            circuitBreakerState=self.circuit_breaker_state,
            circuitRetryInSeconds=self._cb_seconds_until_retry(),
            # Phase 4.3.8
            uptimePercent=round(sr, 2),
            avgSuccessLatencyMs=round(avg_success_lat, 2),
            avgFailureLatencyMs=round(avg_fail_lat, 2),
            consecutiveSuccesses=self._consecutive_successes,
            recoveryCount=self._recovery_count,
            circuitOpenCount=self._circuit_open_count,
            circuitCloseCount=self._circuit_close_count,
            lastSuccessfulQuoteAt=self._last_success_at,
            lastFailedRequestAt=self._last_failure_at,
        )

    def get_metadata(self) -> ProviderMetadata:
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
        return capability in _CAPABILITIES

    # ──────────────────────────────────────────────────────────────────
    # Core fetch — guarded by circuit breaker
    # ──────────────────────────────────────────────────────────────────

    def fetch(self, symbol: str, **kwargs) -> Optional[Dict[str, Any]]:
        t0 = time.time()
        canonical = symbol_mapper.normalize(symbol) or symbol.upper()
        now_ts = time.time()
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Daily budget reset at 00:00 UTC
        if self._daily_date != today_utc:
            self._daily_date = today_utc
            self._daily_calls = 0

        # Check in-memory quote cache (60-second TTL to conserve free API calls)
        cached = self._quote_cache.get(canonical)
        if cached and (now_ts - cached["fetched_at"]) < 60.0:
            return cached["data"]

        # Session budget gate: in STANDBY mode (night or weekend) or if hourly quota reached, permit zero external network calls
        from app.core.services.session_budget_manager import session_budget_manager
        if not session_budget_manager.can_consume_call():
            # If recently cached data is available, serve it without outbound network request
            if cached and (now_ts - cached["fetched_at"]) < 3600.0:
                return cached["data"]
            return None

        # Daily budget protection gate — never exceed free tier limit
        if self._daily_calls >= self._daily_budget:
            print(f"[{self.PROVIDER_NAME}] Daily budget of {self._daily_budget} calls reached for {today_utc}. Skipping fetch to avoid over-limit.")
            self._record_request(False, 0.0)
            return None

        # Rate limiter gate: minimum 7.5 seconds between outbound requests (8 req/min limit)
        if (now_ts - self._last_call_ts) < 7.5:
            # If rate limited, return cached if exists, or return None without sending HTTP
            if cached:
                return cached["data"]
            return None

        # ── Circuit breaker gate ───────────────────────────────────────
        if self._cb_should_block():
            # Circuit is OPEN and cooldown has not elapsed.
            # Return None immediately — no network request.
            retry_in = self._cb_seconds_until_retry()
            print(
                f"[{self.PROVIDER_NAME}] Circuit OPEN — skipping request for {canonical}. "
                f"Retry in {retry_in}s."
            )
            self._record_request(False, 0.0)
            self._last_failure_at = datetime.now(timezone.utc)
            return None

        if not self._connected:
            self._cb_record_failure()
            self._record_request(False, (time.time() - t0) * 1000)
            self._last_failure_at = datetime.now(timezone.utc)
            return None

        ticker = symbol_mapper.to_provider_symbol(canonical, self.PROVIDER_ID)

        if not self._api_key:
            print(f"[{self.PROVIDER_NAME}] Missing API key for live fetch.")
            self._cb_record_failure()
            self._record_request(False, (time.time() - t0) * 1000)
            self._last_failure_at = datetime.now(timezone.utc)
            return None

        self._last_call_ts = time.time()
        self._daily_calls += 1
        session_budget_manager.record_call(self.PROVIDER_ID)

        try:
            params = {"symbol": ticker, "apikey": self._api_key}
            response = requests.get(
                f"{self._base_url}/quote", params=params, timeout=5.0
            )

            # ── HTTP error handling ────────────────────────────────────
            if response.status_code != 200:
                is_429 = response.status_code == 429
                print(f"[{self.PROVIDER_NAME}] HTTP {response.status_code}: {response.text[:200]}")
                self._cb_record_failure(is_429=is_429)
                self._record_request(False, (time.time() - t0) * 1000)
                self._last_failure_at = datetime.now(timezone.utc)
                return None

            data = response.json()

            # TwelveData returns HTTP 200 but embeds error in body (e.g. plan limit)
            if data.get("status") == "error":
                msg = data.get("message", "")
                is_429 = "credits" in msg.lower() or "limit" in msg.lower() or data.get("code") == 429
                print(f"[{self.PROVIDER_NAME}] API Error: {msg}")
                self._cb_record_failure(is_429=is_429)
                self._record_request(False, (time.time() - t0) * 1000)
                self._last_failure_at = datetime.now(timezone.utc)
                return None

            # ── Parse response ─────────────────────────────────────────
            last_price = float(
                data.get("close") or data.get("last") or data.get("price") or 0.0
            )
            if not last_price:
                self._cb_record_failure()
                self._record_request(False, (time.time() - t0) * 1000)
                self._last_failure_at = datetime.now(timezone.utc)
                return None

            raw_bid = data.get("bid")
            raw_ask = data.get("ask")
            if raw_bid is not None and raw_ask is not None:
                bid    = float(raw_bid)
                ask    = float(raw_ask)
                spread = round(ask - bid, 5)
                mid    = round((bid + ask) / 2, 5)
            else:
                bid = ask = mid = last_price
                spread = 0.0

            change         = float(data.get("change") or 0.0)
            change_percent = float(data.get("percent_change") or 0.0)
            timestamp_sec  = data.get("timestamp")
            ts = (
                datetime.fromtimestamp(int(timestamp_sec), tz=timezone.utc).isoformat()
                if timestamp_sec
                else datetime.now(timezone.utc).isoformat()
            )

            result = {
                "symbol":        canonical,
                "providerTicker": ticker,
                "bid":           bid,
                "ask":           ask,
                "spread":        spread,
                "mid":           mid,
                "lastPrice":     last_price,
                "change":        change,
                "changePercent": change_percent,
                "timestamp":     ts,
                "providerId":    self.PROVIDER_ID,
                "providerName":  self.PROVIDER_NAME,
                "fresh":         True,
                "session":       "Global",
            }

            latency = (time.time() - t0) * 1000
            self._cb_record_success()
            self._record_request(True, latency)
            self._last_success_at = datetime.now(timezone.utc)
            self._quote_cache[canonical] = {"data": result, "fetched_at": time.time()}
            return result

        except requests.Timeout:
            print(f"[{self.PROVIDER_NAME}] Timeout fetching {canonical}")
            self._cb_record_failure(is_timeout=True)
            self._record_request(False, (time.time() - t0) * 1000)
            self._last_failure_at = datetime.now(timezone.utc)
            return None

        except Exception as exc:
            print(f"[{self.PROVIDER_NAME}] Exception during fetch: {exc}")
            self._cb_record_failure()
            self._record_request(False, (time.time() - t0) * 1000)
            self._last_failure_at = datetime.now(timezone.utc)
            return None

    # ──────────────────────────────────────────────────────────────────
    # BaseProvider._record_request override to sync .healthy flag
    # ──────────────────────────────────────────────────────────────────

    def _record_request(self, success: bool, latency_ms: float) -> None:
        """Extend base metrics recording and keep .healthy in sync."""
        super()._record_request(success, latency_ms)
        # Keep the public .healthy attribute consistent with circuit state
        self.healthy = self.health_check() != ProviderHealth.CRITICAL
