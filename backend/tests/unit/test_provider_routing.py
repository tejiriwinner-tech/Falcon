"""
Falcon Enterprise — Phase 8.3 Tests
Instrument-Aware Provider Routing & Data Integrity

Verifies:
- Instrument-aware provider selection (provider capability matrix).
- XAU/USD routes TwelveData -> AlphaVantage -> Mock; FMP is NEVER contacted.
- GBP/USD and EUR/USD route TwelveData -> FMP -> AlphaVantage -> Mock.
- Invalid / stale / malformed quotes cannot reach signal generation.
- Gold-futures (GCUSD) substitution is impossible.
- Routing decisions remain observable via non-secret routing events.

These tests use in-memory stub providers — no network calls are made.
"""
from datetime import datetime, timedelta, timezone

from app.core.providers.cache import MarketDataCache
from app.core.providers.base_provider import BaseProvider
from app.core.providers.provider_manager import (
    ProviderManager,
    _INSTRUMENT_PROVIDER_ROUTE,
    _EVT_PROVIDER_SKIPPED_UNSUPPORTED,
)
from app.core.providers.provider_registry import ProviderRegistry
from app.core.providers.quote_validator import quote_validator
from app.core.providers.symbol_mapper import SymbolMapper
from app.schemas.provider_models import (
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderStatus,
    ProviderType,
    ProviderStatistics,
)

_FAST_PRICES = {
    "XAUUSD": 2345.67,
    "GBPUSD": 1.26740,
    "EURUSD": 1.08460,
}


def valid_quote(symbol: str = "XAUUSD", ts=None) -> dict:
    """Return a normalized, validator-passing quote payload (Phase 8.3 tests)."""
    price = _FAST_PRICES.get(symbol, 100.0)
    spread = 0.01 if symbol == "XAUUSD" else 0.0001
    if isinstance(ts, datetime):
        ts_str = ts.isoformat()
    else:
        ts_str = ts or datetime.now(timezone.utc).isoformat()
    return {
        "symbol": symbol,
        "providerTicker": symbol,
        "bid": round(price, 5),
        "ask": round(price + spread, 5),
        "spread": round(spread, 5),
        "mid": round(price, 5),
        "lastPrice": round(price, 5),
        "change": 0.0,
        "changePercent": 0.0,
        "timestamp": ts_str,
        "providerId": "stub",
        "providerName": "stub",
        "fresh": True,
        "session": "Global",
    }


class StubProvider(BaseProvider):
    """Deterministic in-memory provider used to verify routing order.

    `sequence` is a queue of quote payloads (or empty to fail); `fetch_calls`
    records every symbol Falcon asks this provider to fetch, which lets tests
    prove e.g. that FMP.fetch() is never invoked for XAU/USD.
    """

    def __init__(self, provider_id, provider_name, priority, sequence=None):
        super().__init__(
            provider_id=provider_id,
            provider_name=provider_name,
            provider_type="LIVE",
            priority=priority,
        )
        self.capabilities = [ProviderCapability.LIVE_PRICE.value]
        self.health = ProviderHealth.HEALTHY
        self.status = ProviderStatus.ONLINE
        self._sequence = list(sequence or [])
        self.fetch_calls = []
        self._connected = True

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def health_check(self):
        return self.health

    def fetch(self, symbol: str, **kwargs):
        self.fetch_calls.append(symbol)
        if self._sequence:
            return self._sequence.pop(0)
        return None

    def supports(self, capability) -> bool:
        return capability == ProviderCapability.LIVE_PRICE

    def get_metadata(self):
        return ProviderMetadata(
            providerId=self.provider_id,
            providerName=self.provider_name,
            providerVersion="1.0.0",
            providerType=ProviderType.PRICE,
            capabilities=[ProviderCapability.LIVE_PRICE],
            status=self.status,
            health=self.health,
        )

    def get_statistics(self):
        return ProviderStatistics(
            totalRequests=0,
            successfulRequests=0,
            failedRequests=0,
            successRate=100.0,
        )


def build_manager(*providers) -> ProviderManager:
    """Build an isolated ProviderManager registered with the given stubs."""
    registry = ProviderRegistry()
    for provider in providers:
        registry.register(provider, priority=provider.priority)
    return ProviderManager(registry, MarketDataCache(), SymbolMapper())


def td_ok():
    return StubProvider("twelve_data", "TwelveData", 1, sequence=[valid_quote()])


def fmp_ok(symbol="GBPUSD"):
    return StubProvider("fmp", "FMP", 2, sequence=[valid_quote(symbol)])


def av_ok(symbol="XAUUSD"):
    return StubProvider("alpha_vantage", "Alpha Vantage", 3, sequence=[valid_quote(symbol)])


def mock_ok(symbol="XAUUSD"):
    return StubProvider("mock_provider", "Mock", 4, sequence=[valid_quote(symbol)])


