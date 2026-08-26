"""
Unit tests for CanonicalInstrumentRegistry.

Tests all registry methods:
- register_instrument() - registration and index rebuild
- get_instrument() - canonical symbol lookup
- get_by_provider_symbol() - reverse lookup
- get_provider_symbol() - provider symbol retrieval
- all_instruments() - complete listing
- _rebuild_indices() - index consistency
- _normalize_provider_id() - provider ID normalization

Also tests performance characteristics and edge cases.

**Validates: Requirement 1 (Registry), Requirement 10 (Reverse Lookup), Requirement 20 (Performance)**
"""

import unittest
import time
from datetime import datetime, timezone
from app.core.instruments.instrument_registry import CanonicalInstrumentRegistry
from app.schemas.instrument_models import (
    InstrumentMetadata,
    InstrumentType,
    AssetClass,
    Exchange,
)


def create_xauusd_metadata():
    """Create XAUUSD instrument metadata."""
    return InstrumentMetadata(
        canonicalSymbol="XAUUSD",
        instrumentType=InstrumentType.SPOT,
        assetClass=AssetClass.PRECIOUS_METALS,
        exchange=Exchange.FOREX_OTC,
        currency="USD",
        pipSize=0.001,
        precision=3,
        displayName="Gold (Spot)",
        description="Spot gold traded over-the-counter",
        providerMappings={
            "twelve_data": "XAU/USD",
            "alpha_vantage": "XAU",
            "mock_price": "XAUUSD",
        },
        expectedInstrumentTypes=[InstrumentType.SPOT, InstrumentType.FOREX],
        addedAt=datetime.now(timezone.utc),
        lastUpdatedAt=datetime.now(timezone.utc),
    )


def create_gbpusd_metadata():
    """Create GBPUSD instrument metadata."""
    return InstrumentMetadata(
        canonicalSymbol="GBPUSD",
        instrumentType=InstrumentType.FOREX,
        assetClass=AssetClass.CURRENCIES,
        exchange=Exchange.FOREX_OTC,
        currency="USD",
        pipSize=0.0001,
        precision=4,
        displayName="GBP/USD",
        description="British pound / US dollar currency pair",
        providerMappings={
            "twelve_data": "GBP/USD",
            "alpha_vantage": "GBP/USD",
            "mock_price": "GBPUSD",
        },
        expectedInstrumentTypes=[InstrumentType.FOREX],
        addedAt=datetime.now(timezone.utc),
        lastUpdatedAt=datetime.now(timezone.utc),
    )


def create_btcusd_metadata():
    """Create BTCUSD instrument metadata."""
    return InstrumentMetadata(
        canonicalSymbol="BTCUSD",
        instrumentType=InstrumentType.CRYPTO,
        assetClass=AssetClass.CRYPTOCURRENCIES,
        exchange=Exchange.CRYPTO_SPOT,
        currency="USD",
        pipSize=0.01,
        precision=2,
        displayName="Bitcoin",
        description="Bitcoin cryptocurrency spot price",
        providerMappings={
            "twelve_data": "BTC/USD",
            "alpha_vantage": "BTC/USD",
            "mock_price": "BTCUSD",
        },
        expectedInstrumentTypes=[InstrumentType.CRYPTO],
        addedAt=datetime.now(timezone.utc),
        lastUpdatedAt=datetime.now(timezone.utc),
    )


