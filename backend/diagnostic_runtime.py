"""Phase 8.3.2 Runtime Diagnostic — Read-only investigation."""
import sys
sys.path.insert(0, ".")

from app.core.providers import provider_manager, provider_registry, market_cache
from app.core.config import settings
from app.core.providers.provider_manager import _INSTRUMENT_PROVIDER_ROUTE

print("=== PROVIDER REGISTRATION ===")
providers = provider_registry.all_providers()
for p in providers:
    print(f"  {p.provider_id}: priority={p.priority}, health={p.health_check().value}, status={p.get_metadata().status.value}")

print()
print("=== SETTINGS ===")
print(f"  TWELVEDATA_API_KEY configured: {settings.TWELVEDATA_API_KEY is not None}")
print(f"  FMP_API_KEY configured: {settings.FMP_API_KEY is not None}")
print(f"  FMP_BASE_URL: {settings.FMP_BASE_URL}")
print(f"  ALPHA_VANTAGE_API_KEY configured: {settings.ALPHA_VANTAGE_API_KEY is not None}")

print()
print("=== ROUTE MATRIX ===")
for sym, route in _INSTRUMENT_PROVIDER_ROUTE.items():
    print(f"  {sym}: {route}")

print()
print("=== CACHE STATS ===")
print(f"  {market_cache.stats}")

print()
print("=== CACHE ENTRIES ===")
for sym in ["XAUUSD", "GBPUSD", "EURUSD"]:
    entry = market_cache.get(sym)
    if entry:
        print(f"  {sym}: provider={entry.provider_id}, age={entry.age_seconds}s, ttl={entry.ttl_seconds}s, fresh={entry.is_fresh}")
    else:
        print(f"  {sym}: NO CACHE ENTRY")

print()
print("=== CANDIDATE PROVIDERS ===")
for sym in ["XAUUSD", "GBPUSD", "EURUSD"]:
    candidates = provider_manager._get_candidate_providers(sym)
    print(f"  {sym}: {[c.provider_id for c in candidates]}")

print()
print("=== LIVE FETCH TRACE ===")
for sym in ["XAUUSD", "GBPUSD", "EURUSD"]:
    print(f"\n--- {sym} ---")
    # Clear cache to force fresh fetch
    market_cache.invalidate(sym)
    result = provider_manager.get_market_quote(sym)
    if result:
        print(f"  Result: provider={result.quote.providerId}, name={result.quote.providerName}")
        print(f"  Price: bid={result.quote.bidAsk.bid}, ask={result.quote.bidAsk.ask}")
    else:
        print(f"  Result: None (all providers failed)")

print()
print("=== FINAL CACHE STATE ===")
for sym in ["XAUUSD", "GBPUSD", "EURUSD"]:
    entry = market_cache.get(sym)
    if entry:
        print(f"  {sym}: provider={entry.provider_id}, age={entry.age_seconds}s")
