"""
Integration Tests for Tasks 9.5-9.10: Runtime Instruments Endpoint

Tests the GET /api/v1/runtime/instruments endpoint implementation
"""

from app.core.instruments import instrument_registry


def test_all_8_instruments_registered():
    """Validate all 8 primary instruments are registered."""
    all_instruments = instrument_registry.all_instruments()
    assert len(all_instruments) == 8
    canonical_symbols = {i.canonicalSymbol for i in all_instruments}
    expected = {"XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30", "BTCUSD", "ETHUSD"}
    assert canonical_symbols == expected
    print("[PASS] All 8 instruments registered")


def test_provider_coverage_complete():
    """Validate each instrument has provider mappings."""
    all_instruments = instrument_registry.all_instruments()
    required_providers = {"twelve_data", "yahoo_finance", "mock_price"}
    
    for instrument in all_instruments:
        has_providers = set(instrument.providerMappings.keys())
        assert required_providers.issubset(has_providers), \
            f"{instrument.canonicalSymbol} missing providers"
    
    print("[PASS] All instruments have complete provider coverage")


def test_instrument_metadata_correct():
    """Validate instruments have correct metadata."""
    test_cases = {
        "XAUUSD": ("SPOT", "PRECIOUS_METALS", 0.001, 3),
        "GBPUSD": ("FOREX", "CURRENCIES", 0.0001, 4),
        "EURUSD": ("FOREX", "CURRENCIES", 0.0001, 4),
        "USDJPY": ("FOREX", "CURRENCIES", 0.01, 2),
        "NAS100": ("INDEX", "INDICES", 0.01, 2),
        "US30": ("INDEX", "INDICES", 0.01, 2),
        "BTCUSD": ("CRYPTO", "CRYPTOCURRENCIES", 0.01, 2),
        "ETHUSD": ("CRYPTO", "CRYPTOCURRENCIES", 0.01, 2),
    }
    
    for canonical, (exp_type, exp_class, exp_pip, exp_prec) in test_cases.items():
        instrument = instrument_registry.get_instrument(canonical)
        assert instrument is not None
        assert str(instrument.instrumentType).split(".")[-1] == exp_type
        assert str(instrument.assetClass).split(".")[-1] == exp_class
        assert instrument.pipSize == exp_pip
        assert instrument.precision == exp_prec
    
    print("[PASS] All instruments have correct metadata")


def test_xauusd_provider_symbols():
    """Validate XAUUSD has correct provider symbols."""
    xauusd = instrument_registry.get_instrument("XAUUSD")
    assert xauusd is not None
    
    assert xauusd.providerMappings["twelve_data"] == "XAU/USD"
    assert xauusd.providerMappings["yahoo_finance"] == "GC=F"
    assert xauusd.providerMappings["mock_price"] == "XAUUSD"
    
    print("[PASS] XAUUSD provider symbols correct")


def test_reverse_lookup_consistency():
    """Test reverse lookup for all instruments."""
    all_instruments = instrument_registry.all_instruments()
    
    for instrument in all_instruments:
        canonical = instrument.canonicalSymbol
        
        for provider_id, provider_symbol in instrument.providerMappings.items():
            # Forward lookup
            retrieved = instrument_registry.get_provider_symbol(canonical, provider_id)
            assert retrieved == provider_symbol
            
            # Reverse lookup
            reversed_instr = instrument_registry.get_by_provider_symbol(provider_id, provider_symbol)
            assert reversed_instr is not None
            assert reversed_instr.canonicalSymbol == canonical
    
    print("[PASS] Reverse lookup consistency verified")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Testing Tasks 9.5-9.10: Runtime Instruments Endpoint")
    print("="*60 + "\n")
    
    tests = [
        test_all_8_instruments_registered,
        test_provider_coverage_complete,
        test_instrument_metadata_correct,
        test_xauusd_provider_symbols,
        test_reverse_lookup_consistency,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] {test_func.__name__}: {e}")
    
    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60 + "\n")
    
    exit(0 if failed == 0 else 1)
