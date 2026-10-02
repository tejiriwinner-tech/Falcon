"""
Falcon Provider Framework — Provider Manager
High-level interface used by all intelligence engines to request market data.

Phase 4.3.8 hardening:
  - State-aware provider skip: RATE_LIMITED / OPEN / OFFLINE providers are
    bypassed immediately (no network call, zero latency penalty).
  - Adaptive cache TTL: TTL passed to MarketDataCache is chosen based on the
    supplying provider's current status and aggregate success rate.
  - Cold vs warm timing tracked in get_performance_metrics().
"""
import json
import logging
import time
import threading
from concurrent.futures import Future
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from app.core.providers.provider_registry import ProviderRegistry
from app.core.providers.cache import MarketDataCache, compute_adaptive_ttl
from app.core.providers.symbol_mapper import SymbolMapper
from app.core.providers.quote_validator import quote_validator
from app.schemas.provider_models import (
    ProviderCapability,
    ProviderHealth,
    ProviderStatus,
)
from app.schemas.market_quote import (
    MarketQuote,
    BidAsk,
    QuoteStatus,
    MarketStatus,
    MarketQuoteResponse,
)

logger = logging.getLogger(__name__)

# Statuses that mean "skip this provider entirely — no network call"
_SKIP_STATUSES = {ProviderStatus.RATE_LIMITED, ProviderStatus.OFFLINE}

# Instrument-aware provider routing matrix (canonical -> ordered allowed providers)
# GBPUSD / GPBUSD is prioritized with FMP (sub-second real-time quotes); ALL other instruments strictly exclude FMP
_INSTRUMENT_PROVIDER_ROUTE: Dict[str, List[str]] = {
    "XAUUSD": ["twelve_data", "alpha_vantage", "mock_provider"],
    "GBPUSD": ["fmp", "twelve_data", "alpha_vantage", "mock_provider"],
    "GPBUSD": ["fmp", "twelve_data", "alpha_vantage", "mock_provider"],
    "EURUSD": ["twelve_data", "alpha_vantage", "mock_provider"],
}
_DEFAULT_PROVIDER_ROUTE: List[str] = ["twelve_data", "alpha_vantage", "mock_provider"]

_EVT_PROVIDER_SKIPPED_UNSUPPORTED = "ProviderSkippedUnsupported"