def failing(*provider_ids):
    """Return failing stub providers for the given ids (empty sequences)."""
    return [
        StubProvider(pid, pid.replace("_", " ").title(), idx)
        for idx, pid in enumerate(provider_ids, start=1)
    ]


# ────────────────────────────────────────────────────────────────────────
# XAU/USD routing
# ────────────────────────────────────────────────────────────────────────

class TestXauUsdRouting:
    def test_xau_twelve_data_succeeds_fmp_and_av_not_called(self):
        td, fmp, av = td_ok(), fmp_ok(), av_ok("XAUUSD")
        manager = build_manager(td, fmp, av)

        resp = manager._fetch_from_providers("XAUUSD")

        assert resp is not None
        assert resp.quote.providerId == "twelve_data"
        assert td.fetch_calls == ["XAUUSD"]
        assert fmp.fetch_calls == []
        assert av.fetch_calls == []

    def test_xau_twelve_data_fails_av_called_fmp_skipped(self):
        td, fmp, av = failing("twelve_data")[0], fmp_ok("XAUUSD"), av_ok("XAUUSD")
        manager = build_manager(td, fmp, av)

        resp = manager._fetch_from_providers("XAUUSD")

        assert resp is not None
        assert resp.quote.providerId == "alpha_vantage"
        assert td.fetch_calls == ["XAUUSD"]
        assert fmp.fetch_calls == []          # FMP never contacted for XAU
        assert av.fetch_calls == ["XAUUSD"]

    def test_xau_td_and_av_fail_final_fallback_mock_used(self):
        td, av = failing("twelve_data", "alpha_vantage")
        mock = mock_ok("XAUUSD")
        fmp = fmp_ok("XAUUSD")
        manager = build_manager(td, fmp, av, mock)

        resp = manager._fetch_from_providers("XAUUSD")

        assert resp is not None
        assert resp.quote.providerId == "mock_provider"
        assert fmp.fetch_calls == []          # FMP never contacted for XAU
        assert mock.fetch_calls == ["XAUUSD"]

    def test_xau_all_route_providers_fail_returns_none_no_signal(self):
        td, av = failing("twelve_data", "alpha_vantage")
        fmp = fmp_ok("XAUUSD")
        manager = build_manager(td, fmp, av)  # no mock registered

        resp = manager._fetch_from_providers("XAUUSD")

        assert resp is None                    # NO SIGNAL when no valid provider

    def test_xau_fmp_fetch_never_invoked_explicit_spy(self):
        """Hard safety requirement: FMP.fetch() must never be invoked for XAU/USD."""
        scenes = [
            lambda: (td_ok(), fmp_ok("XAUUSD"), av_ok("XAUUSD")),
            lambda: (*failing("twelve_data"), fmp_ok("XAUUSD"), av_ok("XAUUSD")),
            lambda: (*failing("twelve_data", "alpha_vantage"), fmp_ok("XAUUSD"), mock_ok("XAUUSD")),
        ]
        for scene in scenes:
            providers = scene()
            fmp = next(p for p in providers if p.provider_id == "fmp")
            manager = build_manager(*providers)
            manager._fetch_from_providers("XAUUSD")
            assert fmp.fetch_calls == [], "FMP.fetch() was invoked for XAU/USD!"

    def test_xau_fmp_not_in_candidate_route(self):
        td, fmp, av, mock = td_ok(), fmp_ok("XAUUSD"), av_ok("XAUUSD"), mock_ok("XAUUSD")
        manager = build_manager(td, fmp, av, mock)

        candidates = [p.provider_id for p in manager._get_candidate_providers("XAUUSD")]

        assert candidates == ["twelve_data", "alpha_vantage", "mock_provider"]
        assert "fmp" not in candidates


# ────────────────────────────────────────────────────────────────────────
# GBP/USD routing
# ────────────────────────────────────────────────────────────────────────

