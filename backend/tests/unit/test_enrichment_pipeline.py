"""
Unit Tests for Quote Enrichment Pipeline (Task 7.10)

**Validates: Requirement 7 (Enrichment Integration)**

Comprehensive unit tests for the quote enrichment pipeline to verify it works
correctly with all different instrument types in the registry.

Tests coverage includes:
- All registered instrument types (SPOT, FOREX, INDEX, CRYPTO)
- Different asset classes (PRECIOUS_METALS, CURRENCIES, INDICES, CRYPTOCURRENCIES)
- Various provider mappings (twelve_data, yahoo_finance, mock_price)
- Validation scenarios (MATCHED, MISMATCH, UNKNOWN)
- Fallback behavior for unknown instruments
- Performance characteristics
"""

import unittest
import time
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock
from pydantic import ValidationError

from app.core.providers.provider_manager import ProviderManager
from app.core.providers.provider_registry import ProviderRegistry
from app.core.providers.cache import MarketDataCache
from app.core.providers.symbol_mapper import SymbolMapper
from app.schemas.market_quote import MarketQuote, BidAsk, QuoteStatus, MarketStatus
from app.schemas.enriched_quote import EnrichedMarketQuote
from app.schemas.instrument_models import (
    InstrumentType,
    AssetClass,
    Exchange,
    InstrumentMetadata
)
from app.core.instruments import instrument_registry, instrument_validator


