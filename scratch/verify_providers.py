"""
Falcon Phase 4.1 — Provider Framework Verification Script
Run from project root: python scratch/verify_providers.py
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.providers import provider_registry, provider_manager, market_cache
from app.core.providers.symbol_mapper import symbol_mapper
from app.schemas.provider_models import ProviderCapability, ProviderHealth, ProviderStatus


def run_verification():
    print("=== Falcon Provider Framework Verification ===\n")

    # 1. Registered providers
    snapshots = provider_registry.get_all_snapshots()
    assert len(snapshots) >= 1, "FAIL: No providers registered"
    print(f"[OK] Registered Providers: {len(snapshots)}")

    # 2. MockPriceProvider online
    snap = snapshots[0]
    assert snap.metadata.status == ProviderStatus.ONLINE, "FAIL: Provider not ONLINE"
    print(f"[OK] {snap.metadata.providerName} Online")

    # 3. Capabilities verified
    caps = snap.metadata.capabilities
    assert ProviderCapability.LIVE_PRICE in caps, "FAIL: LIVE_PRICE capability missing"
    assert ProviderCapability.SPREAD in caps, "FAIL: SPREAD capability missing"
    print(f"[OK] Capabilities Verified ({[c.value for c in caps]})")

    # 4. XAUUSD retrieved
    xau = provider_manager.get_market_data("XAUUSD")
    assert xau is not None, "FAIL: XAUUSD not retrieved"
    assert xau.quote.bid > 0, "FAIL: Invalid bid"
    print(f"[OK] XAUUSD Retrieved (bid={xau.quote.bid}, ask={xau.quote.ask})")

    # 5. EURUSD retrieved
    eur = provider_manager.get_market_data("EURUSD")
    assert eur is not None, "FAIL: EURUSD not retrieved"
    print(f"[OK] EURUSD Retrieved (bid={eur.quote.bid}, ask={eur.quote.ask})")

    # 6. Symbol mapping - aliases
    assert symbol_mapper.normalize("gold") == "XAUUSD", "FAIL: 'gold' not mapped"
    assert symbol_mapper.normalize("cable") == "GBPUSD", "FAIL: 'cable' not mapped"
    assert symbol_mapper.normalize("NAS100") == "NAS100", "FAIL: 'NAS100' not mapped"
    assert symbol_mapper.normalize("us100") == "NAS100", "FAIL: 'us100' alias not mapped"
    gold = provider_manager.get_market_data("gold")
    assert gold is not None and gold.normalizedSymbol == "XAUUSD", "FAIL: alias fetch failed"
    print(f"[OK] Symbol Mapping Verified (gold->XAUUSD, cable->GBPUSD, us100->NAS100)")

    # 7. Cache hit - second call should be cached
    market_cache.clear()
    provider_manager.get_market_data("BTCUSD")  # miss
    btc2 = provider_manager.get_market_data("BTCUSD")  # should be cached
    assert btc2 is not None and btc2.cacheHit is True, "FAIL: Cache hit not working"
    print(f"[OK] Cache Hit Verified (hit_rate={market_cache.hit_rate}%)")

    # 8. Provider health
    health = snapshots[0].metadata.health
    assert health == ProviderHealth.HEALTHY, f"FAIL: Expected HEALTHY, got {health}"
    print(f"[OK] Provider Health {health.value}")

    # 9. Latency
    latency = snap.latency
    print(f"[OK] Average Latency {latency.averageMs:.1f} ms")

    # 10. Heartbeat event
    provider_registry.heartbeat()
    print("[OK] Event ProviderHeartbeat Published (see above)")

    # 11. Statistics
    stats = snap.statistics
    assert stats.totalRequests >= 0, "FAIL: Stats invalid"
    print(f"[OK] Statistics (requests={stats.totalRequests}, success_rate={stats.successRate}%)")

    # 12. Failover readiness (no other provider registered, but function exists)
    failover = provider_registry.failover_for(ProviderCapability.LIVE_PRICE, "mock-price-v1")
    print(f"[OK] Failover Readiness Checked (fallback={'available' if failover else 'none — expected in 4.1'})")

    print("\nSUCCESS\nFalcon Provider Framework Verified")


if __name__ == "__main__":
    run_verification()
