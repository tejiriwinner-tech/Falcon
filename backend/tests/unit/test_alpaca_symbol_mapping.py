"""
Phase 7.2 Milestone 1 - Alpaca Symbol Mapping Tests
Tests that Alpaca symbol mappings work correctly and existing mappings remain unchanged.
"""
import pytest
from app.core.providers.symbol_mapper import symbol_mapper


class TestAlpacaSymbolMapping:
    """Test Alpaca symbol mappings."""

    def test_xauusd_maps_to_alpaca_format(self):
        """Test that XAUUSD maps to Alpaca format."""
        result = symbol_mapper.to_provider_symbol("XAUUSD", "alpaca")
        assert result == "XAU/USD"

    def test_gbpusd_maps_to_alpaca_format(self):
        """Test that GBPUSD maps to Alpaca format."""
        result = symbol_mapper.to_provider_symbol("GBPUSD", "alpaca")
        assert result == "GBP/USD"

    def test_eurusd_maps_to_alpaca_format(self):
        """Test that EURUSD maps to Alpaca format."""
        result = symbol_mapper.to_provider_symbol("EURUSD", "alpaca")
        assert result == "EUR/USD"

    def test_usdjpy_maps_to_alpaca_format(self):
        """Test that USDJPY maps to Alpaca format."""
        result = symbol_mapper.to_provider_symbol("USDJPY", "alpaca")
        assert result == "USD/JPY"

    def test_nas100_maps_to_alpaca_format(self):
        """Test that NAS100 maps to Alpaca format."""
        result = symbol_mapper.to_provider_symbol("NAS100", "alpaca")
        assert result == "^NDX"

    def test_us30_maps_to_alpaca_format(self):
        """Test that US30 maps to Alpaca format."""
        result = symbol_mapper.to_provider_symbol("US30", "alpaca")
        assert result == "^DJI"

    def test_alias_maps_to_alpaca_format(self):
        """Test that aliases map to Alpaca format."""
        result = symbol_mapper.to_provider_symbol("gold", "alpaca")
        assert result == "XAU/USD"


class TestExistingSymbolMappingsUnchanged:
    """Test that existing symbol mappings remain unchanged after Finnhub removal."""

    def test_xauusd_maps_to_twelvedata_format(self):
        """Test that XAUUSD maps to TwelveData format."""
        result = symbol_mapper.to_provider_symbol("XAUUSD", "twelve_data")
        assert result == "XAU/USD"

    def test_gbpusd_maps_to_alpha_vantage_format(self):
        """Test that GBPUSD maps to current providers' formats (Yahoo removed)."""
        from app.core.providers.symbol_mapper import _PROVIDER_SYMBOL_MAP

        # Alpha Vantage — current secondary/fallback provider (GBP/USD FX pair)
        # Note: assert against the declared mapping table, mirroring the Alpaca
        # mapping tests, because AlphaVantageProvider resolves its tickers
        # internally (FX_DAILY from/to symbols) rather than via to_provider_symbol.
        assert _PROVIDER_SYMBOL_MAP["alpha_vantage"]["GBPUSD"] == "GBP/USD"
        # Twelve Data — primary provider
        assert symbol_mapper.to_provider_symbol("GBPUSD", "twelve_data") == "GBP/USD"

    def test_finnhub_mappings_removed(self):
        """Test that Finnhub mappings are removed from symbol mapper."""
        from app.core.providers.symbol_mapper import _PROVIDER_SYMBOL_MAP
        assert "finnhub" not in _PROVIDER_SYMBOL_MAP


class TestOtherProvidersUnchanged:
    """Test that other provider mappings remain unchanged."""

    def test_twelve_data_mappings_unchanged(self):
        """Test that TwelveData mappings are unchanged."""
        result = symbol_mapper.to_provider_symbol("XAUUSD", "twelve_data")
        assert result == "XAU/USD"

    def test_alpha_vantage_mappings_unchanged(self):
        """Test that Alpha Vantage mappings are active and Yahoo mappings are removed."""
        from app.core.providers.symbol_mapper import _PROVIDER_SYMBOL_MAP

        # Alpha Vantage — current secondary/fallback provider (see AlphaVantageProvider:
        # XAU via GOLD_SILVER_SPOT "XAU", GBP via FX pair GBP/USD).
        # Assert against the declared mapping table, consistent with the Alpaca
        # mapping tests (AlphaVantageProvider does not use to_provider_symbol).
        assert _PROVIDER_SYMBOL_MAP["alpha_vantage"]["XAUUSD"] == "XAU"
        assert _PROVIDER_SYMBOL_MAP["alpha_vantage"]["GBPUSD"] == "GBP/USD"
        # Twelve Data — primary provider
        assert symbol_mapper.to_provider_symbol("XAUUSD", "twelve_data") == "XAU/USD"
        # Yahoo Finance symbol mappings have been completely removed
        assert "yahoo_finance" not in _PROVIDER_SYMBOL_MAP

    def test_mock_price_mappings_unchanged(self):
        """Test that Mock Price mappings are unchanged."""
        result = symbol_mapper.to_provider_symbol("XAUUSD", "mock_price")
        assert result == "XAUUSD"


class TestAlpacaMappingsExist:
    """Test that Alpaca mappings exist in symbol mapper."""

    def test_alpaca_mappings_exist(self):
        """Test that Alpaca mappings exist in symbol mapper."""
        from app.core.providers.symbol_mapper import _PROVIDER_SYMBOL_MAP
        assert "alpaca" in _PROVIDER_SYMBOL_MAP

    def test_alpaca_has_all_required_mappings(self):
        """Test that Alpaca has all required symbol mappings."""
        from app.core.providers.symbol_mapper import _PROVIDER_SYMBOL_MAP
        alpaca_mappings = _PROVIDER_SYMBOL_MAP["alpaca"]
        required_symbols = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30"]
        for symbol in required_symbols:
            assert symbol in alpaca_mappings

    def test_alpaca_mappings_are_correct(self):
        """Test that Alpaca mappings have correct values."""
        from app.core.providers.symbol_mapper import _PROVIDER_SYMBOL_MAP
        alpaca_mappings = _PROVIDER_SYMBOL_MAP["alpaca"]
        assert alpaca_mappings["XAUUSD"] == "XAU/USD"
        assert alpaca_mappings["GBPUSD"] == "GBP/USD"
        assert alpaca_mappings["EURUSD"] == "EUR/USD"
        assert alpaca_mappings["USDJPY"] == "USD/JPY"
        assert alpaca_mappings["NAS100"] == "^NDX"
        assert alpaca_mappings["US30"] == "^DJI"