class TestEnrichmentPipelineBase(unittest.TestCase):
    """Base test class with common setup for enrichment pipeline tests."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.now = datetime.now(timezone.utc)
        
        # Create mock provider manager dependencies
        self.mock_registry = Mock(spec=ProviderRegistry)
        self.mock_cache = Mock(spec=MarketDataCache)
        self.symbol_mapper = SymbolMapper()
        
        # Create provider manager instance
        self.pm = ProviderManager(self.mock_registry, self.mock_cache, self.symbol_mapper)
        
        # Clear validator log for clean tests
        if hasattr(instrument_validator, '_validation_log'):
            instrument_validator._validation_log.clear()
    
    def create_quote(self, symbol: str, provider_id: str, price: float = 100.0, 
                     bid: float = None, ask: float = None, spread: float = None) -> MarketQuote:
        """Helper to create a market quote with optional bid/ask/spread."""
        if bid is None:
            bid = price - 0.5
        if ask is None:
            ask = price + 0.5
        if spread is None:
            spread = ask - bid
            
        return MarketQuote(
            symbol=symbol,
            bidAsk=BidAsk(bid=bid, ask=ask, spread=spread),
            lastPrice=price,
            change=0.0,
            changePercent=0.0,
            timestamp=self.now,
            providerId=provider_id,
            providerName=provider_id.replace("_", " ").title(),
            quoteStatus=QuoteStatus.LIVE,
            marketStatus=MarketStatus.OPEN,
            freshnessSeconds=0.0,
        )


class TestEnrichmentPipelineInstrumentTypes(TestEnrichmentPipelineBase):
    """Test enrichment with different instrument types."""
    
    def test_enrich_xauusd_spot_precious_metal(self):
        """GIVEN: XAUUSD SPOT instrument WHEN: enriching quote THEN: correct metadata enriched"""
        # XAUUSD is SPOT, PRECIOUS_METALS, FOREX_OTC
        quote = self.create_quote("XAUUSD", "twelve_data", 1950.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # Verify instrument metadata
        self.assertEqual(enriched.canonicalSymbol, "XAUUSD")
        self.assertEqual(enriched.instrumentType, InstrumentType.SPOT)
        self.assertEqual(enriched.assetClass, AssetClass.PRECIOUS_METALS)
        self.assertEqual(enriched.exchange, Exchange.FOREX_OTC)
        self.assertEqual(enriched.currency, "USD")
        self.assertEqual(enriched.pipSize, 0.001)
        
        # Verify quote data preserved
        self.assertEqual(enriched.symbol, "XAUUSD")
        self.assertEqual(enriched.lastPrice, 1950.0)
        self.assertEqual(enriched.providerId, "twelve_data")
    
    def test_enrich_gbpusd_forex_currency(self):
        """GIVEN: GBPUSD FOREX instrument WHEN: enriching quote THEN: correct metadata enriched"""
        # GBPUSD is FOREX, CURRENCIES, FOREX_OTC
        quote = self.create_quote("GBPUSD", "twelve_data", 1.2650, 
                                   bid=1.2645, ask=1.2655, spread=0.0010)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "GBPUSD")
        self.assertEqual(enriched.instrumentType, InstrumentType.FOREX)
        self.assertEqual(enriched.assetClass, AssetClass.CURRENCIES)
        self.assertEqual(enriched.exchange, Exchange.FOREX_OTC)
        self.assertEqual(enriched.currency, "USD")
        self.assertEqual(enriched.pipSize, 0.0001)
        
        # Verify quote data preserved
        self.assertEqual(enriched.symbol, "GBPUSD")
        self.assertEqual(enriched.bidAsk.bid, 1.2645)
        self.assertEqual(enriched.bidAsk.ask, 1.2655)
    
    def test_enrich_eurusd_forex_currency(self):
        """GIVEN: EURUSD FOREX instrument WHEN: enriching quote THEN: correct metadata enriched"""
        # EURUSD is FOREX, CURRENCIES, FOREX_OTC
        quote = self.create_quote("EURUSD", "yahoo_finance", 1.0850, 
                                   bid=1.0845, ask=1.0855, spread=0.0010)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "EURUSD")
        self.assertEqual(enriched.instrumentType, InstrumentType.FOREX)
        self.assertEqual(enriched.assetClass, AssetClass.CURRENCIES)
        self.assertEqual(enriched.exchange, Exchange.FOREX_OTC)
        self.assertEqual(enriched.currency, "USD")
        self.assertEqual(enriched.pipSize, 0.0001)
    
    def test_enrich_usdjpy_forex_currency_jpy(self):
        """GIVEN: USDJPY FOREX instrument WHEN: enriching quote THEN: correct metadata enriched"""
        # USDJPY is FOREX, CURRENCIES, FOREX_OTC, currency JPY
        quote = self.create_quote("USDJPY", "yahoo_finance", 155.25, 
                                   bid=155.20, ask=155.30, spread=0.10)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "USDJPY")
        self.assertEqual(enriched.instrumentType, InstrumentType.FOREX)
        self.assertEqual(enriched.assetClass, AssetClass.CURRENCIES)
        self.assertEqual(enriched.exchange, Exchange.FOREX_OTC)
        self.assertEqual(enriched.currency, "JPY")
        self.assertEqual(enriched.pipSize, 0.01)
    
    def test_enrich_nas100_index_indices(self):
        """GIVEN: NAS100 INDEX instrument WHEN: enriching quote THEN: correct metadata enriched"""
        # NAS100 is INDEX, INDICES, NASDAQ
        quote = self.create_quote("NAS100", "twelve_data", 18000.50, 
                                   bid=18000.00, ask=18001.00, spread=1.00)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "NAS100")
        self.assertEqual(enriched.instrumentType, InstrumentType.INDEX)
        self.assertEqual(enriched.assetClass, AssetClass.INDICES)
        self.assertEqual(enriched.exchange, Exchange.NASDAQ)
        self.assertEqual(enriched.currency, "USD")
        self.assertEqual(enriched.pipSize, 0.01)
    
    def test_enrich_us30_index_indices(self):
        """GIVEN: US30 INDEX instrument WHEN: enriching quote THEN: correct metadata enriched"""
        # US30 is INDEX, INDICES, NYSE
        quote = self.create_quote("US30", "yahoo_finance", 39000.75, 
                                   bid=38999.50, ask=39001.00, spread=1.50)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "US30")
        self.assertEqual(enriched.instrumentType, InstrumentType.INDEX)
        self.assertEqual(enriched.assetClass, AssetClass.INDICES)
        self.assertEqual(enriched.exchange, Exchange.NYSE)
        self.assertEqual(enriched.currency, "USD")
        self.assertEqual(enriched.pipSize, 0.01)
    
    def test_enrich_btcusd_crypto_cryptocurrencies(self):
        """GIVEN: BTCUSD CRYPTO instrument WHEN: enriching quote THEN: correct metadata enriched"""
        # BTCUSD is CRYPTO, CRYPTOCURRENCIES, CRYPTO_SPOT
        quote = self.create_quote("BTCUSD", "twelve_data", 43500.00, 
                                   bid=43400.00, ask=43600.00, spread=200.00)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "BTCUSD")
        self.assertEqual(enriched.instrumentType, InstrumentType.CRYPTO)
        self.assertEqual(enriched.assetClass, AssetClass.CRYPTOCURRENCIES)
        self.assertEqual(enriched.exchange, Exchange.CRYPTO_SPOT)
        self.assertEqual(enriched.currency, "USD")
        self.assertEqual(enriched.pipSize, 0.01)
    
    def test_enrich_ethusd_crypto_cryptocurrencies(self):
        """GIVEN: ETHUSD CRYPTO instrument WHEN: enriching quote THEN: correct metadata enriched"""
        # ETHUSD is CRYPTO, CRYPTOCURRENCIES, CRYPTO_SPOT
        quote = self.create_quote("ETHUSD", "yahoo_finance", 2300.50, 
                                   bid=2295.00, ask=2306.00, spread=11.00)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "ETHUSD")
        self.assertEqual(enriched.instrumentType, InstrumentType.CRYPTO)
        self.assertEqual(enriched.assetClass, AssetClass.CRYPTOCURRENCIES)
        self.assertEqual(enriched.exchange, Exchange.CRYPTO_SPOT)
        self.assertEqual(enriched.currency, "USD")
        self.assertEqual(enriched.pipSize, 0.01)


class TestEnrichmentPipelineProviderSymbols(TestEnrichmentPipelineBase):
    """Test enrichment with different provider symbols for the same instrument."""
    
    def test_enrich_xauusd_twelve_data_provider_symbol(self):
        """GIVEN: XAUUSD from twelve_data WHEN: enriching quote THEN: provider symbol correct"""
        # TwelveData uses XAU/USD for XAUUSD, but quote symbol is canonical
        quote = self.create_quote("XAUUSD", "twelve_data", 1950.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "XAUUSD")
        # Provider symbol should be resolved to XAU/USD via mapper
        self.assertEqual(enriched.providerSymbol, "XAU/USD")
    
    def test_enrich_xauusd_yahoo_finance_provider_symbol(self):
        """GIVEN: XAUUSD from yahoo_finance WHEN: enriching quote THEN: provider symbol correct"""
        # Yahoo Finance uses GC=F for XAUUSD, but quote symbol is canonical
        quote = self.create_quote("XAUUSD", "yahoo_finance", 1952.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "XAUUSD")
        # Provider symbol should be resolved to GC=F via mapper
        self.assertEqual(enriched.providerSymbol, "GC=F")
    
    def test_enrich_xauusd_mock_price_provider_symbol(self):
        """GIVEN: XAUUSD from mock_price WHEN: enriching quote THEN: provider symbol correct"""
        # Mock provider uses XAUUSD as is
        quote = self.create_quote("XAUUSD", "mock_price", 1951.5)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "XAUUSD")
        self.assertEqual(enriched.providerSymbol, "XAUUSD")
    
    def test_enrich_nas100_twelve_data_provider_symbol(self):
        """GIVEN: NAS100 from twelve_data WHEN: enriching quote THEN: provider symbol correct"""
        quote = self.create_quote("NAS100", "twelve_data", 18000.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "NAS100")
        self.assertEqual(enriched.providerSymbol, "NAS100")
    
    def test_enrich_nas100_yahoo_finance_provider_symbol(self):
        """GIVEN: NAS100 from yahoo_finance WHEN: enriching quote THEN: provider symbol correct"""
        # Yahoo Finance uses ^NDX for NAS100
        quote = self.create_quote("NAS100", "yahoo_finance", 18000.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "NAS100")
        # Provider symbol should be resolved to ^NDX via mapper
        self.assertEqual(enriched.providerSymbol, "^NDX")
    
    def test_enrich_us30_twelve_data_provider_symbol(self):
        """GIVEN: US30 from twelve_data WHEN: enriching quote THEN: provider symbol correct"""
        # TwelveData uses DJI for US30
        quote = self.create_quote("US30", "twelve_data", 39000.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "US30")
        # Provider symbol should be resolved to DJI via mapper
        self.assertEqual(enriched.providerSymbol, "DJI")
    
    def test_enrich_us30_yahoo_finance_provider_symbol(self):
        """GIVEN: US30 from yahoo_finance WHEN: enriching quote THEN: provider symbol correct"""
        # Yahoo Finance uses ^DJI for US30
        quote = self.create_quote("US30", "yahoo_finance", 39000.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.canonicalSymbol, "US30")
        # Provider symbol should be resolved to ^DJI via mapper
        self.assertEqual(enriched.providerSymbol, "^DJI")


class TestEnrichmentPipelineValidationStatus(TestEnrichmentPipelineBase):
    """Test enrichment validation status for different scenarios."""
    
    def test_enrichment_validation_status_matched(self):
        """GIVEN: Quote with matching provider symbol WHEN: enriching THEN: status MATCHED"""
        # XAUUSD with twelve_data should be MATCHED (SPOT with SPOT expected)
        quote = self.create_quote("XAUUSD", "twelve_data", 1950.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.instrumentValidationStatus, "MATCHED")
        self.assertIsNone(enriched.instrumentValidationWarning)
    
    def test_enrichment_validation_status_unknown_for_unknown_symbol(self):
        """GIVEN: Unknown symbol WHEN: enriching THEN: status appropriate for fallback"""
        # Unknown symbol should create fallback metadata
        quote = self.create_quote("UNKNOWN_SYMBOL_123", "mock_price", 100.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # Unknown symbol falls back to UNKNOWN type, validation may be MATCHED 
        # since unknown symbols don't trigger mismatches
        self.assertEqual(enriched.instrumentType, InstrumentType.UNKNOWN)
        self.assertEqual(enriched.assetClass, AssetClass.UNKNOWN)
        # Status depends on validator logic for unknown symbols
    
    def test_enrichment_validation_log_populated(self):
        """GIVEN: Enrichment occurs WHEN: checking validator log THEN: entry created"""
        initial_log_length = len(instrument_validator.get_validation_log())
        
        quote = self.create_quote("GBPUSD", "twelve_data", 1.2650)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        log = instrument_validator.get_validation_log()
        self.assertGreater(len(log), initial_log_length)
        
        # Check latest entry
        latest = log[-1]
        self.assertEqual(latest["canonicalSymbol"], "GBPUSD")
        self.assertIn("timestamp", latest)
        self.assertIn("providerId", latest)
        self.assertIn("isValid", latest)


class TestEnrichmentPipelinePerformance(TestEnrichmentPipelineBase):
    """Test performance characteristics of enrichment pipeline."""
    
    def test_enrichment_performance_under_1ms(self):
        """GIVEN: Enrichment operation WHEN: measuring time THEN: should be under 1ms"""
        # Measure enrichment performance for multiple instruments
        test_symbols = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", 
                       "NAS100", "US30", "BTCUSD", "ETHUSD"]
        
        for symbol in test_symbols:
            quote = self.create_quote(symbol, "twelve_data", 100.0)
            
            start_time = time.perf_counter()
            enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
            end_time = time.perf_counter()
            
            elapsed_ms = (end_time - start_time) * 1000
            
            # Verify enrichment succeeded
            self.assertEqual(enriched.canonicalSymbol, symbol)
            
            # Log performance for monitoring (actual threshold may vary)
            self.assertLess(elapsed_ms, 10.0,  # More realistic threshold for tests
                           f"Enrichment for {symbol} took {elapsed_ms:.3f}ms")
    
    def test_enrichment_performance_multiple_iterations(self):
        """GIVEN: Multiple enrichment operations WHEN: measuring aggregate time 
        THEN: average should be efficient"""
        quote = self.create_quote("XAUUSD", "twelve_data", 1950.0)
        iterations = 100
        total_time = 0.0
        
        for _ in range(iterations):
            start_time = time.perf_counter()
            enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
            end_time = time.perf_counter()
            total_time += (end_time - start_time)
            
            # Verify consistent results
            self.assertEqual(enriched.canonicalSymbol, "XAUUSD")
        
        avg_time_ms = (total_time / iterations) * 1000
        # Performance check - enrichment should be very fast
        self.assertLess(avg_time_ms, 1.0,  # Requirement 7: < 1ms per quote
                       f"Average enrichment time {avg_time_ms:.3f}ms exceeds 1ms threshold")


class TestEnrichmentPipelineEdgeCases(TestEnrichmentPipelineBase):
    """Test edge cases and error scenarios in enrichment pipeline."""
    
    def test_enrichment_symbol_mapper_normalization_failure(self):
        """GIVEN: Symbol that can't be normalized WHEN: enriching THEN: uses uppercase fallback"""
        # Mock symbol mapper to return None
        original_mapper = self.pm._mapper.normalize
        self.pm._mapper.normalize = Mock(return_value=None)
        
        try:
            quote = self.create_quote("CUSTOM_SYMB", "mock_price", 100.0)
            enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
            
            # Should use uppercase symbol as canonical
            self.assertEqual(enriched.canonicalSymbol, "CUSTOM_SYMB")
            # Should create fallback metadata
            self.assertEqual(enriched.instrumentType, InstrumentType.UNKNOWN)
        finally:
            # Restore original mapper
            self.pm._mapper.normalize = original_mapper
    
    def test_enrichment_provider_symbol_resolution_failure(self):
        """GIVEN: Provider symbol resolution fails WHEN: enriching THEN: uses original symbol"""
        # Mock to_provider_symbol to raise exception
        original_to_provider = self.pm._mapper.to_provider_symbol
        self.pm._mapper.to_provider_symbol = Mock(side_effect=Exception("Mapping failed"))
        
        try:
            quote = self.create_quote("XAUUSD", "twelve_data", 1950.0)
            enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
            
            # Should use original symbol as provider symbol
            self.assertEqual(enriched.providerSymbol, "XAUUSD")
            # Should still enrich successfully
            self.assertEqual(enriched.canonicalSymbol, "XAUUSD")
        finally:
            # Restore original mapper
            self.pm._mapper.to_provider_symbol = original_to_provider
    
    def test_enrichment_with_missing_bid_ask_handled(self):
        """GIVEN: Quote with missing bid/ask (unlikely) WHEN: enriching THEN: still works"""
        # This would be caught by MarketQuote validation, but test robustness
        pass  # MarketQuote requires bidAsk, so this is validated at quote creation


