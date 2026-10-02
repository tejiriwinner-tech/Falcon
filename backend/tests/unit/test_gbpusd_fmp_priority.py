"""
Unit test verifying that FMP is prioritized for GBPUSD (and alias GPBUSD) ONLY,
while TwelveData is prioritized first for all other instruments (EURUSD, XAUUSD, etc.).
"""

import pytest
from app.core.providers import provider_manager
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


def test_other_instruments_do_not_prioritize_fmp():
    """Verify that EURUSD, XAUUSD, and default instruments do NOT prioritize FMP first."""
    candidates_eur = provider_manager._get_candidate_providers("EURUSD")
    candidate_ids_eur = [p.provider_id for p in candidates_eur]
    assert len(candidate_ids_eur) > 0
    assert candidate_ids_eur[0] == "twelve_data", f"Expected TwelveData first for EURUSD, got: {candidate_ids_eur}"

    candidates_gold = provider_manager._get_candidate_providers("XAUUSD")
    candidate_ids_gold = [p.provider_id for p in candidates_gold]
    assert len(candidate_ids_gold) > 0
    assert candidate_ids_gold[0] == "twelve_data", f"Expected TwelveData first for XAUUSD, got: {candidate_ids_gold}"

    candidates_default = provider_manager._get_candidate_providers("USDJPY")
    candidate_ids_default = [p.provider_id for p in candidates_default]
    assert len(candidate_ids_default) > 0
    assert candidate_ids_default[0] == "twelve_data", f"Expected TwelveData first for default, got: {candidate_ids_default}"
