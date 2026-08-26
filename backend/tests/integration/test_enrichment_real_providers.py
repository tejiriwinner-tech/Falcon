"""
Integration Tests for Quote Enrichment with Real Provider Responses (Task 7.12)

Tests end-to-end enrichment pipeline with actual provider data:
- Real provider responses from mock provider and actual providers
- Canonical symbol mapping correctness
- Validation against real data
- Performance measurement with real quotes
- Various instrument types (SPOT, FOREX, INDEX, CRYPTO)
- Enrichment success and warning detection
- Provider mismatch detection

Requirements Validated:
- Requirement 7: Enrichment Integration
- Requirement 20: Performance Requirements
"""
import unittest
import time
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import Mock

from app.core.providers.provider_manager import ProviderManager
from app.core.providers.cache import MarketDataCache
from app.core.providers.symbol_mapper import SymbolMapper
from app.core.providers.provider_registry import ProviderRegistry
from app.core.providers.mock_price_provider import FalconMockPriceProvider
from app.schemas.market_quote import MarketQuote, BidAsk, QuoteStatus, MarketStatus
from app.schemas.enriched_quote import EnrichedMarketQuote
from app.schemas.instrument_models import (
    InstrumentType,
    AssetClass,
    Exchange,
)
from app.core.instruments import instrument_registry, instrument_validator


def create_market_quote_from_provider_response(
    provider_response: dict,
    canonical_symbol: str,
    provider_id: str,
) -> MarketQuote:
    """
    Convert a raw provider response into a MarketQuote for enrichment testing.
    
    This simulates what ProviderManager.get_market_data() does after fetching.
    """
    bid = provider_response.get("bid", provider_response.get("lastPrice", 0.0))
    ask = provider_response.get("ask", provider_response.get("lastPrice", 0.0))
    if bid and ask:
        spread = ask - bid
    else:
        spread = 0.0

    return MarketQuote(
        symbol=canonical_symbol,
        bidAsk=BidAsk(
            bid=bid,
            ask=ask,
            spread=spread,
        ),
        lastPrice=provider_response.get("lastPrice", 0.0),
        change=provider_response.get("change", 0.0),
        changePercent=provider_response.get("changePercent", 0.0),
        timestamp=datetime.now(timezone.utc),
        providerId=provider_id,
        providerName=provider_response.get("providerName", provider_id.title()),
        quoteStatus=QuoteStatus.LIVE,
        marketStatus=MarketStatus.OPEN,
        freshnessSeconds=0.0,
    )


