"""
Falcon Provider Framework — __init__.py
Auto-wires the provider framework on first import.

Phase 4.3.9: The ProviderAnalyticsEngine is wired as an observer.
Events are injected by monkey-patching _print_event on TwelveDataProvider
and by registering a hook in ProviderManager via subclassing.
No intelligence logic is modified.
"""
from app.core.config import settings
from app.core.providers.cache import market_cache
from app.core.providers.symbol_mapper import symbol_mapper
from app.core.providers.provider_registry import provider_registry
from app.core.providers.provider_manager import ProviderManager
from app.core.providers.twelve_data_provider import TwelveDataProvider
from app.core.providers.fmp_provider import FmpProvider
from app.core.providers.alpha_vantage_provider import AlphaVantageProvider
from app.core.providers.mock_price_provider import FalconMockPriceProvider
from app.core.providers.provider_analytics import provider_analytics

# ── Instantiate providers ──────────────────────────────────────────────────────
_twelve_data_provider = TwelveDataProvider()
_alpha_vantage_provider = AlphaVantageProvider()
_fmp_provider = FmpProvider()

# ── Register providers in priority order ──────────────────────────────────────
provider_registry.register(_twelve_data_provider, priority=1)
provider_registry.register(_alpha_vantage_provider, priority=2)
provider_registry.register(_fmp_provider, priority=3)

# The synthetic price provider is opt-in: with ENABLE_MOCK_PROVIDER unset the
# pipeline reports missing data instead of serving fabricated quotes.
if settings.ENABLE_MOCK_PROVIDER:
    _mock_provider = FalconMockPriceProvider()
    provider_registry.register(_mock_provider, priority=4)

# ── Wire analytics — register all providers ───────────────────────────────────
for _p in provider_registry.all_providers():
    provider_analytics.register_provider(_p.provider_id, _p.provider_name)

# ── Intercept TwelveData circuit breaker events → analytics timeline ──────────
_orig_td_print_event = _twelve_data_provider._print_event

def _td_analytics_event_hook(event: str, detail: str) -> None:  # noqa: ANN001
    """Forward circuit breaker events from TwelveDataProvider to analytics."""
    _orig_td_print_event(event, detail)
    pid  = _twelve_data_provider.PROVIDER_ID
    pname = _twelve_data_provider.PROVIDER_NAME
    if event == "CircuitBreakerOpen":
        provider_analytics.record_circuit_open(pid, pname, detail)
        if "429" in detail:
            provider_analytics.record_rate_limited(pid, pname)
    elif event == "CircuitBreakerHalfOpen":
        provider_analytics.record_circuit_half_open(pid, pname)
    elif event == "CircuitBreakerClosed":
        provider_analytics.record_circuit_close(pid, pname)
    elif event == "CircuitBreakerReopened":
        provider_analytics.record_circuit_reopen(pid, pname, detail)

_twelve_data_provider._print_event = _td_analytics_event_hook  # type: ignore[method-assign]


# ── Instrumented ProviderManager subclass ─────────────────────────────────────
class _InstrumentedProviderManager(ProviderManager):
    """ProviderManager that records every fetch, cache hit/miss, and failover
    into the ProviderAnalyticsEngine without altering selection logic."""

    def get_market_quote(self, raw_symbol: str):  # type: ignore[override]
        # Peek at cache before delegating to determine hit/miss for analytics
        canonical = self._mapper.normalize(raw_symbol)
        cache_hit = canonical is not None and self._cache.get(canonical) is not None
        resp = super().get_market_quote(raw_symbol)
        if canonical:
            if cache_hit:
                # Attribute the cache hit to the provider that stored the entry
                entry = self._cache.get(canonical)
                if entry:
                    provider_analytics.record_cache_hit(
                        entry.provider_id,
                        entry.provider_name,
                        canonical,
                    )
                else:
                    provider_analytics.record_cache_hit("cache", "Cache", canonical)
            else:
                # For a cold fetch, record the provider that actually served data
                if resp is not None:
                    q = resp.quote
                    provider_analytics.record_fetch(
                        q.providerId, q.providerName, canonical,
                        success=True, latency_ms=self._last_cold_ms,
                    )
                else:
                    provider_analytics.record_cache_miss("all", "All Providers", canonical)
        return resp

    def _fetch_from_providers(self, canonical: str):  # type: ignore[override]
        self._last_cold_ms: float = 0.0
        import time as _time
        t0 = _time.time()
        result = super()._fetch_from_providers(canonical)
        self._last_cold_ms = (_time.time() - t0) * 1000
        return result

    def _emit_failover_event(
        self, from_provider: str, to_provider: str, reason: str
    ) -> None:
        super()._emit_failover_event(from_provider, to_provider, reason)
        # Map names to IDs best-effort (registry may have both)
        from_id = from_provider.lower().replace(" ", "_")
        to_id   = to_provider.lower().replace(" ", "_")
        provider_analytics.record_failover(
            from_provider_id=from_id,
            from_provider_name=from_provider,
            to_provider_id=to_id,
            to_provider_name=to_provider,
            symbol="",
        )


# ── Singleton manager consumed by all intelligence engines ────────────────────
provider_manager = _InstrumentedProviderManager(
    registry=provider_registry,
    cache=market_cache,
    symbol_mapper=symbol_mapper,
)
