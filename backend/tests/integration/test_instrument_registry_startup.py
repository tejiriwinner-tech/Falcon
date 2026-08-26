"""
Integration tests for CanonicalInstrumentRegistry startup and population.

Tests that verify the registry is properly initialized at application startup
with all 8 primary instruments registered and queryable through various lookup paths.

**Validates: Requirement 1 (Registry), Requirement 8-9 (Provider Mappings, Type Correctness), Requirement 15 (Registry Initialization)**
"""

import unittest
from app.core.instruments import instrument_registry
from app.schemas.instrument_models import (
    InstrumentType,
    AssetClass,
    Exchange,
)


class TestRegistryPopulationAtStartup(unittest.TestCase):
    """Integration tests for registry initialization at startup."""
    
    def test_all_8_instruments_registered(self):
        """GIVEN: Application startup WHEN: registry initialized THEN: should have all 8 instruments"""
        instruments = instrument_registry.all_instruments()
        
        self.assertEqual(len(instruments), 8)
        symbols = {inst.canonicalSymbol for inst in instruments}
        expected_symbols = {"XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30", "BTCUSD", "ETHUSD"}
        self.assertEqual(symbols, expected_symbols)
    
    def test_xauusd_correctly_registered(self):
        """GIVEN: Startup complete WHEN: querying XAUUSD THEN: should have correct metadata"""
        inst = instrument_registry.get_instrument("XAUUSD")
        
        self.assertIsNotNone(inst)
        self.assertEqual(inst.canonicalSymbol, "XAUUSD")
        self.assertEqual(inst.instrumentType, InstrumentType.SPOT)
        self.assertEqual(inst.assetClass, AssetClass.PRECIOUS_METALS)
        self.assertEqual(inst.exchange, Exchange.FOREX_OTC)
        self.assertEqual(inst.currency, "USD")
        self.assertEqual(inst.pipSize, 0.001)
        self.assertEqual(inst.displayName, "Gold (Spot)")
    
    def test_xauusd_provider_mappings(self):
        """GIVEN: Startup complete WHEN: checking XAUUSD provider mappings THEN: should have twelve_data, yahoo_finance, and mock_price"""
        inst = instrument_registry.get_instrument("XAUUSD")
        
        self.assertIn("twelve_data", inst.providerMappings)
        self.assertIn("yahoo_finance", inst.providerMappings)
        self.assertIn("mock_price", inst.providerMappings)
        self.assertNotIn("finnhub", inst.providerMappings)  # Finnhub removed
        
        self.assertEqual(inst.providerMappings["twelve_data"], "XAU/USD")
        self.assertEqual(inst.providerMappings["yahoo_finance"], "GC=F")
        self.assertEqual(inst.providerMappings["mock_price"], "XAUUSD")
    
    def test_gbpusd_correctly_registered(self):
        """GIVEN: Startup complete WHEN: querying GBPUSD THEN: should have correct metadata"""
        inst = instrument_registry.get_instrument("GBPUSD")
        
        self.assertIsNotNone(inst)
        self.assertEqual(inst.instrumentType, InstrumentType.FOREX)
        self.assertEqual(inst.assetClass, AssetClass.CURRENCIES)
        self.assertEqual(inst.exchange, Exchange.FOREX_OTC)
        self.assertEqual(inst.pipSize, 0.0001)
    
    def test_gbpusd_provider_mappings(self):
        """GIVEN: Startup complete WHEN: checking GBPUSD provider mappings THEN: should have all providers"""
        inst = instrument_registry.get_instrument("GBPUSD")
        
        self.assertEqual(inst.providerMappings["twelve_data"], "GBP/USD")
        self.assertEqual(inst.providerMappings["yahoo_finance"], "GBPUSD=X")
        self.assertEqual(inst.providerMappings["mock_price"], "GBPUSD")
        self.assertNotIn("finnhub", inst.providerMappings)  # Finnhub removed
    
    def test_eurusd_correctly_registered(self):
        """GIVEN: Startup complete WHEN: querying EURUSD THEN: should have correct metadata"""
        inst = instrument_registry.get_instrument("EURUSD")
        
        self.assertIsNotNone(inst)
        self.assertEqual(inst.instrumentType, InstrumentType.FOREX)
        self.assertEqual(inst.assetClass, AssetClass.CURRENCIES)
    
    def test_usdjpy_correctly_registered(self):
        """GIVEN: Startup complete WHEN: querying USDJPY THEN: should have correct metadata"""
        inst = instrument_registry.get_instrument("USDJPY")
        
        self.assertIsNotNone(inst)
        self.assertEqual(inst.instrumentType, InstrumentType.FOREX)
        self.assertEqual(inst.currency, "JPY")
        self.assertEqual(inst.pipSize, 0.01)
    
    def test_nas100_correctly_registered(self):
        """GIVEN: Startup complete WHEN: querying NAS100 THEN: should have correct metadata"""
        inst = instrument_registry.get_instrument("NAS100")
        
        self.assertIsNotNone(inst)
        self.assertEqual(inst.instrumentType, InstrumentType.INDEX)
        self.assertEqual(inst.assetClass, AssetClass.INDICES)
        self.assertEqual(inst.exchange, Exchange.NASDAQ)
        self.assertEqual(inst.displayName, "NASDAQ-100")
    
    def test_nas100_provider_mappings(self):
        """GIVEN: Startup complete WHEN: checking NAS100 provider mappings THEN: should have all providers"""
        inst = instrument_registry.get_instrument("NAS100")
        
        self.assertEqual(inst.providerMappings["twelve_data"], "NAS100")
        self.assertEqual(inst.providerMappings["yahoo_finance"], "^NDX")
        self.assertEqual(inst.providerMappings["mock_price"], "NAS100")
        self.assertNotIn("finnhub", inst.providerMappings)  # Finnhub removed
    
    def test_us30_correctly_registered(self):
        """GIVEN: Startup complete WHEN: querying US30 THEN: should have correct metadata"""
        inst = instrument_registry.get_instrument("US30")
        
        self.assertIsNotNone(inst)
        self.assertEqual(inst.instrumentType, InstrumentType.INDEX)
        self.assertEqual(inst.assetClass, AssetClass.INDICES)
        self.assertEqual(inst.exchange, Exchange.NYSE)
        self.assertEqual(inst.displayName, "Dow Jones 30")
    
    def test_us30_provider_mappings(self):
        """GIVEN: Startup complete WHEN: checking US30 provider mappings THEN: should have all providers"""
        inst = instrument_registry.get_instrument("US30")
        
        self.assertEqual(inst.providerMappings["twelve_data"], "DJI")
        self.assertEqual(inst.providerMappings["yahoo_finance"], "^DJI")
        self.assertEqual(inst.providerMappings["mock_price"], "US30")
        self.assertNotIn("finnhub", inst.providerMappings)  # Finnhub removed
    
    def test_btcusd_correctly_registered(self):
        """GIVEN: Startup complete WHEN: querying BTCUSD THEN: should have correct metadata"""
        inst = instrument_registry.get_instrument("BTCUSD")
        
        self.assertIsNotNone(inst)
        self.assertEqual(inst.instrumentType, InstrumentType.CRYPTO)
        self.assertEqual(inst.assetClass, AssetClass.CRYPTOCURRENCIES)
        self.assertEqual(inst.exchange, Exchange.CRYPTO_SPOT)
        self.assertEqual(inst.displayName, "Bitcoin")
    
    def test_btcusd_provider_mappings(self):
        """GIVEN: Startup complete WHEN: checking BTCUSD provider mappings THEN: should have all providers"""
        inst = instrument_registry.get_instrument("BTCUSD")
        
        self.assertEqual(inst.providerMappings["twelve_data"], "BTC/USD")
        self.assertEqual(inst.providerMappings["yahoo_finance"], "BTC-USD")
        self.assertEqual(inst.providerMappings["mock_price"], "BTCUSD")
        self.assertNotIn("finnhub", inst.providerMappings)  # Finnhub removed
    
    def test_ethusd_correctly_registered(self):
        """GIVEN: Startup complete WHEN: querying ETHUSD THEN: should have correct metadata"""
        inst = instrument_registry.get_instrument("ETHUSD")
        
        self.assertIsNotNone(inst)
        self.assertEqual(inst.instrumentType, InstrumentType.CRYPTO)
        self.assertEqual(inst.assetClass, AssetClass.CRYPTOCURRENCIES)
        self.assertEqual(inst.exchange, Exchange.CRYPTO_SPOT)
        self.assertEqual(inst.displayName, "Ethereum")
    
    def test_ethusd_provider_mappings(self):
        """GIVEN: Startup complete WHEN: checking ETHUSD provider mappings THEN: should have all providers"""
        inst = instrument_registry.get_instrument("ETHUSD")
        
        self.assertEqual(inst.providerMappings["twelve_data"], "ETH/USD")
        self.assertEqual(inst.providerMappings["yahoo_finance"], "ETH-USD")
        self.assertEqual(inst.providerMappings["mock_price"], "ETHUSD")
        self.assertNotIn("finnhub", inst.providerMappings)  # Finnhub removed