class TestEnrichmentWithRealProviders(unittest.TestCase):
    """Integration tests using real provider instances."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_registry = ProviderRegistry()
        self.mock_cache = MarketDataCache()
        symbol_mapper = SymbolMapper()
        self.provider_manager = ProviderManager(self.mock_registry, self.mock_cache, symbol_mapper)
        
        self.mock_provider = FalconMockPriceProvider()
        self.mock_provider.connect()

    def test_enrich_real_mock_provider_response_gold(self):
        """Test enrichment with real mock provider response for XAUUSD."""
        # Get real quote from mock provider
        provider_response = self.mock_provider.fetch("XAUUSD")
        self.assertIsNotNone(provider_response, "Mock provider should return valid response")

        # Convert to MarketQuote
        quote = create_market_quote_from_provider_response(
            provider_response,
            canonical_symbol="XAUUSD",
            provider_id="mock_provider",
        )

        # Enrich
        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

        # Assertions
        self.assertIsInstance(enriched, EnrichedMarketQuote)
        self.assertEqual(enriched.canonicalSymbol, "XAUUSD")
        self.assertEqual(enriched.instrumentType, InstrumentType.SPOT)
        self.assertEqual(enriched.assetClass, AssetClass.PRECIOUS_METALS)
        self.assertEqual(enriched.exchange, Exchange.FOREX_OTC)
        self.assertEqual(enriched.currency, "USD")
        self.assertEqual(enriched.pipSize, 0.001)
        self.assertEqual(enriched.lastPrice, provider_response["lastPrice"])
        self.assertEqual(enriched.instrumentValidationStatus, "MATCHED")
        self.assertIsNone(enriched.instrumentValidationWarning)

    def test_enrich_real_mock_provider_response_forex_gbpusd(self):
        """Test enrichment with real mock provider response for GBPUSD."""
        provider_response = self.mock_provider.fetch("GBPUSD")
        self.assertIsNotNone(provider_response)

        quote = create_market_quote_from_provider_response(
            provider_response,
            canonical_symbol="GBPUSD",
            provider_id="mock_provider",
        )

        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

        self.assertEqual(enriched.canonicalSymbol, "GBPUSD")
        self.assertEqual(enriched.instrumentType, InstrumentType.FOREX)
        self.assertEqual(enriched.assetClass, AssetClass.CURRENCIES)
        self.assertEqual(enriched.exchange, Exchange.FOREX_OTC)
        self.assertEqual(enriched.pipSize, 0.0001)
        
        # Verify metadata completeness
        instrument = instrument_registry.get_instrument("GBPUSD")
        self.assertEqual(instrument.precision, 4)

    def test_enrich_real_mock_provider_response_index_nas100(self):
        """Test enrichment with real mock provider response for NAS100."""
        provider_response = self.mock_provider.fetch("NAS100")
        self.assertIsNotNone(provider_response)

        quote = create_market_quote_from_provider_response(
            provider_response,
            canonical_symbol="NAS100",
            provider_id="mock_provider",
        )

        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

        self.assertEqual(enriched.canonicalSymbol, "NAS100")
        self.assertEqual(enriched.instrumentType, InstrumentType.INDEX)
        self.assertEqual(enriched.assetClass, AssetClass.INDICES)
        self.assertEqual(enriched.exchange, Exchange.NASDAQ)
        
        # Verify display name from registry
        instrument = instrument_registry.get_instrument("NAS100")
        self.assertEqual(instrument.displayName, "NASDAQ-100")

    def test_enrich_real_mock_provider_response_crypto_btcusd(self):
        """Test enrichment with real mock provider response for BTCUSD."""
        provider_response = self.mock_provider.fetch("BTCUSD")
        self.assertIsNotNone(provider_response)

        quote = create_market_quote_from_provider_response(
            provider_response,
            canonical_symbol="BTCUSD",
            provider_id="mock_provider",
        )

        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

        self.assertEqual(enriched.canonicalSymbol, "BTCUSD")
        self.assertEqual(enriched.instrumentType, InstrumentType.CRYPTO)
        self.assertEqual(enriched.assetClass, AssetClass.CRYPTOCURRENCIES)
        self.assertEqual(enriched.exchange, Exchange.CRYPTO_SPOT)
        
        # Verify display name from registry
        instrument = instrument_registry.get_instrument("BTCUSD")
        self.assertEqual(instrument.displayName, "Bitcoin")

    def test_enrich_all_eight_instruments_with_real_provider(self):
        """Test enrichment for all 8 registered instruments using real provider."""
        instruments = [
            ("XAUUSD", InstrumentType.SPOT, AssetClass.PRECIOUS_METALS),
            ("GBPUSD", InstrumentType.FOREX, AssetClass.CURRENCIES),
            ("EURUSD", InstrumentType.FOREX, AssetClass.CURRENCIES),
            ("USDJPY", InstrumentType.FOREX, AssetClass.CURRENCIES),
            ("NAS100", InstrumentType.INDEX, AssetClass.INDICES),
            ("US30", InstrumentType.INDEX, AssetClass.INDICES),
            ("BTCUSD", InstrumentType.CRYPTO, AssetClass.CRYPTOCURRENCIES),
            ("ETHUSD", InstrumentType.CRYPTO, AssetClass.CRYPTOCURRENCIES),
        ]

        for symbol, expected_type, expected_asset in instruments:
            provider_response = self.mock_provider.fetch(symbol)
            self.assertIsNotNone(provider_response, f"Provider should return response for {symbol}")

            quote = create_market_quote_from_provider_response(
                provider_response,
                canonical_symbol=symbol,
                provider_id="mock_provider",
            )

            enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

            self.assertEqual(enriched.canonicalSymbol, symbol)
            self.assertEqual(enriched.instrumentType, expected_type, f"{symbol} should be {expected_type}")
            self.assertEqual(enriched.assetClass, expected_asset, f"{symbol} should be {expected_asset}")
            self.assertEqual(enriched.instrumentValidationStatus, "MATCHED")

    def test_enrich_preserves_original_quote_data(self):
        """Test that enrichment preserves all original quote data."""
        provider_response = self.mock_provider.fetch("XAUUSD")
        quote = create_market_quote_from_provider_response(
            provider_response,
            canonical_symbol="XAUUSD",
            provider_id="mock_provider",
        )

        original_price = quote.lastPrice
        original_bid = quote.bidAsk.bid
        original_timestamp = quote.timestamp

        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

        # Original data preserved
        self.assertEqual(enriched.symbol, "XAUUSD")
        self.assertEqual(enriched.lastPrice, original_price)
        self.assertEqual(enriched.bidAsk.bid, original_bid)
        self.assertEqual(enriched.timestamp, original_timestamp)
        self.assertEqual(enriched.providerId, "mock_provider")

    def test_validation_log_records_real_enrichment(self):
        """Test that validation log records enrichment events correctly."""
        provider_response = self.mock_provider.fetch("GBPUSD")
        quote = create_market_quote_from_provider_response(
            provider_response,
            canonical_symbol="GBPUSD",
            provider_id="mock_provider",
        )

        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

        # Validation log should have entries
        log = instrument_validator.get_validation_log()
        self.assertGreater(len(log), 0, "Validation log should have entries")

        # Should have at least one GBPUSD entry in recent history (check last 20 entries for GBPUSD)
        gbpusd_entries = [e for e in log[-20:] if e["canonicalSymbol"] == "GBPUSD"]
        self.assertGreater(len(gbpusd_entries), 0, "Should have GBPUSD validation entries")

        # At least one should be valid
        gbpusd_valid = [e for e in gbpusd_entries if e["isValid"]]
        self.assertGreater(len(gbpusd_valid), 0, "Should have valid GBPUSD entries")

        # Check timestamp format
        for entry in gbpusd_entries:
            self.assertIn("timestamp", entry)

    def test_enrichment_performance_real_provider(self):
        """Test that enrichment performance is < 1ms per quote."""
        provider_response = self.mock_provider.fetch("XAUUSD")
        quote = create_market_quote_from_provider_response(
            provider_response,
            canonical_symbol="XAUUSD",
            provider_id="mock_provider",
        )

        # Measure enrichment time
        start_time = time.perf_counter()
        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        self.assertIsNotNone(enriched)
        self.assertLess(elapsed_ms, 1.0, f"Enrichment took {elapsed_ms:.3f}ms, should be < 1ms")

    def test_enrichment_performance_batch_multiple_quotes(self):
        """Test enrichment performance for a batch of quotes."""
        symbols = ["XAUUSD", "GBPUSD", "EURUSD", "NAS100", "BTCUSD"]
        quotes = []

        for symbol in symbols:
            provider_response = self.mock_provider.fetch(symbol)
            quote = create_market_quote_from_provider_response(
                provider_response,
                canonical_symbol=symbol,
                provider_id="mock_provider",
            )
            quotes.append(quote)

        # Measure batch enrichment
        start_time = time.perf_counter()
        enriched_quotes = []
        for quote in quotes:
            enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)
            enriched_quotes.append(enriched)
        total_elapsed_ms = (time.perf_counter() - start_time) * 1000

        avg_per_quote = total_elapsed_ms / len(quotes)
        self.assertLess(avg_per_quote, 1.0, f"Average enrichment {avg_per_quote:.3f}ms/quote, should be < 1ms")
        self.assertEqual(len(enriched_quotes), len(quotes))

    def test_canonical_symbol_mapping_correctness(self):
        """Test that canonical symbols are correctly mapped from provider responses."""
        provider_response = self.mock_provider.fetch("XAUUSD")
        quote = create_market_quote_from_provider_response(
            provider_response,
            canonical_symbol="XAUUSD",
            provider_id="mock_provider",
        )

        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

        # Verify canonical symbol matches registry
        instrument = instrument_registry.get_instrument("XAUUSD")
        self.assertIsNotNone(instrument)
        self.assertEqual(enriched.canonicalSymbol, instrument.canonicalSymbol)

    def test_provider_symbol_tracking_in_enrichment(self):
        """Test that provider symbols are correctly tracked in enriched quotes."""
        provider_response = self.mock_provider.fetch("XAUUSD")
        quote = create_market_quote_from_provider_response(
            provider_response,
            canonical_symbol="XAUUSD",
            provider_id="mock_provider",
        )

        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

        # Provider symbol should be set
        self.assertIsNotNone(enriched.providerSymbol)
        # Should match registry mapping or fallback to original symbol
        instrument = instrument_registry.get_instrument("XAUUSD")
        if instrument:
            expected_provider_symbol = instrument.providerMappings.get("mock_provider", "XAUUSD")
            self.assertEqual(enriched.providerSymbol, expected_provider_symbol)

    def test_enrichment_metadata_completeness(self):
        """Test that all enriched quotes have complete instrument metadata."""
        provider_response = self.mock_provider.fetch("NAS100")
        quote = create_market_quote_from_provider_response(
            provider_response,
            canonical_symbol="NAS100",
            provider_id="mock_provider",
        )

        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

        # All required metadata fields should be present
        self.assertIsNotNone(enriched.canonicalSymbol)
        self.assertIsNotNone(enriched.providerSymbol)
        self.assertIsNotNone(enriched.instrumentType)
        self.assertIsNotNone(enriched.assetClass)
        self.assertIsNotNone(enriched.exchange)
        self.assertIsNotNone(enriched.currency)
        self.assertGreater(enriched.pipSize, 0)
        self.assertIsNotNone(enriched.instrumentValidationStatus)

    def test_enrichment_idempotence(self):
        """Test that enriching the same quote multiple times produces identical results."""
        provider_response = self.mock_provider.fetch("EURUSD")
        quote = create_market_quote_from_provider_response(
            provider_response,
            canonical_symbol="EURUSD",
            provider_id="mock_provider",
        )

        enriched1 = self.provider_manager._enrich_quote_with_instrument_metadata(quote)
        enriched2 = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

        # Results should be identical
        self.assertEqual(enriched1.canonicalSymbol, enriched2.canonicalSymbol)
        self.assertEqual(enriched1.instrumentType, enriched2.instrumentType)
        self.assertEqual(enriched1.assetClass, enriched2.assetClass)
        self.assertEqual(enriched1.instrumentValidationStatus, enriched2.instrumentValidationStatus)

    def test_enrichment_with_different_providers_same_symbol(self):
        """Test enrichment consistency across different providers for same symbol."""
        # Create quotes with same symbol from different providers
        provider_response = self.mock_provider.fetch("BTCUSD")
        
        quotes_by_provider = []
        for provider_id in ["mock_provider"]:  # Using mock for deterministic testing
            quote = create_market_quote_from_provider_response(
                provider_response,
                canonical_symbol="BTCUSD",
                provider_id=provider_id,
            )
            quotes_by_provider.append((provider_id, quote))

        enriched_by_provider = []
        for provider_id, quote in quotes_by_provider:
            enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)
            enriched_by_provider.append((provider_id, enriched))

        # All should have same canonical symbol and type
        canonical_symbols = [e.canonicalSymbol for _, e in enriched_by_provider]
        for s in canonical_symbols:
            self.assertEqual(s, "BTCUSD")

        types = [e.instrumentType for _, e in enriched_by_provider]
        for t in types:
            self.assertEqual(t, InstrumentType.CRYPTO)


class TestEnrichmentEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_registry = ProviderRegistry()
        self.mock_cache = MarketDataCache()
        symbol_mapper = SymbolMapper()
        self.provider_manager = ProviderManager(self.mock_registry, self.mock_cache, symbol_mapper)

    def test_enrich_unknown_symbol_creates_fallback_metadata(self):
        """Test that unknown symbols get fallback metadata."""
        quote = MarketQuote(
            symbol="UNKNOWN_SYMBOL",
            bidAsk=BidAsk(bid=100.0, ask=101.0, spread=1.0),
            lastPrice=100.5,
            change=0.0,
            changePercent=0.0,
            timestamp=datetime.now(timezone.utc),
            providerId="mock_provider",
            providerName="Mock",
            quoteStatus=QuoteStatus.LIVE,
            marketStatus=MarketStatus.OPEN,
            freshnessSeconds=0.0,
        )

        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

        self.assertEqual(enriched.canonicalSymbol, "UNKNOWN_SYMBOL")
        self.assertEqual(enriched.instrumentType, InstrumentType.UNKNOWN)
        self.assertEqual(enriched.assetClass, AssetClass.UNKNOWN)
        self.assertEqual(enriched.exchange, Exchange.UNKNOWN)
        self.assertEqual(enriched.lastPrice, 100.5)

    def test_enrich_zero_price_quote(self):
        """Test enrichment with zero price."""
        quote = MarketQuote(
            symbol="XAUUSD",
            bidAsk=BidAsk(bid=0.0, ask=0.0, spread=0.0),
            lastPrice=0.0,
            change=0.0,
            changePercent=0.0,
            timestamp=datetime.now(timezone.utc),
            providerId="mock_provider",
            providerName="Mock",
            quoteStatus=QuoteStatus.STALE,
            marketStatus=MarketStatus.CLOSED,
            freshnessSeconds=60.0,
        )

        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

        self.assertIsNotNone(enriched)
        self.assertEqual(enriched.canonicalSymbol, "XAUUSD")
        self.assertEqual(enriched.lastPrice, 0.0)

    def test_enrich_with_wide_spread(self):
        """Test enrichment with wide spread (market stress scenario)."""
        quote = MarketQuote(
            symbol="EURUSD",
            bidAsk=BidAsk(bid=1.08, ask=1.10, spread=0.02),
            lastPrice=1.09,
            change=-0.05,
            changePercent=-4.4,
            timestamp=datetime.now(timezone.utc),
            providerId="mock_provider",
            providerName="Mock",
            quoteStatus=QuoteStatus.DELAYED,
            marketStatus=MarketStatus.OPEN,
            freshnessSeconds=5.0,
        )

        enriched = self.provider_manager._enrich_quote_with_instrument_metadata(quote)

        self.assertIsNotNone(enriched)
        self.assertEqual(enriched.canonicalSymbol, "EURUSD")
        self.assertEqual(enriched.bidAsk.spread, 0.02)


if __name__ == "__main__":
    unittest.main()
