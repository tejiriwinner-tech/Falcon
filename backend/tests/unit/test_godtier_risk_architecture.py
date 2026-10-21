import pytest
from unittest.mock import MagicMock
from app.core.services.position_sizing_service import PositionSizingService
from app.core.services.signal_service import (
    extract_directional_currency_exposures,
)
from app.core.engines.decision.evaluators.macro_cross_asset_evaluator import (
    MacroCrossAssetEngine,
    MacroDxySnapshot,
)
from app.core.engines.risk_engine import RiskEngine


def test_portfolio_heat_multipliers():
    """Verify progressive position sizing throttling based on active portfolio heat."""
    assert PositionSizingService.calculate_portfolio_heat_multiplier(0) == 1.0
    assert PositionSizingService.calculate_portfolio_heat_multiplier(1) == 1.0
    assert PositionSizingService.calculate_portfolio_heat_multiplier(2) == 0.75
    assert PositionSizingService.calculate_portfolio_heat_multiplier(3) == 0.50
    assert PositionSizingService.calculate_portfolio_heat_multiplier(4) == 0.35
    assert PositionSizingService.calculate_portfolio_heat_multiplier(5) == 0.35

    # Check scaled lot sizes
    assert PositionSizingService.calculate_portfolio_heat_lot_size(1, 0.10) == 0.10
    assert PositionSizingService.calculate_portfolio_heat_lot_size(2, 0.10) == 0.08  # 0.075 rounded to 0.08
    assert PositionSizingService.calculate_portfolio_heat_lot_size(3, 0.10) == 0.05
    assert PositionSizingService.calculate_portfolio_heat_lot_size(4, 0.10) == 0.03  # 0.035 rounded to 0.03


def test_directional_currency_exposure_extraction():
    """Verify exact directional currency exposure extraction for major pairs and crosses."""
    # Major pairs
    assert extract_directional_currency_exposures("EUR/USD", "BUY") == ["+EUR", "-USD"]
    assert extract_directional_currency_exposures("EUR/USD", "SELL") == ["-EUR", "+USD"]
    assert extract_directional_currency_exposures("USD/JPY", "BUY") == ["+USD", "-JPY"]
    assert extract_directional_currency_exposures("USD/JPY", "SELL") == ["-USD", "+JPY"]
    assert extract_directional_currency_exposures("GBP/USD", "BUY") == ["+GBP", "-USD"]
    assert extract_directional_currency_exposures("AUD/USD", "BUY") == ["+AUD", "-USD"]

    # Commodity
    assert extract_directional_currency_exposures("XAU/USD", "BUY") == ["+XAU", "-USD"]
    assert extract_directional_currency_exposures("XAU/USD", "SELL") == ["-XAU", "+USD"]

    # Crosses
    assert extract_directional_currency_exposures("GBP/JPY", "BUY") == ["+GBP", "-JPY"]
    assert extract_directional_currency_exposures("GBP/JPY", "SELL") == ["-GBP", "+JPY"]
    assert extract_directional_currency_exposures("EUR/GBP", "BUY") == ["+EUR", "-GBP"]


def test_macro_dxy_trap_filter():
    """Verify macro cross-asset filter vetoes adverse directional USD bets."""
    engine = MacroCrossAssetEngine()

    # Case 1: DXY is BULLISH, candidate is EUR/USD BUY (Short USD) -> Must trigger macro trap
    snap_bullish = MacroDxySnapshot(
        dxy_index=105.5,
        dxy_momentum_pct=0.45,
        dxy_bias="BULLISH",
        yield_proxy_bias="NEUTRAL",
        timestamp=1000.0,
        components_used=5,
    )
    assessment1 = engine.evaluate_alignment("EURUSD", "BUY", snap_bullish)
    assert assessment1.is_macro_trap is True
    assert "Macro Bull Trap Veto" in assessment1.rationale

    # Case 2: DXY is BULLISH, candidate is EUR/USD SELL (Long USD) -> Permitted
    assessment2 = engine.evaluate_alignment("EURUSD", "SELL", snap_bullish)
    assert assessment2.is_macro_trap is False

    # Case 3: DXY is STRONG_BEARISH, candidate is USD/JPY BUY (Long USD) -> Must trigger macro trap
    snap_bearish = MacroDxySnapshot(
        dxy_index=103.0,
        dxy_momentum_pct=-0.55,
        dxy_bias="STRONG_BEARISH",
        yield_proxy_bias="NEUTRAL",
        timestamp=1000.0,
        components_used=5,
    )
    assessment3 = engine.evaluate_alignment("USDJPY", "BUY", snap_bearish)
    assert assessment3.is_macro_trap is True
    assert "Macro Bull Trap Veto" in assessment3.rationale

    # Case 4: DXY is STRONG_BEARISH, candidate is USD/JPY SELL (Short USD) -> Permitted
    assessment4 = engine.evaluate_alignment("USDJPY", "SELL", snap_bearish)
    assert assessment4.is_macro_trap is False


def test_risk_engine_currency_basket_correlation():
    """Verify RiskEngine evaluates directional currency correlation with open trades."""
    engine = RiskEngine()
    
    # Candidate is EUR/USD BUY (+EUR, -USD)
    candidate = MagicMock()
    candidate.symbol = "EUR/USD"
    candidate.pair = "EUR/USD"
    candidate.action = "BUY"
    candidate.direction = "BUY"

    # Context has open trade on GBP/USD BUY (+GBP, -USD) -> Correlated USD short!
    correlated_trade = MagicMock()
    correlated_trade.pair = "GBP/USD"
    correlated_trade.symbol = "GBP/USD"
    correlated_trade.action = "BUY"
    correlated_trade.direction = "BUY"
    correlated_trade.status = "OPEN"
    correlated_trade.closeDate = None

    score_corr = engine._evaluate_currency_basket_correlation(candidate, [correlated_trade])
    assert score_corr == 15.0  # High exposure docked

    # Context has open trade on USD/JPY BUY (+USD, -JPY) -> Diversified / Hedged!
    hedged_trade = MagicMock()
    hedged_trade.pair = "USD/JPY"
    hedged_trade.symbol = "USD/JPY"
    hedged_trade.action = "BUY"
    hedged_trade.direction = "BUY"
    hedged_trade.status = "OPEN"
    hedged_trade.closeDate = None

    score_clean = engine._evaluate_currency_basket_correlation(candidate, [hedged_trade])
    assert score_clean == 8.0  # Clean score
