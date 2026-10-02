"""
Unit test verifying that FMP is prioritized for GBPUSD (and alias GPBUSD) ONLY,
and that FMP is STRICTLY EXCLUDED from calling any other currency pair or instrument
(EURUSD, XAUUSD, USDJPY, BTCUSD, etc.).
"""

from unittest.mock import Mock, patch
import pytest

from app.core.providers import provider_manager
from app.core.providers.fmp_provider import FmpProvider
from app.core.providers.symbol_mapper import symbol_mapper


def test_symbol_mapper_gpbusd_normalization():
    """Verify that GPBUSD and variations normalize to canonical GBPUSD."""
    assert symbol_mapper.normalize("GPBUSD") == "GBPUSD"
    assert symbol_mapper.normalize("gpb/usd") == "GBPUSD"
    assert symbol_mapper.normalize("gpb_usd") == "GBPUSD"
    assert symbol_mapper.normalize("GBPUSD") == "GBPUSD"


def test_gbpusd_prioritizes_fmp_first():
    """Verify that GBPUSD and GPBUSD candidate provider list routes FMP as Priority 1."""
    candidates_gbp = provider_manager._get_candidate_providers("GBPUSD")
    candidate_ids_gbp = [p.provider_id for p in candidates_gbp]
    assert len(candidate_ids_gbp) > 0
    assert candidate_ids_gbp[0] == "fmp", f"Expected FMP first for GBPUSD, got: {candidate_ids_gbp}"

    candidates_gpb = provider_manager._get_candidate_providers("GPBUSD")
    candidate_ids_gpb = [p.provider_id for p in candidates_gpb]
    assert len(candidate_ids_gpb) > 0
    assert candidate_ids_gpb[0] == "fmp", f"Expected FMP first for GPBUSD, got: {candidate_ids_gpb}"


def test_other_instruments_strictly_exclude_fmp():
    """Verify that EURUSD, XAUUSD, USDJPY, and any other pair DO NOT include FMP at all."""
    for sym in ["EURUSD", "XAUUSD", "USDJPY", "BTCUSD", "ETHUSD", "AUDUSD", "NZDUSD"]:
        candidates = provider_manager._get_candidate_providers(sym)
        candidate_ids = [p.provider_id for p in candidates]
        assert "fmp" not in candidate_ids, f"FMP must NOT be called for {sym}, but found in candidates: {candidate_ids}"
        assert candidate_ids[0] == "twelve_data", f"Expected TwelveData first for {sym}, got: {candidate_ids}"


def test_fmp_provider_supports_symbol_whitelist():
    """Verify that FmpProvider.supports_symbol returns True strictly for GBPUSD / GPBUSD."""
    provider = FmpProvider(api_key="test_key")
    assert provider.supports_symbol("GBPUSD") is True
    assert provider.supports_symbol("GPBUSD") is True
    assert provider.supports_symbol("gbp/usd") is True

    # All other currency pairs must return False
    assert provider.supports_symbol("EURUSD") is False
    assert provider.supports_symbol("XAUUSD") is False
    assert provider.supports_symbol("USDJPY") is False
    assert provider.supports_symbol("BTCUSD") is False
    assert provider.supports_symbol("USDCAD") is False


@patch("app.core.providers.fmp_provider.requests.Session.get")
def test_fmp_fetch_rejects_non_gbp_pairs_without_network_call(mock_get):
    """Verify that FmpProvider.fetch immediately rejects any non-GBP pair with zero HTTP requests."""
    provider = FmpProvider(api_key="test_key")
    provider._connected = True

    for non_gbp_sym in ["EURUSD", "XAUUSD", "USDJPY", "BTCUSD", "AUDUSD"]:
        result = provider.fetch(non_gbp_sym)
        assert result is None, f"Expected fetch({non_gbp_sym}) to return None, got: {result}"

    # Ensure no HTTP requests were dispatched
    mock_get.assert_not_called()
