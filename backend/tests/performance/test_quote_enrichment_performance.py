"""
Performance Tests for Quote Enrichment Pipeline
==============================================

Task 7.9: Measure and verify enrichment overhead is < 1ms per quote

This test suite measures the performance of the quote enrichment pipeline
to ensure it meets Requirement 20 (Performance): "The per-quote enrichment 
cost (registry lookup + validator call) SHALL be less than 1 millisecond"

Test coverage:
- Single quote enrichment timing
- Batch enrichment timing to simulate real workload  
- Registry lookup performance with all registered instruments
- Validator performance under different scenarios
- Memory usage verification
- Concurrent enrichment performance

Run from backend/ directory:
    python tests/performance/test_quote_enrichment_performance.py
"""

import sys
import os
import time
import unittest
from datetime import datetime, timezone
from typing import List
import statistics

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.providers.provider_manager import ProviderManager
from app.core.providers.provider_registry import ProviderRegistry
from app.core.providers.cache import MarketDataCache
from app.core.providers.symbol_mapper import SymbolMapper
from app.schemas.market_quote import MarketQuote, BidAsk, QuoteStatus, MarketStatus
from app.schemas.enriched_quote import EnrichedMarketQuote
from app.core.instruments import instrument_registry, instrument_validator


class TestQuoteEnrichmentPerformance(unittest.TestCase):
    """Performance tests for quote enrichment pipeline."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Ensure registry is populated with all instruments
        from app.core.instruments.instrument_registry import _populate_registry
        _populate_registry()
        
        # Create provider manager for testing
        cls.registry = ProviderRegistry()
        cls.cache = MarketDataCache()
        cls.symbol_mapper = SymbolMapper()
        cls.provider_manager = ProviderManager(cls.registry, cls.cache, cls.symbol_mapper)
        
        # Test symbols
        cls.test_symbols = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30", "BTCUSD", "ETHUSD"]
    
    def create_test_quote(self, symbol: str, provider_id: str = "twelve_data") -> MarketQuote:
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
    
    def test_single_quote_enrichment_performance(self):
        """
        GIVEN: A single MarketQuote for XAUUSD
        WHEN: enriching with instrument metadata
        THEN: enrichment should complete in < 1ms
        """
        quote = self.create_test_quote("XAUUSD")
        
        # Warm up (ensure any lazy loading is done)
        _ = self.provider_manager._enrich_quote_with_instrument_metadata(quote)
        
        # Measure single enrichment time
        start_time = time.perf_counter()
        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        # Verify enrichment worked
        self.assertIsInstance(enriched, EnrichedMarketQuote)
        self.assertEqual(enriched.canonicalSymbol, "XAUUSD")
        self.assertIsNotNone(enriched.instrumentType)
        
        # Verify performance requirement
        self.assertLess(elapsed_ms, 1.0, 
            f"Single quote enrichment took {elapsed_ms:.3f}ms, exceeds 1ms limit")
        
        print(f"  Single quote enrichment: {elapsed_ms:.3f}ms (PASS)")
    
    def test_batch_enrichment_performance(self):
        """
        GIVEN: Multiple MarketQuotes for all 8 tracked symbols
        WHEN: enriching each with instrument metadata  
        THEN: average enrichment time should be < 1ms per quote
        """
        quotes = [self.create_test_quote(symbol) for symbol in self.test_symbols]
        timings = []
        
        # Warm up
        for quote in quotes:
            _ = self.provider_manager._enrich_quote_with_instrument_metadata(quote)
        
        # Measure batch enrichment times
        for quote in quotes:
            start_time = time.perf_counter()
            enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            timings.append(elapsed_ms)
            
            # Verify enrichment worked
            self.assertIsInstance(enriched, EnrichedMarketQuote)
        
        # Calculate statistics
        avg_time = statistics.mean(timings)
        max_time = max(timings)
        min_time = min(timings)
        
        # Verify performance requirements
        self.assertLess(avg_time, 1.0, 
            f"Average enrichment time {avg_time:.3f}ms exceeds 1ms limit")
        self.assertLess(max_time, 2.0, 
            f"Max enrichment time {max_time:.3f}ms too high (should be < 2ms)")
        
        print(f"  Batch enrichment - avg: {avg_time:.3f}ms, max: {max_time:.3f}ms, min: {min_time:.3f}ms")
        for symbol, timing in zip(self.test_symbols, timings):
            print(f"    {symbol}: {timing:.3f}ms")
    
    def test_registry_lookup_performance(self):
        """
        GIVEN: All 8 instruments registered in the registry
        WHEN: performing many registry lookups
        THEN: lookups should be extremely fast (O(1) performance)
        """
        # Test canonical symbol lookup performance
        start_time = time.perf_counter()
        for _ in range(10000):
            for symbol in self.test_symbols:
                instrument = instrument_registry.get_instrument(symbol)
                self.assertIsNotNone(instrument)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        operations = 10000 * len(self.test_symbols)  # 80,000 operations
        avg_per_op_us = (elapsed_ms * 1000) / operations  # microseconds per operation
        
        # Should be extremely fast
        self.assertLess(elapsed_ms, 100, 
            f"Registry lookups too slow: {elapsed_ms:.1f}ms for {operations} operations")
        
        print(f"  Registry lookup: {elapsed_ms:.1f}ms for {operations} ops ({avg_per_op_us:.2f}μs per lookup)")
    
    def test_provider_symbol_mapping_performance(self):
        """
        GIVEN: All instruments with provider mappings
        WHEN: performing provider symbol resolution
        THEN: mapping should be fast
        """
        providers = ["twelve_data", "yahoo_finance", "mock_price"]
        
        start_time = time.perf_counter()
        for _ in range(1000):
            for symbol in self.test_symbols:
                for provider in providers:
                    provider_symbol = instrument_registry.get_provider_symbol(symbol, provider)
                    self.assertIsNotNone(provider_symbol)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        operations = 1000 * len(self.test_symbols) * len(providers)  # 24,000 operations
        avg_per_op_us = (elapsed_ms * 1000) / operations
        
        self.assertLess(elapsed_ms, 200, 
            f"Provider symbol mapping too slow: {elapsed_ms:.1f}ms for {operations} operations")
        
        print(f"  Provider mapping: {elapsed_ms:.1f}ms for {operations} ops ({avg_per_op_us:.2f}μs per mapping)")
    
    def test_validator_performance(self):
        """
        GIVEN: Instrument validator with various validation scenarios
        WHEN: performing many validations
        THEN: validation should be fast
        """
        test_cases = [
            ("XAUUSD", "XAU/USD", "twelve_data"),  # Valid case
            ("XAUUSD", "GC=F", "yahoo_finance"),   # Type mismatch case (SPOT vs FUTURES)
            ("GBPUSD", "GBP/USD", "twelve_data"),  # Valid case
            ("UNKNOWN", "UNKNOWN", "unknown_provider"),  # Unknown case
        ]
        
        start_time = time.perf_counter()
        for _ in range(5000):
            for canonical, provider_symbol, provider_id in test_cases:
                is_valid, warning = instrument_validator.validate(
                    canonical_symbol=canonical,
                    received_provider_symbol=provider_symbol,
                    provider_id=provider_id
                )
                # Just check that it returns something reasonable
                self.assertIsInstance(is_valid, bool)
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        operations = 5000 * len(test_cases)  # 20,000 validations
        avg_per_op_us = (elapsed_ms * 1000) / operations
        
        self.assertLess(elapsed_ms, 500,
            f"Validation too slow: {elapsed_ms:.1f}ms for {operations} validations")
        
        print(f"  Validator: {elapsed_ms:.1f}ms for {operations} validations ({avg_per_op_us:.2f}μs per validation)")
    
    def test_enrichment_with_unknown_instrument_performance(self):
        """
        GIVEN: A quote for an unknown instrument  
        WHEN: enriching with fallback metadata creation
        THEN: should still be fast (< 2ms including fallback creation)
        """
        quote = self.create_test_quote("UNKNOWN_SYMBOL")
        
        # Warm up
        _ = self.provider_manager._enrich_quote_with_instrument_metadata(quote)
        
        start_time = time.perf_counter()
        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        # Verify fallback worked
        self.assertIsInstance(enriched, EnrichedMarketQuote)
        self.assertEqual(enriched.canonicalSymbol, "UNKNOWN_SYMBOL")
        self.assertEqual(enriched.instrumentType.value, "UNKNOWN")
        
        # Should still be reasonably fast even with fallback creation
        self.assertLess(elapsed_ms, 2.0, 
            f"Unknown instrument enrichment took {elapsed_ms:.3f}ms, too slow")
        
        print(f"  Unknown instrument enrichment: {elapsed_ms:.3f}ms")
    
    def test_concurrent_enrichment_performance(self):
        """
        GIVEN: Multiple quotes being enriched concurrently (simulating real load)
        WHEN: enriching quotes from multiple threads
        THEN: performance should not degrade significantly
        """
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        quotes = [self.create_test_quote(symbol) for symbol in self.test_symbols] * 10  # 80 quotes
        results = []
        
        def enrich_quote(quote):
            start = time.perf_counter()
            enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)
            elapsed_ms = (time.perf_counter() - start) * 1000
            return elapsed_ms, enriched
        
        # Test with multiple threads
        start_time = time.perf_counter()
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(enrich_quote, quote) for quote in quotes]
            for future in as_completed(futures):
                elapsed_ms, enriched = future.result()
                results.append(elapsed_ms)
                self.assertIsInstance(enriched, EnrichedMarketQuote)
        
        total_elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        avg_time = statistics.mean(results)
        max_time = max(results)
        throughput = len(quotes) / (total_elapsed_ms / 1000)  # quotes per second
        
        # Performance should not degrade significantly under concurrent load
        self.assertLess(avg_time, 1.5,
            f"Concurrent average enrichment time {avg_time:.3f}ms too high")
        self.assertGreater(throughput, 1000,
            f"Throughput {throughput:.0f} quotes/sec too low")
        
        print(f"  Concurrent enrichment ({len(quotes)} quotes, 5 threads):")
        print(f"    Total time: {total_elapsed_ms:.1f}ms")
        print(f"    Average per quote: {avg_time:.3f}ms")
        print(f"    Max time: {max_time:.3f}ms") 
        print(f"    Throughput: {throughput:.0f} quotes/sec")
    
    def test_memory_usage_verification(self):
        """
        GIVEN: Quote enrichment pipeline
        WHEN: performing many enrichment operations
        THEN: memory usage should remain stable (no significant leaks)
        """
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform many enrichment operations
        for i in range(1000):
            symbol = self.test_symbols[i % len(self.test_symbols)]
            quote = self.create_test_quote(symbol)
            enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)
            
            # Clear local references periodically
            if i % 100 == 0:
                del enriched
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory
        
        # Memory growth should be minimal (< 10MB for 1000 operations)
        self.assertLess(memory_growth, 10, 
            f"Memory usage grew by {memory_growth:.1f}MB, possible memory leak")
        
        print(f"  Memory usage: initial {initial_memory:.1f}MB, final {final_memory:.1f}MB (growth: {memory_growth:.1f}MB)")


if __name__ == "__main__":
    # Run performance tests with verbose output
    unittest.main(verbosity=2)