class TestRegisterInstrument(unittest.TestCase):
    """Tests for register_instrument() method."""
    
    def setUp(self):
        """Create empty registry for each test."""
        self.registry = CanonicalInstrumentRegistry()
    
    def test_register_single_instrument(self):
        """GIVEN: Empty registry WHEN: registering instrument THEN: should store it"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        # Verify it's in registry
        assert self.registry.get_instrument("XAUUSD") is not None
        assert self.registry.get_instrument("XAUUSD").canonicalSymbol == "XAUUSD"
    
    def test_register_multiple_instruments(self):
        """GIVEN: Empty registry WHEN: registering multiple instruments THEN: all should be stored"""
        xauusd = create_xauusd_metadata()
        gbpusd = create_gbpusd_metadata()
        self.registry.register_instrument(xauusd)
        self.registry.register_instrument(gbpusd)
        
        self.assertIsNotNone(self.registry.get_instrument("XAUUSD"))
        self.assertIsNotNone(self.registry.get_instrument("GBPUSD"))
        self.assertEqual(len(self.registry.all_instruments()), 2)
    
    def test_register_replaces_existing(self):
        """GIVEN: Registry with instrument WHEN: re-registering with changes THEN: should update"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        # Create updated metadata with different type
        updated = InstrumentMetadata(
            canonicalSymbol="XAUUSD",
            instrumentType=InstrumentType.FUTURES,
            assetClass=AssetClass.PRECIOUS_METALS,
            exchange=Exchange.COMEX,
            currency="USD",
            pipSize=0.01,
            precision=2,
            displayName="Gold (Futures)",
            providerMappings=xauusd.providerMappings,
            expectedInstrumentTypes=[InstrumentType.FUTURES],
            addedAt=datetime.now(timezone.utc),
            lastUpdatedAt=datetime.now(timezone.utc),
        )
        
        self.registry.register_instrument(updated)
        
        # Verify it's updated
        retrieved = self.registry.get_instrument("XAUUSD")
        self.assertEqual(retrieved.instrumentType, InstrumentType.FUTURES)
        self.assertEqual(retrieved.displayName, "Gold (Futures)")
    
    def test_register_missing_canonical_symbol_raises(self):
        """GIVEN: Metadata without canonical symbol WHEN: registering THEN: should raise error"""
        bad_metadata = InstrumentMetadata(
            canonicalSymbol="",
            instrumentType=InstrumentType.SPOT,
            assetClass=AssetClass.PRECIOUS_METALS,
            exchange=Exchange.FOREX_OTC,
            currency="USD",
            pipSize=0.001,
            precision=3,
            displayName="Bad",
            providerMappings={"mock": "MOCK"},
            expectedInstrumentTypes=[InstrumentType.SPOT],
            addedAt=datetime.now(timezone.utc),
            lastUpdatedAt=datetime.now(timezone.utc),
        )
        
        with self.assertRaises(ValueError) as context:
            self.registry.register_instrument(bad_metadata)
        self.assertIn("canonicalSymbol is required", str(context.exception))
    
    def test_register_missing_provider_mappings_raises(self):
        """GIVEN: Metadata without provider mappings WHEN: creating THEN: Pydantic should raise error"""
        # Empty providerMappings is caught by Pydantic during model creation, not registration
        from pydantic import ValidationError
        
        with self.assertRaises(ValidationError):
            bad_metadata = InstrumentMetadata(
                canonicalSymbol="BADXXX",
                instrumentType=InstrumentType.SPOT,
                assetClass=AssetClass.PRECIOUS_METALS,
                exchange=Exchange.FOREX_OTC,
                currency="USD",
                pipSize=0.001,
                precision=3,
                displayName="Bad",
                providerMappings={},  # Empty - should fail Pydantic validation
                expectedInstrumentTypes=[InstrumentType.SPOT],
                addedAt=datetime.now(timezone.utc),
                lastUpdatedAt=datetime.now(timezone.utc),
            )


