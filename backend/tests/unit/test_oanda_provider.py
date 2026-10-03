"""
Unit tests for OANDA v20 Provider, Symbol Mapping, Batch Quotes, and Graceful Failover.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.core.providers.oanda_provider import OandaProvider
from app.core.providers.symbol_mapper import symbol_mapper
from app.core.providers.provider_registry import ProviderRegistry
from app.core.providers.cache import MarketDataCache
from app.core.providers.provider_manager import ProviderManager
from app.schemas.provider_models import ProviderHealth, ProviderCapability


def test_oanda_symbol_mapping():
    """Verify canonical symbols translate to OANDA underscore format and aliases normalize."""
    assert symbol_mapper.to_provider_symbol("GBPUSD", "oanda") == "GBP_USD"
    assert symbol_mapper.to_provider_symbol("XAUUSD", "oanda") == "XAU_USD"
    assert symbol_mapper.to_provider_symbol("EURUSD", "oanda") == "EUR_USD"
    assert symbol_mapper.to_provider_symbol("GBPJPY", "oanda") == "GBP_JPY"
    assert symbol_mapper.to_provider_symbol("USDJPY", "oanda") == "USD_JPY"

    # Aliases
    assert symbol_mapper.normalize("gbp_jpy") == "GBPJPY"
    assert symbol_mapper.normalize("guppy") == "GBPJPY"
    assert symbol_mapper.normalize("gold") == "XAUUSD"
    assert symbol_mapper.normalize("cable") == "GBPUSD"


def test_oanda_unconfigured_graceful_failover():
    """Verify that when unconfigured, OANDA provider safely returns None with zero HTTP calls."""
    unconfigured_provider = OandaProvider(api_key="", account_id="")
    assert not unconfigured_provider.configured
    assert unconfigured_provider.health_check() == ProviderHealth.CRITICAL

    with patch("requests.get") as mock_get:
        res = unconfigured_provider.fetch("GBPUSD")
        assert res is None
        mock_get.assert_not_called()

        batch_res = unconfigured_provider.fetch_batch(["GBPUSD", "EURUSD"])
        assert batch_res == {}
        mock_get.assert_not_called()


def test_oanda_single_quote_fetch_and_pip_calculation():
    """Verify parsing of OANDA JSON pricing payload and pip spread calculation."""
    provider = OandaProvider(
        api_key="mock_test_key_12345",
        account_id="101-004-12345678-001",
        base_url="https://api-fxpractice.oanda.com",
    )
    assert provider.configured

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "time": "2026-10-03T10:00:00.000000Z",
        "prices": [
            {
                "instrument": "GBP_USD",
                "status": "tradeable",
                "closeoutBid": "1.32160",
                "closeoutAsk": "1.32175",
                "time": "2026-10-03T10:00:00.000000Z",
            }
        ],
    }

    with patch("requests.get", return_value=mock_resp) as mock_get:
        quote = provider.fetch("GBPUSD")
        assert quote is not None
        assert quote["symbol"] == "GBPUSD"
        assert quote["bid"] == 1.32160
        assert quote["ask"] == 1.32175
        assert quote["price"] == 1.32167  # mid
        assert quote["mid"] == 1.32167
        assert quote["lastPrice"] == 1.32167
        assert quote["spread"] == 0.00015
        assert quote["spread_pips"] == 1.5
        assert quote["is_market_open"] is True
        assert quote["provider"] == "oanda"
        mock_get.assert_called_once()


def test_oanda_batch_quote_fetch_multi_symbol():
    """Verify batch fetching returns multiple symbols in one single HTTP call."""
    provider = OandaProvider(
        api_key="mock_test_key_12345",
        account_id="101-004-12345678-001",
        base_url="https://api-fxpractice.oanda.com",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "time": "2026-10-03T10:00:00.000000Z",
        "prices": [
            {
                "instrument": "GBP_USD",
                "status": "tradeable",
                "closeoutBid": "1.32160",
                "closeoutAsk": "1.32175",
            },
            {
                "instrument": "EUR_USD",
                "status": "tradeable",
                "closeoutBid": "1.08500",
                "closeoutAsk": "1.08512",
            },
            {
                "instrument": "XAU_USD",
                "status": "tradeable",
                "closeoutBid": "2650.50",
                "closeoutAsk": "2650.85",
            },
            {
                "instrument": "GBP_JPY",
                "status": "tradeable",
                "closeoutBid": "194.200",
                "closeoutAsk": "194.225",
            },
        ],
    }

    with patch("requests.get", return_value=mock_resp) as mock_get:
        batch = provider.fetch_batch(["GBPUSD", "EURUSD", "XAUUSD", "GBPJPY"])
        assert len(batch) == 4
        assert "GBPUSD" in batch
        assert "EURUSD" in batch
        assert "XAUUSD" in batch
        assert "GBPJPY" in batch

        # Verify JPY pip calculation (pip_size = 0.01)
        jpy_quote = batch["GBPJPY"]
        assert jpy_quote["spread"] == 0.025
        assert jpy_quote["spread_pips"] == 2.5

        # Verify Gold pip calculation (pip_size = 0.10)
        gold_quote = batch["XAUUSD"]
        assert gold_quote["spread"] == 0.35
        assert gold_quote["spread_pips"] == 3.5

        # Verify single HTTP call was dispatched
        mock_get.assert_called_once()
        called_url = mock_get.call_args[0][0]
        called_params = mock_get.call_args[1]["params"]
        assert "pricing" in called_url
        assert "GBP_USD" in called_params["instruments"]
        assert "EUR_USD" in called_params["instruments"]


def test_provider_manager_routing_prioritizes_oanda():
    """Verify ProviderManager routes to OANDA as Priority 1 when configured."""
    registry = ProviderRegistry()
    cache = MarketDataCache()

    oanda = OandaProvider(api_key="valid_key", account_id="101-004-valid-001")
    twelve_data = MagicMock()
    twelve_data.provider_id = "twelve_data"
    twelve_data.provider_name = "TwelveData"
    twelve_data.configured = True
    twelve_data.supports_symbol.return_value = True
    twelve_data.supports.return_value = True

    fmp = MagicMock()
    fmp.provider_id = "fmp"
    fmp.provider_name = "Financial Modeling Prep"
    fmp.configured = True
    fmp.supports_symbol.side_effect = lambda s: s in ("GBPUSD", "GPBUSD")
    fmp.supports.return_value = True

    registry.register(oanda, priority=1)
    registry.register(fmp, priority=2)
    registry.register(twelve_data, priority=3)

    pm = ProviderManager(registry, cache, symbol_mapper)

    # When OANDA is configured, candidate #1 for GBPUSD, EURUSD, XAUUSD is OANDA
    gbp_candidates = pm._get_candidate_providers("GBPUSD")
    assert gbp_candidates[0].provider_id == "oanda"
    assert gbp_candidates[1].provider_id == "fmp"

    eur_candidates = pm._get_candidate_providers("EURUSD")
    assert eur_candidates[0].provider_id == "oanda"
    assert eur_candidates[1].provider_id == "twelve_data"

    xau_candidates = pm._get_candidate_providers("XAUUSD")
    assert xau_candidates[0].provider_id == "oanda"
    assert xau_candidates[1].provider_id == "twelve_data"


def test_provider_manager_routing_failover_when_oanda_unconfigured():
    """Verify ProviderManager skips unconfigured OANDA and smoothly falls back to FMP/TwelveData."""
    registry = ProviderRegistry()
    cache = MarketDataCache()

    oanda_unconfigured = OandaProvider(api_key="", account_id="")
    twelve_data = MagicMock()
    twelve_data.provider_id = "twelve_data"
    twelve_data.provider_name = "TwelveData"
    twelve_data.configured = True
    twelve_data.supports_symbol.return_value = True
    twelve_data.supports.return_value = True

    fmp = MagicMock()
    fmp.provider_id = "fmp"
    fmp.provider_name = "Financial Modeling Prep"
    fmp.configured = True
    fmp.supports_symbol.side_effect = lambda s: s in ("GBPUSD", "GPBUSD")
    fmp.supports.return_value = True

    registry.register(oanda_unconfigured, priority=1)
    registry.register(fmp, priority=2)
    registry.register(twelve_data, priority=3)

    pm = ProviderManager(registry, cache, symbol_mapper)

    # When OANDA is unconfigured, candidate #1 for GBPUSD is FMP, and for EURUSD is TwelveData
    gbp_candidates = pm._get_candidate_providers("GBPUSD")
    assert gbp_candidates[0].provider_id == "fmp"

    eur_candidates = pm._get_candidate_providers("EURUSD")
    assert eur_candidates[0].provider_id == "twelve_data"