class ProviderManager:
    """Falcon's market data distribution hub."""

    def __init__(
        self,
        registry: ProviderRegistry,
        cache: MarketDataCache,
        symbol_mapper: SymbolMapper,
    ):
        self._registry = registry
        self._cache = cache
        self._mapper = symbol_mapper

        # ── Aggregate counters ─────────────────────────────────────────
        self._total_requests: int = 0
        self._successful_requests: int = 0
        self._failed_requests: int = 0
        self._failover_count: int = 0

        # ── Phase 4.3.8 timing accumulators ───────────────────────────
        self._cold_request_count: int = 0
        self._cold_total_ms: float = 0.0
        self._warm_request_count: int = 0   # cache hits
        self._warm_total_ms: float = 0.0

        self._lock = threading.Lock()
        self._pending_requests: Dict[str, Future] = {}

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def get_market_quote(self, raw_symbol: str) -> Optional[MarketQuoteResponse]:
        """Return a normalized MarketQuoteResponse for the given symbol."""
        t_start = time.time()
        self._total_requests += 1
        canonical = self._mapper.normalize(raw_symbol)
        if canonical is None:
            self._failed_requests += 1
            return None

        # ── Single-Flight + Cache ──────────────────────────────────────
        with self._lock:
            cached_entry = self._cache.get(canonical, allow_stale=True)
            if cached_entry is not None:
                quote = cached_entry.data
                if isinstance(quote, MarketQuote):
                    quote.freshnessSeconds = cached_entry.age_seconds
                    self._successful_requests += 1
                    elapsed_ms = (time.time() - t_start) * 1000
                    self._warm_request_count += 1
                    self._warm_total_ms += elapsed_ms
                    return MarketQuoteResponse(quote=quote)

            if canonical in self._pending_requests:
                future = self._pending_requests[canonical]
                already_fetching = True
            else:
                future = Future()
                self._pending_requests[canonical] = future
                already_fetching = False

        if already_fetching:
            return future.result()

        try:
            result = self._fetch_from_providers(canonical)
            future.set_result(result)
            elapsed_ms = (time.time() - t_start) * 1000
            self._cold_request_count += 1
            self._cold_total_ms += elapsed_ms
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            with self._lock:
                self._pending_requests.pop(canonical, None)

    # ──────────────────────────────────────────────────────────────────
    # Internal fetch with state-aware skip + adaptive TTL
    # ──────────────────────────────────────────────────────────────────

    def _compute_quote_age_seconds(self, ts: Any) -> float:
        try:
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            if isinstance(ts, datetime):
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                return max(0.0, age)
        except Exception:
            pass
        return 0.0

    def _get_candidate_providers(self, canonical: str) -> List[Any]:
        allowed_route = _INSTRUMENT_PROVIDER_ROUTE.get(canonical, _DEFAULT_PROVIDER_ROUTE)
        all_live = self._registry.get_by_capability(ProviderCapability.LIVE_PRICE)
        live_map = {p.provider_id: p for p in all_live}
        candidates = []
        for pid in allowed_route:
            # Absolute guard: FMP must NEVER be invoked for any pair except GBPUSD / GPBUSD
            if pid == "fmp" and canonical not in ("GBPUSD", "GPBUSD"):
                continue
            if pid in live_map:
                provider = live_map[pid]
                if hasattr(provider, "supports_symbol") and not provider.supports_symbol(canonical):
                    continue
                candidates.append(provider)
        return candidates

    def _fetch_from_providers(self, canonical: str) -> Optional[MarketQuoteResponse]:
        """Query providers in priority order.

        Phase 4.3.8 additions:
          1. State-aware skip: providers in RATE_LIMITED / OFFLINE state are
             skipped without calling fetch(), preserving latency budget.
          2. Adaptive TTL: the TTL stored in cache reflects provider reliability.
        """
        # Emit event for any registered LIVE_PRICE provider not in allowed route
        allowed_route = _INSTRUMENT_PROVIDER_ROUTE.get(canonical, _DEFAULT_PROVIDER_ROUTE)
        all_live = self._registry.get_by_capability(ProviderCapability.LIVE_PRICE)
        for p in all_live:
            if p.provider_id not in allowed_route:
                evt = {
                    "eventName": _EVT_PROVIDER_SKIPPED_UNSUPPORTED,
                    "providerId": p.provider_id,
                    "symbol": canonical,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                logger.info(json.dumps(evt))

        providers = self._get_candidate_providers(canonical)
        attempted_failed_providers: List[str] = []

        for idx, provider in enumerate(providers):
            p_id   = provider.provider_id
            p_name = provider.provider_name

            # ── Gate 1: health_check() — handles circuit-OPEN state ───
            if provider.health_check() == ProviderHealth.CRITICAL:
                attempted_failed_providers.append(p_name)
                continue

            # ── Gate 2: status-aware skip (Phase 4.3.8) ───────────────
            # Retrieve status without calling fetch() — zero network cost.
            try:
                p_status = provider.get_metadata().status
            except Exception:
                p_status = ProviderStatus.OFFLINE

            if p_status in _SKIP_STATUSES:
                # Provider is rate-limited or offline — skip entirely.
                attempted_failed_providers.append(p_name)
                continue

            # ── Attempt fetch ──────────────────────────────────────────
            raw_data = provider.fetch(canonical)
            if raw_data is None:
                attempted_failed_providers.append(p_name)
                continue

            # ── Quote validation ───────────────────────────────────────
            is_valid, failure_reason = quote_validator.validate(raw_data, canonical)
            if not is_valid:
                quote_validator.emit_failure_event(
                    p_id, canonical, failure_reason or "Validation failed"
                )
                attempted_failed_providers.append(p_name)
                continue

            # ── Failover event ─────────────────────────────────────────
            if idx > 0 and attempted_failed_providers:
                self._failover_count += 1
                self._emit_failover_event(
                    from_provider=attempted_failed_providers[0],
                    to_provider=p_name,
                    reason=(
                        f"Primary provider {attempted_failed_providers[0]} "
                        "unavailable or failed validation"
                    ),
                )

            # ── Build immutable MarketQuote ────────────────────────────
            freshness = self._compute_quote_age_seconds(raw_data.get("timestamp"))
            quote = MarketQuote(
                symbol=canonical,
                bidAsk=BidAsk(
                    bid=raw_data["bid"],
                    ask=raw_data["ask"],
                    spread=raw_data["spread"],
                ),
                lastPrice=raw_data.get("lastPrice", raw_data.get("mid", 0.0)),
                change=raw_data.get("change", 0.0),
                changePercent=raw_data.get("changePercent", 0.0),
                timestamp=(
                    datetime.fromisoformat(raw_data["timestamp"])
                    if isinstance(raw_data["timestamp"], str)
                    else raw_data["timestamp"]
                ),
                providerId=p_id,
                providerName=p_name,
                quoteStatus=QuoteStatus.LIVE,
                marketStatus=MarketStatus.OPEN,
                freshnessSeconds=freshness,
            )

            # ── Adaptive TTL ───────────────────────────────────────────
            stats = provider.get_statistics()
            adaptive_ttl = compute_adaptive_ttl(
                provider_status=p_status.value,
                success_rate=stats.successRate,
            )

            self._cache.set(
                symbol=canonical,
                data=quote,
                provider_id=p_id,
                provider_name=p_name,
                ttl=adaptive_ttl,
            )

            self._successful_requests += 1
            return MarketQuoteResponse(quote=quote)

        # All providers failed / skipped — return None (empty state as requested, zero mock data)
        self._failed_requests += 1
        return None

    # ──────────────────────────────────────────────────────────────────
    # Backward compatibility
    # ──────────────────────────────────────────────────────────────────

    def get_market_data(self, raw_symbol: str) -> Optional[Any]:
        resp = self.get_market_quote(raw_symbol)
        if resp is None:
            return None
        quote = resp.quote
        from app.schemas.provider_models import MarketDataSnapshot, MarketQuote as LegacyQuote
        legacy = LegacyQuote(
            symbol=quote.symbol,
            bid=quote.bidAsk.bid,
            ask=quote.bidAsk.ask,
            spread=quote.bidAsk.spread,
            spreadPips=quote.bidAsk.spread,
            mid=quote.lastPrice,
            timestamp=quote.timestamp,
            providerId=quote.providerId,
            fresh=True,
            session="London-NY",
        )
        return MarketDataSnapshot(
            symbol=raw_symbol,
            normalizedSymbol=quote.symbol,
            quote=legacy,
            fetchedAt=datetime.now(timezone.utc),
            cacheTtlSeconds=10,
            cacheHit=False,
        )

    def get_quote(self, raw_symbol: str) -> Optional[Dict[str, Any]]:
        """Return a normalized quote dictionary for intelligence engines."""
        resp = self.get_market_quote(raw_symbol)
        if resp is None or resp.quote is None:
            return None
        q = resp.quote
        mid_val = getattr(q.bidAsk, "mid", None) or q.lastPrice
        return {
            "symbol": q.symbol,
            "mid": mid_val,
            "lastPrice": q.lastPrice,
            "bid": q.bidAsk.bid,
            "ask": q.bidAsk.ask,
            "spread": q.bidAsk.spread,
            "providerId": q.providerId,
            "providerName": q.providerName,
            "timestamp": q.timestamp.isoformat() if hasattr(q.timestamp, "isoformat") else str(q.timestamp),
        }

    def supported_symbols(self) -> List[str]:
        return self._mapper.supported_symbols()

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Return provider framework performance metrics including cold/warm timings."""
        success_rate = (
            (self._successful_requests / self._total_requests * 100)
            if self._total_requests > 0
            else 100.0
        )
        avg_cold_ms = (
            self._cold_total_ms / self._cold_request_count
            if self._cold_request_count > 0
            else 0.0
        )
        avg_warm_ms = (
            self._warm_total_ms / self._warm_request_count
            if self._warm_request_count > 0
            else 0.0
        )
        return {
            "totalRequests": self._total_requests,
            "successfulRequests": self._successful_requests,
            "failedRequests": self._failed_requests,
            "failoverCount": self._failover_count,
            "successRate": round(success_rate, 2),
            "cacheStats": self._cache.stats,
            # Phase 4.3.8
            "coldRequests": self._cold_request_count,
            "warmRequests": self._warm_request_count,
            "avgColdRequestMs": round(avg_cold_ms, 2),
            "avgWarmRequestMs": round(avg_warm_ms, 2),
        }

    # ──────────────────────────────────────────────────────────────────
    # Internal event helpers
    # ──────────────────────────────────────────────────────────────────

    def _emit_failover_event(
        self, from_provider: str, to_provider: str, reason: str
    ) -> None:
        payload = {
            "eventName": "ProviderFailover",
            "fromProvider": from_provider,
            "toProvider": to_provider,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(f"[EVENT BUS] {json.dumps(payload)}")
