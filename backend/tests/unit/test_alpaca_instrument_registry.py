"""
Phase 7.2 Milestone 1 - Alpaca Instrument Registry Tests
Tests that instrument registry includes Alpaca mappings and existing mappings remain unchanged.
"""
import pytest
from app.core.instruments.instrument_registry import instrument_registry


class TestAlpacaInstrumentMappings:
    """Test that instruments include Alpaca provider mappings."""

    def test_xauusd_has_alpaca_mapping(self):
        """Test that XAUUSD has Alpaca mapping."""
        instrument = instrument_registry.get_instrument("XAUUSD")
        assert instrument is not None
        assert "alpaca" in instrument.providerMappings
        assert instrument.providerMappings["alpaca"] == "XAU/USD"

    def test_gbpusd_has_alpaca_mapping(self):
        """Test that GBPUSD has Alpaca mapping."""
        instrument = instrument_registry.get_instrument("GBPUSD")
        assert instrument is not None
        assert "alpaca" in instrument.providerMappings
        assert instrument.providerMappings["alpaca"] == "GBP/USD"

    def test_eurusd_has_alpaca_mapping(self):
        """Test that EURUSD has Alpaca mapping."""
        instrument = instrument_registry.get_instrument("EURUSD")
        assert instrument is not None
        assert "alpaca" in instrument.providerMappings
        assert instrument.providerMappings["alpaca"] == "EUR/USD"

    def test_usdjpy_has_alpaca_mapping(self):
        """Test that USDJPY has Alpaca mapping."""
        instrument = instrument_registry.get_instrument("USDJPY")
        assert instrument is not None
        assert "alpaca" in instrument.providerMappings
        assert instrument.providerMappings["alpaca"] == "USD/JPY"

    def test_nas100_has_alpaca_mapping(self):
        """Test that NAS100 has Alpaca mapping."""
        instrument = instrument_registry.get_instrument("NAS100")
        assert instrument is not None
        assert "alpaca" in instrument.providerMappings
        assert instrument.providerMappings["alpaca"] == "^NDX"

    def test_us30_has_alpaca_mapping(self):
        """Test that US30 has Alpaca mapping."""
        instrument = instrument_registry.get_instrument("US30")
        assert instrument is not None
        assert "alpaca" in instrument.providerMappings
        assert instrument.providerMappings["alpaca"] == "^DJI"


class TestExistingInstrumentMappingsUnchanged:
    """Test that existing instrument provider mappings remain unchanged after Finnhub removal."""

    def test_xauusd_has_twelve_data_mapping(self):
        """Test that XAUUSD still has TwelveData mapping."""
        instrument = instrument_registry.get_instrument("XAUUSD")
        assert instrument is not None
        assert "twelve_data" in instrument.providerMappings
        assert instrument.providerMappings["twelve_data"] == "XAU/USD"

    def test_xauusd_has_yahoo_finance_mapping(self):
        """Test that XAUUSD still has Yahoo Finance mapping."""
        instrument = instrument_registry.get_instrument("XAUUSD")
        assert instrument is not None
        assert "yahoo_finance" in instrument.providerMappings
        assert instrument.providerMappings["yahoo_finance"] == "GC=F"

    def test_xauusd_no_finnhub_mapping(self):
        """Test that XAUUSD no longer has Finnhub mapping (Finnhub removed)."""
        instrument = instrument_registry.get_instrument("XAUUSD")
        assert instrument is not None
        assert "finnhub" not in instrument.providerMappings

    def test_gbpusd_no_finnhub_mapping(self):
        """Test that GBPUSD no longer has Finnhub mapping (Finnhub removed)."""
        instrument = instrument_registry.get_instrument("GBPUSD")
        assert instrument is not None
        assert "finnhub" not in instrument.providerMappings

    def test_eurusd_no_finnhub_mapping(self):
        """Test that EURUSD no longer has Finnhub mapping (Finnhub removed)."""
        instrument = instrument_registry.get_instrument("EURUSD")
        assert instrument is not None
        assert "finnhub" not in instrument.providerMappings


class TestInstrumentRegistryReverseLookup:
    """Test that reverse lookups work with Alpaca mappings."""

    def test_reverse_lookup_alpaca_xauusd(self):
        """Test reverse lookup for Alpaca XAUUSD."""
        instrument = instrument_registry.get_by_provider_symbol("alpaca", "XAU/USD")
        assert instrument is not None
        assert instrument.canonicalSymbol == "XAUUSD"

    def test_reverse_lookup_alpaca_gbpusd(self):
        """Test reverse lookup for Alpaca GBPUSD."""
        instrument = instrument_registry.get_by_provider_symbol("alpaca", "GBP/USD")
        assert instrument is not None
        assert instrument.canonicalSymbol == "GBPUSD"

    def test_reverse_lookup_twelvedata_still_works(self):
        """Test that reverse lookup for TwelveData still works."""
        instrument = instrument_registry.get_by_provider_symbol("twelve_data", "XAU/USD")
        assert instrument is not None
        assert instrument.canonicalSymbol == "XAUUSD"


class TestInstrumentRegistryCompleteness:
    """Test that instrument registry has all required mappings."""

    def test_xauusd_has_all_provider_mappings(self):
        """Test that XAUUSD has all provider mappings (Finnhub removed)."""
        instrument = instrument_registry.get_instrument("XAUUSD")
        expected_providers = ["twelve_data", "alpaca", "yahoo_finance", "mock_price"]
        for provider in expected_providers:
            assert provider in instrument.providerMappings

    def test_gbpusd_has_all_provider_mappings(self):
        """Test that GBPUSD has all provider mappings (Finnhub removed)."""
        instrument = instrument_registry.get_instrument("GBPUSD")
        expected_providers = ["twelve_data", "alpaca", "yahoo_finance", "mock_price"]
        for provider in expected_providers:
            assert provider in instrument.providerMappings

    def test_eurusd_has_all_provider_mappings(self):
        """Test that EURUSD has all provider mappings (Finnhub removed)."""
        instrument = instrument_registry.get_instrument("EURUSD")
        expected_providers = ["twelve_data", "alpaca", "yahoo_finance", "mock_price"]
        for provider in expected_providers:
            assert provider in instrument.providerMappings