class TestRegistryReverseLookupsAtStartup(unittest.TestCase):
    """Integration tests for reverse lookups of all registered instruments."""
    
    def test_reverse_lookup_xauusd_twelve_data(self):
        """GIVEN: Registered XAUUSD WHEN: reverse lookup via twelve_data THEN: should work"""
        inst = instrument_registry.get_by_provider_symbol("twelve_data", "XAU/USD")
        
        self.assertIsNotNone(inst)
        self.assertEqual(inst.canonicalSymbol, "XAUUSD")
    
    def test_reverse_lookup_xauusd_yahoo_finance(self):
        """GIVEN: Registered XAUUSD WHEN: reverse lookup via yahoo_finance THEN: should work"""
        inst = instrument_registry.get_by_provider_symbol("yahoo_finance", "GC=F")
        
        self.assertIsNotNone(inst)
        self.assertEqual(inst.canonicalSymbol, "XAUUSD")
    
    def test_reverse_lookup_xauusd_mock_price(self):
        """GIVEN: Registered XAUUSD WHEN: reverse lookup via mock_price THEN: should work"""
        inst = instrument_registry.get_by_provider_symbol("mock_price", "XAUUSD")
        
        self.assertIsNotNone(inst)
        self.assertEqual(inst.canonicalSymbol, "XAUUSD")
    
    def test_reverse_lookup_xauusd_finnhub_removed(self):
        """GIVEN: Finnhub removed WHEN: reverse lookup via finnhub THEN: should return None"""
        inst = instrument_registry.get_by_provider_symbol("finnhub", "OANDA:XAU_USD")
        
        # Finnhub removed, so this should return None
        self.assertIsNone(inst)
    
    def test_reverse_lookup_gbpusd_all_providers(self):
        """GIVEN: Registered GBPUSD WHEN: reverse lookup for all providers THEN: all should work"""
        mappings = [
            ("twelve_data", "GBP/USD"),
            ("yahoo_finance", "GBPUSD=X"),
            ("mock_price", "GBPUSD"),
        ]
        
        for provider_id, provider_symbol in mappings:
            inst = instrument_registry.get_by_provider_symbol(provider_id, provider_symbol)
            self.assertIsNotNone(inst, f"Failed to lookup {provider_symbol} from {provider_id}")
            self.assertEqual(inst.canonicalSymbol, "GBPUSD")
    
    def test_reverse_lookup_nas100_all_providers(self):
        """GIVEN: Registered NAS100 WHEN: reverse lookup for all providers THEN: all should work"""
        mappings = [
            ("twelve_data", "NAS100"),
            ("yahoo_finance", "^NDX"),
            ("mock_price", "NAS100"),
        ]
        
        for provider_id, provider_symbol in mappings:
            inst = instrument_registry.get_by_provider_symbol(provider_id, provider_symbol)
            self.assertIsNotNone(inst)
            self.assertEqual(inst.canonicalSymbol, "NAS100")
    
    def test_reverse_lookup_all_instruments_all_providers(self):
        """GIVEN: All registered instruments WHEN: reverse lookup for each provider mapping THEN: all should work"""
        for inst in instrument_registry.all_instruments():
            canonical = inst.canonicalSymbol
            for provider_id, provider_symbol in inst.providerMappings.items():
                retrieved = instrument_registry.get_by_provider_symbol(provider_id, provider_symbol)
                self.assertIsNotNone(
                    retrieved,
                    f"Failed reverse lookup: {provider_id}:{provider_symbol} for {canonical}"
                )
                self.assertEqual(
                    retrieved.canonicalSymbol,
                    canonical,
                    f"Reverse lookup returned wrong canonical: {retrieved.canonicalSymbol} instead of {canonical}"
                )