class TestGbpUsdRouting:
    def test_gbp_twelve_data_succeeds(self):
        td = StubProvider("twelve_data", "TwelveData", 1, sequence=[valid_quote("GBPUSD")])
        fmp, av = fmp_ok("GBPUSD"), av_ok("GBPUSD")
        manager = build_manager(td, fmp, av)

        resp = manager._fetch_from_providers("GBPUSD")

        assert resp.quote.providerId == "twelve_data"
        assert fmp.fetch_calls == []
        assert av.fetch_calls == []

    def test_gbp_twelve_data_fails_fmp_used(self):
        td, fmp, av = failing("twelve_data")[0], fmp_ok("GBPUSD"), av_ok("GBPUSD")
        manager = build_manager(td, fmp, av)

        resp = manager._fetch_from_providers("GBPUSD")

        assert resp.quote.providerId == "fmp"
        assert td.fetch_calls == ["GBPUSD"]
        assert fmp.fetch_calls == ["GBPUSD"]
        assert av.fetch_calls == []

    def test_gbp_td_and_fmp_fail_av_used(self):
        td, fmp, av = (*failing("twelve_data", "fmp"), av_ok("GBPUSD"))
        manager = build_manager(td, fmp, av)

        resp = manager._fetch_from_providers("GBPUSD")

        assert resp.quote.providerId == "alpha_vantage"
        assert td.fetch_calls == ["GBPUSD"]
        assert fmp.fetch_calls == ["GBPUSD"]

    def test_gbp_all_live_fail_final_fallback(self):
        td, fmp, av = failing("twelve_data", "fmp", "alpha_vantage")
        mock = mock_ok("GBPUSD")
        manager = build_manager(td, fmp, av, mock)

        resp = manager._fetch_from_providers("GBPUSD")

        assert resp.quote.providerId == "mock_provider"

    def test_gbp_all_providers_fail_returns_none(self):
        td, fmp, av = failing("twelve_data", "fmp", "alpha_vantage")
        manager = build_manager(td, fmp, av)

        assert manager._fetch_from_providers("GBPUSD") is None


# ────────────────────────────────────────────────────────────────────────
# EUR/USD routing
# ────────────────────────────────────────────────────────────────────────

class TestEurUsdRouting:
    def test_eur_twelve_data_succeeds(self):
        td = StubProvider("twelve_data", "TwelveData", 1, sequence=[valid_quote("EURUSD")])
        fmp, av = fmp_ok("EURUSD"), av_ok("EURUSD")
        manager = build_manager(td, fmp, av)

        resp = manager._fetch_from_providers("EURUSD")

        assert resp.quote.providerId == "twelve_data"

    def test_eur_twelve_data_fails_fmp_used(self):
        td, fmp, av = failing("twelve_data")[0], fmp_ok("EURUSD"), av_ok("EURUSD")
        manager = build_manager(td, fmp, av)

        resp = manager._fetch_from_providers("EURUSD")

        assert resp.quote.providerId == "fmp"
        assert fmp.fetch_calls == ["EURUSD"]
        assert av.fetch_calls == []

    def test_eur_td_and_fmp_fail_av_used(self):
        td, fmp, av = (*failing("twelve_data", "fmp"), av_ok("EURUSD"))
        manager = build_manager(td, fmp, av)

        resp = manager._fetch_from_providers("EURUSD")

        assert resp.quote.providerId == "alpha_vantage"
        assert fmp.fetch_calls == ["EURUSD"]

    def test_eur_all_live_fail_final_fallback(self):
        td, fmp, av = failing("twelve_data", "fmp", "alpha_vantage")
        mock = mock_ok("EURUSD")
        manager = build_manager(td, fmp, av, mock)

        resp = manager._fetch_from_providers("EURUSD")

        assert resp.quote.providerId == "mock_provider"

    def test_eur_all_providers_fail_returns_none(self):
        td, fmp, av = failing("twelve_data", "fmp", "alpha_vantage")
        manager = build_manager(td, fmp, av)

        assert manager._fetch_from_providers("EURUSD") is None


# ────────────────────────────────────────────────────────────────────────
# Data safety
# ────────────────────────────────────────────────────────────────────────