class TestGetInstrument(unittest.TestCase):
    """Tests for get_instrument() method (canonical lookup)."""
    
    def setUp(self):
        """Create empty registry for each test."""
        self.registry = CanonicalInstrumentRegistry()
    
    def test_get_existing_instrument(self):
        """GIVEN: Registered instrument WHEN: getting by canonical symbol THEN: should return metadata"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        retrieved = self.registry.get_instrument("XAUUSD")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.canonicalSymbol, "XAUUSD")
        self.assertEqual(retrieved.instrumentType, InstrumentType.SPOT)
    
    def test_get_nonexistent_instrument(self):
        """GIVEN: Empty registry WHEN: getting non-existent instrument THEN: should return None"""
        result = self.registry.get_instrument("NONEXISTENT")
        self.assertIsNone(result)
    
    def test_get_is_case_sensitive(self):
        """GIVEN: Registered instrument WHEN: getting with wrong case THEN: should return None"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        # Exact match works
        self.assertIsNotNone(self.registry.get_instrument("XAUUSD"))
        
        # Case variations don't work
        self.assertIsNone(self.registry.get_instrument("xauusd"))
        self.assertIsNone(self.registry.get_instrument("XauUsd"))
    
    def test_get_returns_correct_metadata(self):
        """GIVEN: Multiple registered instruments WHEN: getting each THEN: should return correct metadata"""
        xauusd = create_xauusd_metadata()
        gbpusd = create_gbpusd_metadata()
        self.registry.register_instrument(xauusd)
        self.registry.register_instrument(gbpusd)
        
        xau = self.registry.get_instrument("XAUUSD")
        gbp = self.registry.get_instrument("GBPUSD")
        
        self.assertEqual(xau.assetClass, AssetClass.PRECIOUS_METALS)
        self.assertEqual(gbp.assetClass, AssetClass.CURRENCIES)
        self.assertEqual(xau.pipSize, 0.001)
        self.assertEqual(gbp.pipSize, 0.0001)


class TestGetByProviderSymbol(unittest.TestCase):
    """Tests for get_by_provider_symbol() method (reverse lookup)."""
    
    def setUp(self):
        """Create empty registry for each test."""
        self.registry = CanonicalInstrumentRegistry()
    
    def test_reverse_lookup_single_provider(self):
        """GIVEN: Registered instrument WHEN: reverse lookup by provider symbol THEN: should return metadata"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        result = self.registry.get_by_provider_symbol("twelve_data", "XAU/USD")
        self.assertIsNotNone(result)
        self.assertEqual(result.canonicalSymbol, "XAUUSD")
    
    def test_reverse_lookup_all_providers(self):
        """GIVEN: Registered instrument WHEN: reverse lookup for all providers THEN: all should work"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        providers = [
            ("twelve_data", "XAU/USD"),
            ("alpha_vantage", "XAU"),
            ("mock_price", "XAUUSD"),
        ]
        
        for provider_id, provider_symbol in providers:
            result = self.registry.get_by_provider_symbol(provider_id, provider_symbol)
            self.assertIsNotNone(result, f"Failed to lookup {provider_symbol} from {provider_id}")
            self.assertEqual(result.canonicalSymbol, "XAUUSD")
    
    def test_reverse_lookup_nonexistent_provider(self):
        """GIVEN: Registered instrument WHEN: reverse lookup for non-existent provider THEN: should return None"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        result = self.registry.get_by_provider_symbol("nonexistent_provider", "FAKE")
        self.assertIsNone(result)
    
    def test_reverse_lookup_nonexistent_symbol(self):
        """GIVEN: Registered instrument WHEN: reverse lookup for non-existent symbol THEN: should return None"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        result = self.registry.get_by_provider_symbol("twelve_data", "FAKE/SYMBOL")
        self.assertIsNone(result)
    
    def test_reverse_lookup_correct_instrument_returned(self):
        """GIVEN: Multiple instruments WHEN: reverse lookup for each THEN: should return correct one"""
        xauusd = create_xauusd_metadata()
        gbpusd = create_gbpusd_metadata()
        self.registry.register_instrument(xauusd)
        self.registry.register_instrument(gbpusd)
        
        xau_result = self.registry.get_by_provider_symbol("twelve_data", "XAU/USD")
        gbp_result = self.registry.get_by_provider_symbol("twelve_data", "GBP/USD")
        
        self.assertEqual(xau_result.canonicalSymbol, "XAUUSD")
        self.assertEqual(gbp_result.canonicalSymbol, "GBPUSD")
        self.assertNotEqual(xau_result, gbp_result)