class TestRegistryProviderSymbolLookupAtStartup(unittest.TestCase):
    """Integration tests for forward (canonical → provider) lookups."""
    
    def test_forward_lookup_xauusd_all_providers(self):
        """GIVEN: Registered XAUUSD WHEN: forward lookup for all providers THEN: all should work"""
        expected = {
            "twelve_data": "XAU/USD",
            "yahoo_finance": "GC=F",
            "mock_price": "XAUUSD",
        }
        
        for provider_id, expected_symbol in expected.items():
            symbol = instrument_registry.get_provider_symbol("XAUUSD", provider_id)
            self.assertEqual(symbol, expected_symbol)
        
        # Verify Finnhub is NOT available for XAUUSD (removed)
        finnhub_symbol = instrument_registry.get_provider_symbol("XAUUSD", "finnhub")
        self.assertIsNone(finnhub_symbol)
    
    def test_forward_lookup_all_instruments_all_providers(self):
        """GIVEN: All registered instruments WHEN: forward lookup for each provider THEN: all should work"""
        for inst in instrument_registry.all_instruments():
            canonical = inst.canonicalSymbol
            for provider_id, expected_symbol in inst.providerMappings.items():
                symbol = instrument_registry.get_provider_symbol(canonical, provider_id)
                self.assertIsNotNone(symbol, f"Forward lookup failed for {canonical} @ {provider_id}")
                self.assertEqual(symbol, expected_symbol)