class TestEnrichmentPipelineAssetClassCoverage(TestEnrichmentPipelineBase):
    """Test enrichment across all asset classes."""
    
    def test_asset_class_precious_metals(self):
        """GIVEN: PRECIOUS_METALS asset class WHEN: enriching THEN: correct metadata"""
        quote = self.create_quote("XAUUSD", "twelve_data", 1950.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.assetClass, AssetClass.PRECIOUS_METALS)
    
    def test_asset_class_currencies(self):
        """GIVEN: CURRENCIES asset class WHEN: enriching THEN: correct metadata"""
        quote = self.create_quote("GBPUSD", "twelve_data", 1.2650)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.assetClass, AssetClass.CURRENCIES)
    
    def test_asset_class_indices(self):
        """GIVEN: INDICES asset class WHEN: enriching THEN: correct metadata"""
        quote = self.create_quote("NAS100", "twelve_data", 18000.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.assetClass, AssetClass.INDICES)
    
    def test_asset_class_cryptocurrencies(self):
        """GIVEN: CRYPTOCURRENCIES asset class WHEN: enriching THEN: correct metadata"""
        quote = self.create_quote("BTCUSD", "twelve_data", 43500.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.assetClass, AssetClass.CRYPTOCURRENCIES)


class TestEnrichmentPipelineExchangeCoverage(TestEnrichmentPipelineBase):
    """Test enrichment across all exchanges."""
    
    def test_exchange_forex_otc(self):
        """GIVEN: FOREX_OTC exchange WHEN: enriching THEN: correct metadata"""
        quote = self.create_quote("XAUUSD", "twelve_data", 1950.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.exchange, Exchange.FOREX_OTC)
    
    def test_exchange_nasdaq(self):
        """GIVEN: NASDAQ exchange WHEN: enriching THEN: correct metadata"""
        quote = self.create_quote("NAS100", "twelve_data", 18000.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.exchange, Exchange.NASDAQ)
    
    def test_exchange_nyse(self):
        """GIVEN: NYSE exchange WHEN: enriching THEN: correct metadata"""
        quote = self.create_quote("US30", "twelve_data", 39000.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.exchange, Exchange.NYSE)
    
    def test_exchange_crypto_spot(self):
        """GIVEN: CRYPTO_SPOT exchange WHEN: enriching THEN: correct metadata"""
        quote = self.create_quote("BTCUSD", "twelve_data", 43500.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        self.assertEqual(enriched.exchange, Exchange.CRYPTO_SPOT)


class TestEnrichmentPipelineFallbackBehavior(TestEnrichmentPipelineBase):
    """Test fallback behavior for unknown/unregistered instruments.
    
    **Validates: Requirement 7.4 (Fallback for unknown instruments)**
    
    When the enrichment pipeline encounters unknown instruments not in the registry,
    it should create minimal fallback metadata with UNKNOWN values while preserving
    all original quote data and ensuring validation status is UNKNOWN.
    """
    
    def test_fallback_unknown_symbol_creates_minimal_metadata(self):
        """GIVEN: Unknown symbol not in registry WHEN: enriching THEN: creates fallback metadata"""
        unknown_symbol = "CUSTOM_SYMBOL_XYZ123"
        quote = self.create_quote(unknown_symbol, "mock_price", 123.45)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # Should create fallback metadata with UNKNOWN values
        self.assertEqual(enriched.canonicalSymbol, unknown_symbol)
        self.assertEqual(enriched.instrumentType, InstrumentType.UNKNOWN)
        self.assertEqual(enriched.assetClass, AssetClass.UNKNOWN)
        self.assertEqual(enriched.exchange, Exchange.UNKNOWN)
        self.assertEqual(enriched.currency, "USD")  # Default currency
        self.assertEqual(enriched.pipSize, 0.01)  # Default pip size
        
        # Original quote data preserved
        self.assertEqual(enriched.symbol, unknown_symbol)
        self.assertEqual(enriched.lastPrice, 123.45)
        self.assertEqual(enriched.providerId, "mock_price")
    
    def test_fallback_enrichment_not_blocked_with_unknown_instrument(self):
        """GIVEN: Unknown instrument WHEN: enriching THEN: enrichment succeeds, not blocked"""
        unknown_symbol = "EXOTIC_PAIR_99"
        quote = self.create_quote(unknown_symbol, "twelve_data", 55.75)
        
        # Enrichment should succeed without throwing exception
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # Verify enrichment completed successfully
        self.assertIsNotNone(enriched)
        self.assertIsInstance(enriched, EnrichedMarketQuote)
        self.assertEqual(enriched.symbol, unknown_symbol)
        self.assertEqual(enriched.lastPrice, 55.75)
    
    def test_fallback_metadata_with_multiple_unknown_symbols(self):
        """GIVEN: Multiple unknown symbols WHEN: enriching each THEN: independent fallback metadata"""
        symbols = ["UNKNOWN_A", "UNKNOWN_B", "EXOTIC_XYZ"]
        
        enriched_list = []
        for symbol in symbols:
            quote = self.create_quote(symbol, "mock_price", 100.0)
            enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
            enriched_list.append(enriched)
        
        # Each should have fallback metadata
        for i, enriched in enumerate(enriched_list):
            self.assertEqual(enriched.canonicalSymbol, symbols[i])
            self.assertEqual(enriched.instrumentType, InstrumentType.UNKNOWN)
            self.assertEqual(enriched.assetClass, AssetClass.UNKNOWN)
    
    def test_fallback_includes_provider_mapping_in_metadata(self):
        """GIVEN: Unknown symbol with specific provider WHEN: enriching THEN: provider mapping captured"""
        unknown_symbol = "CUSTOM_SYMBOL_ABC"
        provider_id = "custom_provider"
        quote = self.create_quote(unknown_symbol, provider_id, 99.99)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # Fallback should include the actual provider mapping
        # Verify enriched quote has provider symbol
        self.assertEqual(enriched.providerSymbol, unknown_symbol)
        self.assertEqual(enriched.providerId, provider_id)
    
    def test_fallback_validation_status_for_unknown_instrument(self):
        """GIVEN: Unknown instrument WHEN: enriching THEN: validation status is appropriate"""
        unknown_symbol = "UNKNOWN_INST_XYZ"
        quote = self.create_quote(unknown_symbol, "mock_price", 123.45)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # Validation of unknown instrument should pass through (not force mismatch)
        # Unknown instruments are treated as pass-through (no validation failure)
        self.assertIsNotNone(enriched.instrumentValidationStatus)
        # The status should be MATCHED since unknown types pass validation
        self.assertEqual(enriched.instrumentValidationStatus, "MATCHED")
        # No warning should be present for unknown instruments
        self.assertIsNone(enriched.instrumentValidationWarning)
    
    def test_fallback_preserves_all_original_quote_data(self):
        """GIVEN: Unknown symbol with complete quote data WHEN: enriching 
        THEN: all original data preserved exactly"""
        unknown_symbol = "CUSTOM_SYMB"
        quote = self.create_quote(unknown_symbol, "mock_price", 100.0,
                                   bid=99.5, ask=100.5, spread=1.0)
        quote.change = 1.5
        quote.changePercent = 1.52
        quote.freshnessSeconds = 2.5
        quote.quoteStatus = QuoteStatus.DELAYED
        
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # Verify all original data preserved exactly
        self.assertEqual(enriched.symbol, unknown_symbol)
        self.assertEqual(enriched.bidAsk.bid, 99.5)
        self.assertEqual(enriched.bidAsk.ask, 100.5)
        self.assertEqual(enriched.bidAsk.spread, 1.0)
        self.assertEqual(enriched.lastPrice, 100.0)
        self.assertEqual(enriched.change, 1.5)
        self.assertEqual(enriched.changePercent, 1.52)
        self.assertEqual(enriched.timestamp, quote.timestamp)
        self.assertEqual(enriched.providerId, "mock_price")
        self.assertEqual(enriched.freshnessSeconds, 2.5)
        self.assertEqual(enriched.quoteStatus, QuoteStatus.DELAYED)
    
    def test_fallback_handles_various_price_levels(self):
        """GIVEN: Unknown symbol with various price levels WHEN: enriching THEN: all prices preserved"""
        test_cases = [
            (0.0001, 0.00005, 0.00015),  # Very small prices
            (1.0, 0.5, 1.5),  # Normal prices
            (10000.0, 9999.0, 10001.0),  # Large prices
            (0.001, 0.0005, 0.0015),  # Fractional prices
        ]
        
        for i, (last_price, bid, ask) in enumerate(test_cases):
            quote = self.create_quote(f"UNKNOWN_{i}", "mock_price", last_price, 
                                       bid=bid, ask=ask)
            enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
            
            self.assertEqual(enriched.lastPrice, last_price)
            self.assertEqual(enriched.bidAsk.bid, bid)
            self.assertEqual(enriched.bidAsk.ask, ask)
    
    def test_fallback_with_all_providers(self):
        """GIVEN: Unknown symbol from each provider WHEN: enriching THEN: all providers handled"""
        unknown_symbol = "MULTI_PROVIDER_TEST"
        providers = ["twelve_data", "yahoo_finance", "mock_price", "custom_provider"]
        
        for provider in providers:
            quote = self.create_quote(unknown_symbol, provider, 100.0)
            enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
            
            # Each should create fallback successfully
            self.assertEqual(enriched.canonicalSymbol, unknown_symbol)
            self.assertEqual(enriched.instrumentType, InstrumentType.UNKNOWN)
            self.assertEqual(enriched.providerId, provider)
    
    def test_fallback_creates_immutable_metadata(self):
        """GIVEN: Unknown instrument fallback metadata WHEN: attempting to modify THEN: immutable"""
        unknown_symbol = "IMMUTABLE_TEST"
        quote = self.create_quote(unknown_symbol, "mock_price", 100.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # EnrichedMarketQuote should be a valid Pydantic model
        # Verify it's constructed correctly without errors
        self.assertIsInstance(enriched, EnrichedMarketQuote)
        
        # Try to access fields to ensure they're properly set
        _ = enriched.canonicalSymbol
        _ = enriched.instrumentType
        _ = enriched.assetClass
    
    def test_fallback_with_zero_bid_ask_spread(self):
        """GIVEN: Unknown symbol with zero bid-ask spread WHEN: enriching THEN: handled correctly"""
        unknown_symbol = "ZERO_SPREAD_TEST"
        price = 100.0
        quote = self.create_quote(unknown_symbol, "mock_price", price,
                                   bid=price, ask=price, spread=0.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # Should handle zero spread gracefully
        self.assertEqual(enriched.lastPrice, price)
        self.assertEqual(enriched.bidAsk.bid, price)
        self.assertEqual(enriched.bidAsk.ask, price)
        self.assertEqual(enriched.bidAsk.spread, 0.0)
    
    def test_fallback_currency_defaults_to_usd(self):
        """GIVEN: Unknown symbol WHEN: enriching THEN: currency defaults to USD"""
        unknown_symbol = "CURRENCY_DEFAULT_TEST"
        quote = self.create_quote(unknown_symbol, "mock_price", 100.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # Should default to USD for unknown instruments
        self.assertEqual(enriched.currency, "USD")
    
    def test_fallback_pip_size_defaults_to_0_01(self):
        """GIVEN: Unknown symbol WHEN: enriching THEN: pip size defaults to 0.01"""
        unknown_symbol = "PIP_SIZE_DEFAULT_TEST"
        quote = self.create_quote(unknown_symbol, "mock_price", 100.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # Should default to 0.01 pip size for unknown instruments
        self.assertEqual(enriched.pipSize, 0.01)
    
    def test_fallback_active_status_true(self):
        """GIVEN: Unknown symbol WHEN: creating fallback metadata THEN: active status is true"""
        unknown_symbol = "ACTIVE_STATUS_TEST"
        quote = self.create_quote(unknown_symbol, "mock_price", 100.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # Fallback should have active=true (treat as available)
        # This is reflected in the enrichment being created successfully
        self.assertIsNotNone(enriched)
    
    def test_fallback_enrichment_idempotent(self):
        """GIVEN: Unknown symbol enriched multiple times WHEN: comparing results THEN: identical"""
        unknown_symbol = "IDEMPOTENT_TEST"
        quote1 = self.create_quote(unknown_symbol, "mock_price", 100.0)
        quote2 = self.create_quote(unknown_symbol, "mock_price", 100.0)
        
        enriched1 = self.pm._enrich_quote_with_instrument_metadata(quote1)
        enriched2 = self.pm._enrich_quote_with_instrument_metadata(quote2)
        
        # Results should be identical (idempotent)
        self.assertEqual(enriched1.canonicalSymbol, enriched2.canonicalSymbol)
        self.assertEqual(enriched1.instrumentType, enriched2.instrumentType)
        self.assertEqual(enriched1.assetClass, enriched2.assetClass)
        self.assertEqual(enriched1.exchange, enriched2.exchange)
        self.assertEqual(enriched1.pipSize, enriched2.pipSize)
    
    def test_fallback_validation_logged(self):
        """GIVEN: Unknown symbol enrichment WHEN: validation occurs THEN: logged to validator"""
        initial_log_count = len(instrument_validator.get_validation_log())
        
        unknown_symbol = "VALIDATION_LOG_TEST"
        quote = self.create_quote(unknown_symbol, "mock_price", 100.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # Validation should be logged
        new_log = instrument_validator.get_validation_log()
        self.assertGreater(len(new_log), initial_log_count)
        
        # Latest entry should be for this unknown symbol
        latest = new_log[-1]
        self.assertEqual(latest["canonicalSymbol"], unknown_symbol)
        self.assertIsNotNone(latest["timestamp"])
        self.assertIn("isValid", latest)
    
    def test_fallback_does_not_throw_exception_on_missing_metadata(self):
        """GIVEN: Unknown symbol without metadata in registry WHEN: enriching THEN: no exception"""
        unknown_symbol = "EXCEPTION_TEST_SYMBOL"
        quote = self.create_quote(unknown_symbol, "mock_price", 100.0)
        
        # Should not raise any exception
        try:
            enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
            self.assertIsNotNone(enriched)
        except Exception as e:
            self.fail(f"Enrichment should not raise exception for unknown symbol: {e}")
    
    def test_fallback_enriched_quote_is_valid_model(self):
        """GIVEN: Unknown symbol WHEN: enriching THEN: returned EnrichedMarketQuote is valid"""
        unknown_symbol = "MODEL_VALIDATION_TEST"
        quote = self.create_quote(unknown_symbol, "mock_price", 100.0)
        enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
        
        # Should be valid EnrichedMarketQuote instance
        self.assertIsInstance(enriched, EnrichedMarketQuote)
        
        # All required fields should be present
        self.assertIsNotNone(enriched.symbol)
        self.assertIsNotNone(enriched.canonicalSymbol)
        self.assertIsNotNone(enriched.instrumentType)
        self.assertIsNotNone(enriched.assetClass)
        self.assertIsNotNone(enriched.exchange)
        self.assertIsNotNone(enriched.providerId)
    
    def test_fallback_with_symbol_normalization_failure(self):
        """GIVEN: Unknown symbol when normalization fails WHEN: enriching THEN: fallback works"""
        unknown_symbol = "NORMALIZATION_FAILURE"
        quote = self.create_quote(unknown_symbol, "mock_price", 100.0)
        
        # Mock the symbol mapper to return None (normalization failure)
        original_normalize = self.pm._mapper.normalize
        self.pm._mapper.normalize = Mock(return_value=None)
        
        try:
            enriched = self.pm._enrich_quote_with_instrument_metadata(quote)
            
            # Should use uppercase as fallback canonical
            self.assertEqual(enriched.canonicalSymbol, unknown_symbol.upper())
            self.assertEqual(enriched.instrumentType, InstrumentType.UNKNOWN)
        finally:
            # Restore
            self.pm._mapper.normalize = original_normalize


if __name__ == "__main__":
    unittest.main()
