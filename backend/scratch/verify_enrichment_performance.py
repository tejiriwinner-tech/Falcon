"""
Falcon Task 7.9 — Quote Enrichment Performance Verification
==========================================================

Verifies that quote enrichment overhead meets the < 1ms performance requirement.
This script directly measures the _enrich_quote_with_instrument_metadata() method
performance to validate Requirement 20.

Performance targets:
- Single quote enrichment: < 1ms
- Batch average: < 1ms per quote
- Registry lookup: < 0.1ms per lookup
- Validation: < 0.1ms per validation

Run from backend/ directory:
    python scratch/verify_enrichment_performance.py

This script can run without the full server running (unit-level testing).
"""

import sys
import os
import time
import statistics
from datetime import datetime, timezone
from typing import List

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.providers.provider_manager import ProviderManager
from app.core.providers.provider_registry import ProviderRegistry
from app.core.providers.cache import MarketDataCache
from app.core.providers.symbol_mapper import SymbolMapper
from app.schemas.market_quote import MarketQuote, BidAsk, QuoteStatus, MarketStatus
from app.schemas.enriched_quote import EnrichedMarketQuote
from app.core.instruments import instrument_registry, instrument_validator

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"

CHECKS_PASSED = 0
CHECKS_FAILED = 0


def ok(msg: str, detail: str = ""):
    global CHECKS_PASSED
    CHECKS_PASSED += 1
    suffix = f"\n        {detail}" if detail else ""
    print(f"  {PASS} {msg}{suffix}")


def fail(msg: str, detail: str = ""):
    global CHECKS_FAILED
    CHECKS_FAILED += 1
    suffix = f"\n        {detail}" if detail else ""
    print(f"  {FAIL} {msg}{suffix}")


def section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def create_test_quote(symbol: str, provider_id: str = "twelve_data") -> MarketQuote:
    """Create a test MarketQuote for performance testing."""
    return MarketQuote(
        symbol=symbol,
        bidAsk=BidAsk(bid=1.2345, ask=1.2347, spread=0.0002),
        lastPrice=1.2346,
        change=0.0005,
        changePercent=0.04,
        timestamp=datetime.now(timezone.utc),
        providerId=provider_id,
        providerName="TwelveData",
        quoteStatus=QuoteStatus.LIVE,
        marketStatus=MarketStatus.OPEN,
        freshnessSeconds=0.0
    )


