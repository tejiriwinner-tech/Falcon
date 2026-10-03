"""
Unit tests for Watchlist Expansion (6 Assets) and OANDA Historical Candle Backfilling.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.core.config import settings
from app.core.providers.symbol_mapper import symbol_mapper
from app.core.services.market_data_scheduler import MarketDataScheduler
from app.core.services.market_history_service import (
    MarketHistoryService,
    OANDA_PROVIDER,
    TWELVE_DATA_PROVIDER,
    ALPHA_VANTAGE_PROVIDER,
    _parse_bar_time,
)


def test_watchlist_expansion_parsing():
    """Verify MarketDataScheduler parses all 6 core institutional symbols from settings."""
    scheduler = MarketDataScheduler()
    symbols = scheduler._parse_watchlist(settings.MARKET_DATA_WATCHLIST)
    expected = ["XAUUSD", "GBPUSD", "EURUSD", "GBPJPY", "USDJPY", "AUDUSD"]
    for sym in expected:
        assert sym in symbols
    assert len(symbols) >= 6


def test_all_symbols_mapped_to_oanda_and_fallbacks():
    """Verify symbol mapper maps all 6 symbols to OANDA, TwelveData, and Alpha Vantage tickers."""
    symbols = ["XAUUSD", "GBPUSD", "EURUSD", "GBPJPY", "USDJPY", "AUDUSD"]
    for sym in symbols:
        assert symbol_mapper.to_provider_symbol(sym, "oanda") is not None
        assert "_" in symbol_mapper.to_provider_symbol(sym, "oanda")
        assert symbol_mapper.to_provider_symbol(sym, "twelve_data") is not None
        assert symbol_mapper.to_provider_symbol(sym, "alpha_vantage") is not None


def test_parse_bar_time_rfc3339_and_nanoseconds():
    """Verify _parse_bar_time handles OANDA RFC3339 nanosecond timestamps accurately."""
    rfc3339_nano = "2026-10-03T10:00:00.000000000Z"
    dt = _parse_bar_time(rfc3339_nano)
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 10
    assert dt.day == 3
    assert dt.hour == 10
    assert dt.tzinfo == timezone.utc

    rfc3339_simple = "2026-10-03T08:30:00Z"
    dt2 = _parse_bar_time(rfc3339_simple)
    assert dt2 is not None
    assert dt2.minute == 30


def test_market_history_service_fetches_oanda_first():
    """Verify that MarketHistoryService fetches from OANDA as Priority 1."""
    service = MarketHistoryService()

    mock_candles = [
        {
            "time": "2026-10-03T08:00:00.000000000Z",
            "open": 1.3210,
            "high": 1.3250,
            "low": 1.3200,
            "close": 1.3240,
            "volume": 1250,
        },
        {
            "time": "2026-10-03T09:00:00.000000000Z",
            "open": 1.3240,
            "high": 1.3280,
            "low": 1.3235,
            "close": 1.3275,
            "volume": 1400,
        },
    ]

    mock_oanda = MagicMock()
    mock_oanda.configured = True
    mock_oanda.fetch_candles.return_value = mock_candles

    with patch("app.core.providers._oanda_provider", mock_oanda), \
         patch.object(settings, "OANDA_API_KEY", "test_key"), \
         patch.object(service, "_fetch_twelve_data") as mock_td, \
         patch.object(service, "_fetch_alpha_vantage") as mock_av:

        bars = service._fetch_oanda("GBPJPY", "1h", 500)
        assert len(bars) == 2
        assert bars[0].symbol == "GBPJPY"
        assert bars[0].provider == OANDA_PROVIDER
        assert bars[0].close == 1.3240
        assert bars[1].close == 1.3275

        # When refresh_symbol runs, twelve_data and alpha_vantage should not be called
        with patch.object(service, "store_bars", return_value=2):
            count = service.refresh_symbol("GBPJPY", timeframe="1h", force=True, bypass_budget=True)
            assert count == 2
            mock_td.assert_not_called()
            mock_av.assert_not_called()


def test_market_history_service_fallback_when_oanda_empty():
    """Verify that MarketHistoryService falls back to TwelveData when OANDA returns no bars."""
    service = MarketHistoryService()

    with patch.object(service, "_fetch_oanda", return_value=[]), \
         patch.object(service, "_fetch_twelve_data", return_value=[
             MagicMock(symbol="AUDUSD", timeframe="1h", bar_time=datetime.now(timezone.utc),
                       open=0.6500, high=0.6520, low=0.6490, close=0.6515, volume=500, provider=TWELVE_DATA_PROVIDER)
         ]) as mock_td, \
         patch.object(service, "store_bars", return_value=1):

        count = service.refresh_symbol("AUDUSD", timeframe="1h", force=True, bypass_budget=True)
        assert count == 1
        mock_td.assert_called_once()