class TestGetProviderSymbol(unittest.TestCase):
    """Tests for get_provider_symbol() method."""
    
    def setUp(self):
        """Create empty registry for each test."""
        self.registry = CanonicalInstrumentRegistry()
    
    def test_get_provider_symbol_forward_lookup(self):
        """GIVEN: Registered instrument WHEN: getting provider symbol THEN: should return correct symbol"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        result = self.registry.get_provider_symbol("XAUUSD", "twelve_data")
        self.assertEqual(result, "XAU/USD")
    
    def test_get_provider_symbol_all_providers(self):
        """GIVEN: Registered instrument WHEN: getting provider symbols for all providers THEN: all should work"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        expected = {
            "twelve_data": "XAU/USD",
            "alpha_vantage": "XAU",
            "mock_price": "XAUUSD",
        }
        
        for provider_id, expected_symbol in expected.items():
            result = self.registry.get_provider_symbol("XAUUSD", provider_id)
            self.assertEqual(result, expected_symbol)
    
    def test_get_provider_symbol_nonexistent_canonical(self):
        """GIVEN: Empty registry WHEN: getting provider symbol for non-existent canonical THEN: should return None"""
        result = self.registry.get_provider_symbol("FAKE", "twelve_data")
        self.assertIsNone(result)
    
    def test_get_provider_symbol_nonexistent_provider(self):
        """GIVEN: Registered instrument WHEN: getting non-existent provider symbol THEN: should return None"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        result = self.registry.get_provider_symbol("XAUUSD", "fake_provider")
        self.assertIsNone(result)
    
    def test_get_provider_symbol_multiple_instruments(self):
        """GIVEN: Multiple instruments WHEN: getting provider symbols THEN: should return correct ones"""
        xauusd = create_xauusd_metadata()
        gbpusd = create_gbpusd_metadata()
        self.registry.register_instrument(xauusd)
        self.registry.register_instrument(gbpusd)
        
        xau_symbol = self.registry.get_provider_symbol("XAUUSD", "twelve_data")
        gbp_symbol = self.registry.get_provider_symbol("GBPUSD", "twelve_data")
        
        self.assertEqual(xau_symbol, "XAU/USD")
        self.assertEqual(gbp_symbol, "GBP/USD")
        self.assertNotEqual(xau_symbol, gbp_symbol)


class TestAllInstruments(unittest.TestCase):
    """Tests for all_instruments() method."""
    
    def setUp(self):
        """Create empty registry for each test."""
        self.registry = CanonicalInstrumentRegistry()
    
    def test_all_instruments_empty_registry(self):
        """GIVEN: Empty registry WHEN: getting all instruments THEN: should return empty list"""
        result = self.registry.all_instruments()
        self.assertEqual(result, [])
    
    def test_all_instruments_single_instrument(self):
        """GIVEN: Registry with one instrument WHEN: getting all THEN: should return one"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        result = self.registry.all_instruments()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].canonicalSymbol, "XAUUSD")
    
    def test_all_instruments_multiple_instruments(self):
        """GIVEN: Registry with multiple instruments WHEN: getting all THEN: should return all"""
        xauusd = create_xauusd_metadata()
        gbpusd = create_gbpusd_metadata()
        btcusd = create_btcusd_metadata()
        self.registry.register_instrument(xauusd)
        self.registry.register_instrument(gbpusd)
        self.registry.register_instrument(btcusd)
        
        result = self.registry.all_instruments()
        self.assertEqual(len(result), 3)
        
        symbols = {inst.canonicalSymbol for inst in result}
        self.assertEqual(symbols, {"XAUUSD", "GBPUSD", "BTCUSD"})
    
    def test_all_instruments_returns_list(self):
        """GIVEN: Registry with instrument WHEN: getting all THEN: should return list"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        result = self.registry.all_instruments()
        self.assertIsInstance(result, list)
    
    def test_all_instruments_includes_metadata(self):
        """GIVEN: Registry with instrument WHEN: getting all THEN: should have complete metadata"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        result = self.registry.all_instruments()
        self.assertEqual(len(result), 1)
        
        inst = result[0]
        self.assertEqual(inst.canonicalSymbol, "XAUUSD")
        self.assertEqual(inst.instrumentType, InstrumentType.SPOT)
        self.assertEqual(inst.assetClass, AssetClass.PRECIOUS_METALS)
        self.assertIn("twelve_data", inst.providerMappings)