def main():
    print("=" * 68)
    print("  Falcon Task 7.9 — Quote Enrichment Performance Verification")
    print("=" * 68)
    
    # Initialize components
    print(f"\n  {INFO} Initializing provider manager and instruments...")
    
    # Ensure registry is populated
    from app.core.instruments.instrument_registry import _populate_registry
    _populate_registry()
    
    # Create provider manager for testing
    registry = ProviderRegistry()
    cache = MarketDataCache()
    symbol_mapper = SymbolMapper()
    provider_manager = ProviderManager(registry, cache, symbol_mapper)
    
    test_symbols = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30", "BTCUSD", "ETHUSD"]
    
    print(f"  {INFO} Testing {len(test_symbols)} symbols: {', '.join(test_symbols)}")

    # ── Section 1: Single Quote Enrichment ───────────────────────────────
    section("1 — Single Quote Enrichment Performance")
    
    quote = create_test_quote("XAUUSD")
    
    # Warm up (ensure any lazy loading is done)
    print("  Warming up enrichment pipeline...")
    _ = provider_manager._enrich_quote_with_instrument_metadata(quote)
    
    # Measure single enrichment
    start_time = time.perf_counter()
    enriched = provider_manager._enrich_quote_with_instrument_metadata(quote)
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    
    if isinstance(enriched, EnrichedMarketQuote) and enriched.canonicalSymbol == "XAUUSD":
        if elapsed_ms < 1.0:
            ok(f"Single quote enrichment: {elapsed_ms:.3f}ms < 1ms requirement")
        else:
            fail(f"Single quote enrichment: {elapsed_ms:.3f}ms > 1ms requirement")
    else:
        fail("Enrichment failed to produce valid EnrichedMarketQuote")
    
    print(f"    Enriched fields: {enriched.instrumentType}, {enriched.assetClass}, {enriched.exchange}")
    print(f"    Validation: {enriched.instrumentValidationStatus}")

    # ── Section 2: Batch Enrichment Performance ──────────────────────────
    section("2 — Batch Enrichment Performance")
    
    quotes = [create_test_quote(symbol) for symbol in test_symbols]
    timings = []
    
    print(f"  Testing enrichment for all {len(test_symbols)} tracked symbols...")
    
    # Warm up all symbols
    for quote in quotes:
        _ = provider_manager._enrich_quote_with_instrument_metadata(quote)
    
    # Measure each quote individually
    for i, quote in enumerate(quotes):
        start_time = time.perf_counter()
        enriched = provider_manager._enrich_quote_with_instrument_metadata(quote)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        timings.append(elapsed_ms)
        
        symbol = test_symbols[i]
        print(f"    {symbol:<8}: {elapsed_ms:.3f}ms - {enriched.instrumentType.value}")
    
    # Calculate statistics
    avg_time = statistics.mean(timings)
    max_time = max(timings)
    min_time = min(timings)
    
    if avg_time < 1.0:
        ok(f"Batch average: {avg_time:.3f}ms < 1ms requirement")
    else:
        fail(f"Batch average: {avg_time:.3f}ms > 1ms requirement")
    
    if max_time < 2.0:
        ok(f"Maximum time: {max_time:.3f}ms < 2ms (reasonable worst case)")
    else:
        fail(f"Maximum time: {max_time:.3f}ms > 2ms (too slow)")
    
    print(f"    Statistics: min={min_time:.3f}ms, avg={avg_time:.3f}ms, max={max_time:.3f}ms")

    # ── Section 3: Registry Performance ───────────────────────────────────
    section("3 — Registry Lookup Performance")
    
    print("  Testing registry lookup performance (10,000 operations per symbol)...")
    
    # Test canonical symbol lookup
    start_time = time.perf_counter()
    for _ in range(10000):
        for symbol in test_symbols:
            instrument = instrument_registry.get_instrument(symbol)
            assert instrument is not None
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    
    operations = 10000 * len(test_symbols)
    avg_per_op_us = (elapsed_ms * 1000) / operations
    
    if elapsed_ms < 100:  # Should be very fast
        ok(f"Registry lookup: {elapsed_ms:.1f}ms for {operations} ops ({avg_per_op_us:.2f}μs per lookup)")
    else:
        fail(f"Registry lookup too slow: {elapsed_ms:.1f}ms for {operations} operations")

    # ── Section 4: Validator Performance ──────────────────────────────────
    section("4 — Validation Performance")
    
    print("  Testing validator performance with various scenarios...")
    
    test_cases = [
        ("XAUUSD", "XAU/USD", "twelve_data"),     # Valid match
        ("XAUUSD", "GC=F", "yahoo_finance"),      # Known mismatch (SPOT vs FUTURES)
        ("GBPUSD", "GBP/USD", "twelve_data"),     # Valid forex
        ("UNKNOWN", "UNKNOWN", "unknown"),        # Unknown case
    ]
    
    start_time = time.perf_counter()
    mismatch_count = 0
    for _ in range(5000):
        for canonical, provider_symbol, provider_id in test_cases:
            is_valid, warning = instrument_validator.validate(
                canonical_symbol=canonical,
                received_provider_symbol=provider_symbol,
                provider_id=provider_id
            )
            if not is_valid:
                mismatch_count += 1
    
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    operations = 5000 * len(test_cases)
    avg_per_op_us = (elapsed_ms * 1000) / operations
    
    if elapsed_ms < 500:  # Allow more reasonable time for 20,000 validations
        ok(f"Validation: {elapsed_ms:.1f}ms for {operations} validations ({avg_per_op_us:.2f}μs per validation)")
    else:
        fail(f"Validation too slow: {elapsed_ms:.1f}ms for {operations} validations")
    
    print(f"    Detected {mismatch_count} mismatches in test data (expected)")

    # ── Section 5: Unknown Instrument Performance ─────────────────────────
    section("5 — Unknown Instrument Fallback Performance")
    
    print("  Testing enrichment performance with unknown instruments...")
    
    unknown_quote = create_test_quote("UNKNOWN_SYMBOL")
    
    # Warm up
    _ = provider_manager._enrich_quote_with_instrument_metadata(unknown_quote)
    
    start_time = time.perf_counter()
    enriched = provider_manager._enrich_quote_with_instrument_metadata(unknown_quote)
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    
    if enriched.instrumentType.value == "UNKNOWN":
        if elapsed_ms < 2.0:  # Allow extra time for fallback metadata creation
            ok(f"Unknown instrument enrichment: {elapsed_ms:.3f}ms < 2ms (includes fallback creation)")
        else:
            fail(f"Unknown instrument enrichment too slow: {elapsed_ms:.3f}ms > 2ms")
    else:
        fail("Unknown instrument fallback did not work correctly")
    
    print(f"    Fallback metadata: {enriched.canonicalSymbol}, {enriched.instrumentType}")

    # ── Section 6: End-to-End Enrichment Overhead ────────────────────────
    section("6 — End-to-End Enrichment Overhead Analysis")
    
    print("  Analyzing enrichment overhead vs baseline quote creation...")
    
    # Baseline: create EnrichedMarketQuote directly (no enrichment logic)
    start_time = time.perf_counter()
    for _ in range(1000):
        quote = create_test_quote("XAUUSD")
        # Direct creation without enrichment
        baseline = EnrichedMarketQuote(
            symbol=quote.symbol,
            bidAsk=quote.bidAsk,
            lastPrice=quote.lastPrice,
            change=quote.change,
            changePercent=quote.changePercent,
            timestamp=quote.timestamp,
            providerId=quote.providerId,
            providerName=quote.providerName,
            quoteStatus=quote.quoteStatus,
            marketStatus=quote.marketStatus,
            freshnessSeconds=quote.freshnessSeconds,
            canonicalSymbol="XAUUSD",
            providerSymbol="XAU/USD",
            instrumentType="SPOT",
            assetClass="PRECIOUS_METALS",
            exchange="FOREX_OTC",
            currency="USD",
            pipSize=0.001,
            instrumentValidationStatus="MATCHED",
            instrumentValidationWarning=None,
        )
    baseline_ms = (time.perf_counter() - start_time) * 1000
    
    # With enrichment
    start_time = time.perf_counter()
    for _ in range(1000):
        quote = create_test_quote("XAUUSD")
        enriched = provider_manager._enrich_quote_with_instrument_metadata(quote)
    enrichment_ms = (time.perf_counter() - start_time) * 1000
    
    overhead_ms = enrichment_ms - baseline_ms
    overhead_per_quote = overhead_ms / 1000
    
    print(f"    Baseline (1000 quotes): {baseline_ms:.1f}ms")
    print(f"    With enrichment (1000 quotes): {enrichment_ms:.1f}ms")
    print(f"    Total overhead: {overhead_ms:.1f}ms")
    print(f"    Overhead per quote: {overhead_per_quote:.3f}ms")
    
    if overhead_per_quote < 1.0:
        ok(f"Enrichment overhead: {overhead_per_quote:.3f}ms per quote < 1ms requirement")
    else:
        fail(f"Enrichment overhead: {overhead_per_quote:.3f}ms per quote > 1ms requirement")

    # ── Final Summary ─────────────────────────────────────────────────────
    total = CHECKS_PASSED + CHECKS_FAILED
    print(f"\n{'=' * 68}")
    print(f"  Performance Test Results: {CHECKS_PASSED}/{total} passed  |  {CHECKS_FAILED} failed")
    
    if CHECKS_FAILED == 0:
        print(f"\n  ✅ REQUIREMENT 20 VERIFIED: Quote enrichment overhead < 1ms per quote")
        print(f"     - Single quote: {elapsed_ms:.3f}ms")
        print(f"     - Batch average: {avg_time:.3f}ms")  
        print(f"     - End-to-end overhead: {overhead_per_quote:.3f}ms")
        print(f"  ")
        print(f"     Task 7.9 COMPLETED: Enrichment pipeline meets performance requirements")
    else:
        print(f"\n  ❌ REQUIREMENT 20 FAILED: Performance requirements not met")
        print(f"     Review the failed checks above and optimize the enrichment pipeline")
    
    print("=" * 68)
    
    return CHECKS_FAILED == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)