class TestRegistryRoundTripConsistencyAtStartup(unittest.TestCase):
    """Integration tests verifying round-trip consistency (canonical → provider → canonical)."""
    
    def test_round_trip_xauusd_all_providers(self):
        """GIVEN: Registered XAUUSD WHEN: round-trip for all providers THEN: should be consistent"""
        canonical = "XAUUSD"
        
        for provider_id in ["twelve_data", "yahoo_finance", "mock_price"]:
            # Forward: canonical → provider
            provider_symbol = instrument_registry.get_provider_symbol(canonical, provider_id)
            self.assertIsNotNone(provider_symbol)
            
            # Reverse: provider → canonical
            retrieved = instrument_registry.get_by_provider_symbol(provider_id, provider_symbol)
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.canonicalSymbol, canonical)
    
    def test_round_trip_all_instruments_all_providers(self):
        """GIVEN: All instruments WHEN: round-trip for each provider THEN: all should be consistent"""
        for inst in instrument_registry.all_instruments():
            canonical = inst.canonicalSymbol
            for provider_id in inst.providerMappings.keys():
                # Forward
                provider_symbol = instrument_registry.get_provider_symbol(canonical, provider_id)
                self.assertIsNotNone(provider_symbol)
                
                # Reverse
                retrieved = instrument_registry.get_by_provider_symbol(provider_id, provider_symbol)
                self.assertIsNotNone(retrieved)
                self.assertEqual(retrieved.canonicalSymbol, canonical)