class TestNormalizeProviderId(unittest.TestCase):
    """Tests for _normalize_provider_id() method."""
    
    def setUp(self):
        """Create registry for each test."""
        self.registry = CanonicalInstrumentRegistry()
    
    def test_normalize_lowercase(self):
        """GIVEN: Uppercase provider ID WHEN: normalizing THEN: should be lowercased"""
        result = self.registry._normalize_provider_id("TWELVE_DATA")
        self.assertEqual(result, "twelve_data")
    
    def test_normalize_hyphens_to_underscores(self):
        """GIVEN: Provider ID with hyphens WHEN: normalizing THEN: should use underscores"""
        result = self.registry._normalize_provider_id("twelve-data")
        self.assertEqual(result, "twelve_data")
    
    def test_normalize_removes_version_suffix(self):
        """GIVEN: Provider ID with version suffix WHEN: normalizing THEN: should remove version"""
        result = self.registry._normalize_provider_id("twelve_data_v1")
        self.assertEqual(result, "twelve_data")
        
        result = self.registry._normalize_provider_id("twelve_data_v2")
        self.assertEqual(result, "twelve_data")
    
    def test_normalize_already_normalized(self):
        """GIVEN: Already normalized ID WHEN: normalizing THEN: should remain unchanged"""
        result = self.registry._normalize_provider_id("twelve_data")
        self.assertEqual(result, "twelve_data")


class TestRebuildIndices(unittest.TestCase):
    """Tests for _rebuild_indices() method."""
    
    def setUp(self):
        """Create registry for each test."""
        self.registry = CanonicalInstrumentRegistry()
    
    def test_rebuild_indices_creates_provider_index(self):
        """GIVEN: Registered instrument WHEN: indices rebuilt THEN: provider index should exist"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        self.assertIn("twelve_data", self.registry._provider_index)
        self.assertIn("alpha_vantage", self.registry._provider_index)
        self.assertIn("mock_price", self.registry._provider_index)
    
    def test_rebuild_indices_creates_reverse_mappings(self):
        """GIVEN: Registered instrument WHEN: indices rebuilt THEN: reverse mappings should be correct"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        self.assertEqual(self.registry._provider_index["twelve_data"]["XAU/USD"], "XAUUSD")
        self.assertEqual(self.registry._provider_index["alpha_vantage"]["XAU"], "XAUUSD")
        self.assertEqual(self.registry._provider_index["mock_price"]["XAUUSD"], "XAUUSD")
    
    def test_rebuild_indices_consistency(self):
        """GIVEN: Multiple instruments WHEN: indices rebuilt THEN: indices should be consistent"""
        xauusd = create_xauusd_metadata()
        gbpusd = create_gbpusd_metadata()
        self.registry.register_instrument(xauusd)
        self.registry.register_instrument(gbpusd)
        
        # Get total provider mappings
        total_mappings = sum(
            len(metadata.providerMappings)
            for metadata in self.registry._registry.values()
        )
        
        # Count total indexed mappings
        indexed_count = sum(
            len(provider_map)
            for provider_map in self.registry._provider_index.values()
        )
        
        self.assertEqual(total_mappings, indexed_count)


