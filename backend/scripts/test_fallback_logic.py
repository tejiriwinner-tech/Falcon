#!/usr/bin/env python3
"""
Test fallback logic with Alpha Vantage provider (Phase 8.1)
Verifies that the provider priority chain works correctly.
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.providers.provider_registry import provider_registry
from app.core.providers import provider_manager

def test_fallback_logic():
    print("=" * 80)
    print("Testing Provider Fallback Logic (Phase 8.1)")
    print("=" * 80)
    
    # Display current provider registry
    print("\nCurrent Provider Registry:")
    print("-" * 80)
    providers = provider_registry.all_providers()
    for provider in providers:
        print(f"  {provider.provider_name} (ID: {provider.provider_id}, Priority: {provider.priority})")
    
    print("\nExpected Priority Order:")
    print("  1. TwelveData (primary)")
    print("  2. Alpha Vantage (secondary/fallback)")
    print("  3. Alpaca (if enabled)")
    print("  4. Mock Price (final fallback)")
    
    # Test symbol fetch
    print("\n" + "=" * 80)
    print("Testing Symbol Fetch")
    print("=" * 80)
    
    test_symbols = ["XAUUSD", "GBPUSD"]
    
    for symbol in test_symbols:
        print(f"\nFetching {symbol}...")
        try:
            result = provider_manager.get_market_quote(symbol)
            if result:
                print(f"  SUCCESS: {result.quote.providerName} - Price: {result.quote.lastPrice}")
            else:
                print(f"  FAILED: No provider returned data")
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print("\n" + "=" * 80)
    print("Fallback Logic Test Complete")
    print("=" * 80)

if __name__ == "__main__":
    test_fallback_logic()