class TestRegistryIndexConsistencyAtStartup(unittest.TestCase):
    """Integration tests verifying internal registry indices are consistent."""
    
    def test_provider_index_populated(self):
        """GIVEN: Startup complete WHEN: checking provider index THEN: should be populated for all providers"""
        # Should have at least our providers (twelve_data, yahoo_finance, mock_price, alpaca optional)
        providers_in_index = set(instrument_registry._provider_index.keys())
        
        # Normalize provider names
        expected_providers = {"twelve_data", "yahoo_finance", "mock_price"}
        for expected in expected_providers:
            normalized = instrument_registry._normalize_provider_id(expected)
            self.assertIn(normalized, providers_in_index)
    
    def test_symbol_reverse_index_populated(self):
        """GIVEN: Startup complete WHEN: checking reverse index THEN: should be populated"""
        # Should have entries for all provider symbols via _provider_index
        providers_in_index = instrument_registry._provider_index
        
        # Should have at least 3 providers represented (twelve_data, yahoo_finance, mock_price)
        self.assertGreaterEqual(len(providers_in_index), 3)
    
    def test_total_provider_mappings_count(self):
        """GIVEN: All instruments WHEN: counting provider mappings THEN: should be correct total"""
        total_mappings = sum(
            len(inst.providerMappings)
            for inst in instrument_registry.all_instruments()
        )
        
        # XAUUSD: 3 providers (twelve_data, yahoo_finance, mock_price)
        # GBPUSD: 3 providers (twelve_data, yahoo_finance, mock_price)
        # EURUSD: 3 providers (twelve_data, yahoo_finance, mock_price)
        # USDJPY: 3 providers (twelve_data, yahoo_finance, mock_price)
        # NAS100: 3 providers (twelve_data, yahoo_finance, mock_price)
        # US30: 3 providers (twelve_data, yahoo_finance, mock_price)
        # BTCUSD: 3 providers (twelve_data, yahoo_finance, mock_price)
        # ETHUSD: 3 providers (twelve_data, yahoo_finance, mock_price)
        # Total: 3×8 = 24 base, plus 6 if Alpaca is enabled (total 30)
        self.assertIn(total_mappings, [24, 30])
    
    def test_index_consistency_count(self):
        """GIVEN: All instruments registered WHEN: checking index consistency THEN: count should match"""
        total_registry_mappings = sum(
            len(inst.providerMappings)
            for inst in instrument_registry.all_instruments()
        )
        
        total_indexed_mappings = sum(
            len(provider_map)
            for provider_map in instrument_registry._provider_index.values()
        )
        
        self.assertEqual(total_registry_mappings, total_indexed_mappings)


class TestRegistryTypeCorrectionAtStartup(unittest.TestCase):
    """Integration tests verifying correct instrument type classification."""
    
    def test_precious_metals_correct_type(self):
        """GIVEN: Startup complete WHEN: checking XAUUSD THEN: should be SPOT precious metal"""
        inst = instrument_registry.get_instrument("XAUUSD")
        
        self.assertEqual(inst.instrumentType, InstrumentType.SPOT)
        self.assertEqual(inst.assetClass, AssetClass.PRECIOUS_METALS)
        self.assertIn(InstrumentType.SPOT, inst.expectedInstrumentTypes)
    
    def test_forex_pairs_correct_type(self):
        """GIVEN: Startup complete WHEN: checking forex pairs THEN: should all be FOREX"""
        forex_pairs = ["GBPUSD", "EURUSD", "USDJPY"]
        
        for symbol in forex_pairs:
            inst = instrument_registry.get_instrument(symbol)
            self.assertEqual(inst.instrumentType, InstrumentType.FOREX)
            self.assertEqual(inst.assetClass, AssetClass.CURRENCIES)
            self.assertIn(InstrumentType.FOREX, inst.expectedInstrumentTypes)
    
    def test_indices_correct_type(self):
        """GIVEN: Startup complete WHEN: checking indices THEN: should all be INDEX"""
        indices = ["NAS100", "US30"]
        
        for symbol in indices:
            inst = instrument_registry.get_instrument(symbol)
            self.assertEqual(inst.instrumentType, InstrumentType.INDEX)
            self.assertEqual(inst.assetClass, AssetClass.INDICES)
            self.assertIn(InstrumentType.INDEX, inst.expectedInstrumentTypes)
    
    def test_cryptocurrencies_correct_type(self):
        """GIVEN: Startup complete WHEN: checking cryptos THEN: should all be CRYPTO"""
        cryptos = ["BTCUSD", "ETHUSD"]
        
        for symbol in cryptos:
            inst = instrument_registry.get_instrument(symbol)
            self.assertEqual(inst.instrumentType, InstrumentType.CRYPTO)
            self.assertEqual(inst.assetClass, AssetClass.CRYPTOCURRENCIES)
            self.assertEqual(inst.exchange, Exchange.CRYPTO_SPOT)
            self.assertIn(InstrumentType.CRYPTO, inst.expectedInstrumentTypes)


if __name__ == "__main__":
    unittest.main()