class TestPerformance(unittest.TestCase):
    """Tests for performance characteristics."""
    
    def setUp(self):
        """Create registry with sample data for each test."""
        self.registry = CanonicalInstrumentRegistry()
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
    
    def test_get_instrument_performance(self):
        """GIVEN: Registered instrument WHEN: doing many lookups THEN: should be very fast"""
        start = time.perf_counter()
        for _ in range(10000):
            self.registry.get_instrument("XAUUSD")
        elapsed = time.perf_counter() - start
        
        # Should be extremely fast (< 20ms for 10000 operations - allows for system variation)
        self.assertLess(elapsed, 0.02, f"Lookup too slow: {elapsed}s for 10000 operations")
    
    def test_reverse_lookup_performance(self):
        """GIVEN: Registered instrument WHEN: doing many reverse lookups THEN: should be very fast"""
        start = time.perf_counter()
        for _ in range(10000):
            self.registry.get_by_provider_symbol("twelve_data", "XAU/USD")
        elapsed = time.perf_counter() - start
        
        # Should be extremely fast (< 30ms for 10000 operations - allows for system variation)
        self.assertLess(elapsed, 0.03, f"Reverse lookup too slow: {elapsed}s for 10000 operations")
    
    def test_provider_symbol_lookup_performance(self):
        """GIVEN: Registered instrument WHEN: doing many provider symbol lookups THEN: should be very fast"""
        start = time.perf_counter()
        for _ in range(10000):
            self.registry.get_provider_symbol("XAUUSD", "twelve_data")
        elapsed = time.perf_counter() - start
        
        # Should be extremely fast (< 20ms for 10000 operations - allows for system variation)
        self.assertLess(elapsed, 0.02, f"Provider symbol lookup too slow: {elapsed}s for 10000 operations")


class TestRoundTripConsistency(unittest.TestCase):
    """Tests for round-trip consistency (canonical → provider → canonical)."""
    
    def setUp(self):
        """Create registry for each test."""
        self.registry = CanonicalInstrumentRegistry()
    
    def test_round_trip_twelve_data(self):
        """GIVEN: Registered instrument WHEN: round-trip lookup THEN: should return original"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        canonical = "XAUUSD"
        provider_symbol = self.registry.get_provider_symbol(canonical, "twelve_data")
        self.assertEqual(provider_symbol, "XAU/USD")
        
        retrieved = self.registry.get_by_provider_symbol("twelve_data", provider_symbol)
        self.assertEqual(retrieved.canonicalSymbol, canonical)
    
    def test_round_trip_alpha_vantage(self):
        """GIVEN: Registered instrument WHEN: round-trip lookup for Alpha Vantage THEN: should return original"""
        xauusd = create_xauusd_metadata()
        self.registry.register_instrument(xauusd)
        
        canonical = "XAUUSD"
        provider_symbol = self.registry.get_provider_symbol(canonical, "alpha_vantage")
        self.assertEqual(provider_symbol, "XAU")
        
        retrieved = self.registry.get_by_provider_symbol("alpha_vantage", provider_symbol)
        self.assertEqual(retrieved.canonicalSymbol, canonical)
    
    def test_round_trip_all_instruments_all_providers(self):
        """GIVEN: Multiple instruments WHEN: round-trip for all THEN: all should work"""
        all_metadata = [create_xauusd_metadata(), create_gbpusd_metadata(), create_btcusd_metadata()]
        for metadata in all_metadata:
            self.registry.register_instrument(metadata)
        
        for metadata in all_metadata:
            canonical = metadata.canonicalSymbol
            for provider_id in metadata.providerMappings.keys():
                provider_symbol = self.registry.get_provider_symbol(canonical, provider_id)
                self.assertIsNotNone(provider_symbol)
                
                retrieved = self.registry.get_by_provider_symbol(provider_id, provider_symbol)
                self.assertIsNotNone(retrieved)
                self.assertEqual(retrieved.canonicalSymbol, canonical)


if __name__ == "__main__":
    unittest.main()