class TestDataSafety:
    def _quote_with(self, **overrides):
        q = valid_quote("XAUUSD")
        q.update(overrides)
        return q

    def test_zero_price_rejected(self):
        ok, reason = quote_validator.validate(
            self._quote_with(bid=0.0, mid=0.0, lastPrice=0.0), "XAUUSD"
        )
        assert ok is False
        assert "greater than zero" in reason

    def test_negative_price_rejected(self):
        ok, reason = quote_validator.validate(
            self._quote_with(bid=-10.0, ask=-9.0, mid=-9.5), "XAUUSD"
        )
        assert ok is False
        assert "greater than zero" in reason

    def test_malformed_timestamp_rejected(self):
        ok, reason = quote_validator.validate(
            self._quote_with(timestamp="not-a-date"), "XAUUSD"
        )
        assert ok is False
        assert "Unparseable" in reason

    def test_objectively_stale_quote_rejected(self):
        stale_ts = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        ok, reason = quote_validator.validate(
            self._quote_with(timestamp=stale_ts), "XAUUSD", max_age_seconds=30
        )
        assert ok is False
        assert "stale" in reason

    def test_fresh_quote_passes_max_age_check(self):
        ok, reason = quote_validator.validate(valid_quote("XAUUSD"), "XAUUSD", max_age_seconds=30)
        assert ok is True
        assert reason is None

    def test_missing_timestamp_handled_safely(self):
        q = self._quote_with()
        q.pop("timestamp", None)
        ok, reason = quote_validator.validate(q, "XAUUSD")
        assert ok is False
        assert reason == "Missing timestamp"

    def test_missing_timestamp_provider_falls_back(self):
        """A provider response with no timestamp is invalid -> next provider used."""
        no_ts = dict(valid_quote("GBPUSD"))
        no_ts.pop("timestamp", None)
        td = StubProvider("twelve_data", "TwelveData", 1, sequence=[no_ts])
        fmp, av = fmp_ok("GBPUSD"), av_ok("GBPUSD")
        manager = build_manager(td, fmp, av)

        resp = manager._fetch_from_providers("GBPUSD")

        assert resp.quote.providerId == "fmp"
        assert td.fetch_calls == ["GBPUSD"]
        assert fmp.fetch_calls == ["GBPUSD"]

    def test_invalid_price_prevents_first_provider_use(self):
        """Zero price from TwelveData must not be used; fallback proceeds."""
        bad = self._quote_with(lastPrice=0.0, mid=0.0, bid=0.0, ask=0.0, spread=0.0)
        td = StubProvider("twelve_data", "TwelveData", 1, sequence=[bad])
        fmp, av = fmp_ok("EURUSD"), av_ok("EURUSD")
        manager = build_manager(td, fmp, av)

        resp = manager._fetch_from_providers("EURUSD")

        assert resp.quote.providerId == "fmp"

    def test_stale_server_timestamp_recorded_in_freshness(self):
        """Actual quote age is computed from the server timestamp (not 0.0)."""
        old_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        td = StubProvider("twelve_data", "TwelveData", 1,
                          sequence=[valid_quote("XAUUSD", ts=old_ts)])
        av = av_ok("XAUUSD")
        manager = build_manager(td, av)

        resp = manager._fetch_from_providers("XAUUSD")

        assert resp.quote.providerId == "twelve_data"
        assert resp.quote.freshnessSeconds > 590  # ~10 minutes of real age


# ────────────────────────────────────────────────────────────────────────
# Gold futures substitution protection / unsupported combinations
# ────────────────────────────────────────────────────────────────────────

class TestInstrumentIntegrity:
    def test_gc_usd_cannot_be_used_as_xau_usd(self):
        sm = SymbolMapper()
        # GCUSD / gold futures are not Falcon canonical symbols and have no
        # provider mapping — substitution is impossible by construction.
        assert sm.normalize("GCUSD") is None
        assert sm.normalize("GC=F") is None

        manager = build_manager(td_ok(), fmp_ok(), av_ok("XAUUSD"))
        assert manager.get_market_quote("GCUSD") is None

    def test_no_gold_futures_in_route_for_xau(self):
        assert "GCUSD" not in _INSTRUMENT_PROVIDER_ROUTE["XAUUSD"]

    def test_unsupported_provider_instrument_combination_skipped(self):
        """FMP registered but unsupported for XAU/USD must never be contacted."""
        td, av = failing("twelve_data", "alpha_vantage")
        fmp = fmp_ok("XAUUSD")
        mock = mock_ok("XAUUSD")
        manager = build_manager(td, fmp, av, mock)

        candidates = [p.provider_id for p in manager._get_candidate_providers("XAUUSD")]

        assert "twelve_data" in candidates
        assert "alpha_vantage" in candidates
        assert "mock_provider" in candidates
        assert "fmp" not in candidates

        resp = manager._fetch_from_providers("XAUUSD")
        assert resp.quote.providerId == "mock_provider"
        assert fmp.fetch_calls == []

    def test_unregistered_symbol_returns_none(self):
        manager = build_manager(td_ok(), fmp_ok(), av_ok())
        assert manager.get_market_quote("NOTASYM") is None


# ────────────────────────────────────────────────────────────────────────
# Observability
# ────────────────────────────────────────────────────────────────────────

class TestRoutingObservability:
    def test_provider_skipped_unsupported_event_emitted_for_xau_fmp(self, caplog):
        import logging
        caplog.set_level(logging.INFO, logger="app.core.providers.provider_manager")
        td, fmp, av = td_ok(), fmp_ok("XAUUSD"), av_ok("XAUUSD")
        manager = build_manager(td, fmp, av)
        manager._fetch_from_providers("XAUUSD")

        assert any(
            _EVT_PROVIDER_SKIPPED_UNSUPPORTED in r.message and '"providerId": "fmp"' in r.message
            for r in caplog.records
        )

    def test_public_api_never_routes_xau_to_fmp(self):
        td, fmp, av = failing("twelve_data")[0], fmp_ok("XAUUSD"), av_ok("XAUUSD")
        manager = build_manager(td, fmp, av)

        resp = manager.get_market_quote("XAUUSD")

        assert resp is not None
        assert resp.quote.providerId == "alpha_vantage"
        assert fmp.fetch_calls == []          # FMP never contacted for XAU/USD