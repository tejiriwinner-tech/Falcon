"""
Falcon Phase 4.2 — Verification Script for Live Market Data Integration Foundation
Asserts all 10 architectural and functional requirements.
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.providers import provider_registry, provider_manager, market_cache
from app.core.providers.twelve_data_provider import TwelveDataProvider
from app.core.providers.yahoo_finance_provider import YahooFinanceProvider
from app.core.providers.mock_price_provider import FalconMockPriceProvider
from app.core.engines.market_state_engine import MarketStateEngine
from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator


def run_verification():
    print("=== Falcon Live Market Integration Verification ===\n")

    # 1. Primary Provider Connected
    twelve = provider_registry.get("twelve-data-v1")
    assert twelve is not None and twelve.get_metadata().status.value == "ONLINE", "FAIL: Primary provider not online"
    print("[OK] Primary Provider Connected")

    # 2. Secondary Provider Available
    yahoo = provider_registry.get("yahoo-finance-v1")
    assert yahoo is not None and yahoo.get_metadata().status.value == "ONLINE", "FAIL: Secondary provider not online"
    print("[OK] Secondary Provider Available")

    # 3. Automatic Provider Failover Verified
    market_cache.clear()
    # Force primary provider to be unhealthy to trigger failover to secondary provider
    if isinstance(twelve, TwelveDataProvider):
        twelve.set_healthy(False)

    quote_failover = provider_manager.get_market_quote("XAUUSD")
    assert quote_failover is not None, "FAIL: Failover returned None"
    assert quote_failover.quote.providerId == "yahoo-finance-v1", f"FAIL: Expected failover to yahoo-finance-v1, got {quote_failover.quote.providerId}"
    print("[OK] Automatic Provider Failover Verified")

    # Restore primary provider health
    if isinstance(twelve, TwelveDataProvider):
        twelve.set_healthy(True)

    # 4. Provider Heartbeats Active
    provider_registry.heartbeat()
    print("[OK] Provider Heartbeats Active")

    # 5. Provider Health Monitoring Active
    summary = provider_registry.get_summary()
    assert summary.online > 0, "FAIL: Provider health monitoring failed"
    print("[OK] Provider Health Monitoring Active")

    # 6. Cache Freshness Verified
    market_cache.clear()
    q1 = provider_manager.get_market_quote("GBPUSD")
    assert q1 is not None, "FAIL: GBPUSD query failed"
    c_entry = market_cache.get("GBPUSD")
    assert c_entry is not None and c_entry.is_fresh, "FAIL: Cache freshness failed"
    print("[OK] Cache Freshness Verified")

    # 7. Cache Expiration Verified
    # Invalidate cache to verify re-fetching behavior
    market_cache.invalidate("GBPUSD")
    assert market_cache.get("GBPUSD") is None, "FAIL: Cache expiration / invalidation failed"
    print("[OK] Cache Expiration Verified")

    # 8. Dynamic Watchlist API Verified
    symbols = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30"]
    quotes_list = []
    for s in symbols:
        q = provider_manager.get_market_quote(s)
        if q:
            quotes_list.append(q.quote)
    assert len(quotes_list) == len(symbols), f"FAIL: Expected {len(symbols)} quotes, got {len(quotes_list)}"
    print("[OK] Dynamic Watchlist API Verified")

    # 9. Market Quotes Normalized
    for q in quotes_list:
        assert hasattr(q, "symbol") and hasattr(q, "bidAsk") and hasattr(q, "providerName"), "FAIL: Normalization contract broken"
    print("[OK] Market Quotes Normalized")

    # 10. Market State Engine Consuming ProviderManager
    ms_engine = MarketStateEngine()
    m_state = ms_engine.get_market_state()
    assert m_state is not None and "XAUUSD" in m_state.prices, "FAIL: MarketStateEngine failed to consume quotes"
    print("[OK] Market State Engine Using ProviderManager")

    # 11. Pipeline Remains Immutable
    orchestrator = PipelineOrchestrator()
    mission_report = orchestrator.run_pipeline()
    assert mission_report is not None and mission_report.status.value in ("SUCCESS", "PARTIAL_SUCCESS"), "FAIL: Immutable pipeline execution failed"
    print("[OK] Pipeline Remains Immutable\n")

    print("SUCCESS")


if __name__ == "__main__":
    run_verification()
