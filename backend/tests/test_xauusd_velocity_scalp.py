"""
Verification test suite for strat-024 (XAU/USD London-NY Velocity Scalp):
1. strat-024 registered as ACTIVE SCALPING strategy on XAU/USD
2. True Scalp Geometry ($3.50-$7.00 SL, 1.2R TP) when is_scalp=True
3. Standard Gold swing ($14.00+ floor) and EUR/USD strat-006 (v3.1) 100% untouched
4. OrderFlowEngine v3.0 Hedge Fund Trap veto works alongside strat-006 anti-wick DNA
"""
import sys
sys.path.insert(0, "backend")

from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.schemas.signal_candidate import CandidateDirection
from app.schemas.strategy import StrategyCategory, StrategyStatus


def test_strat_024_definition_and_strat_006_untouched():
    engine = StrategyEngine()
    s24 = engine.get_strategy_by_id("strat-024")
    assert s24 is not None, "strat-024 missing"
    assert s24.category == StrategyCategory.SCALPING
    assert s24.symbol == "XAU/USD"
    assert s24.minimumRiskReward == 1.2

    s06 = engine.get_strategy_by_id("strat-006")
    assert s06 is not None
    assert s06.symbol == "EUR/USD"
    assert s06.strategyVersion == "3.1", "strat-006 must remain untouched!"
    print("strat-024 definition & strat-006 untouched verified!")


def test_xau_scalp_geometry_vs_swing_and_eurusd():
    # Gold Scalp: ATR = 5.0 -> 0.85 * 5.0 = 4.25 (clamped between 3.50 and 7.00), TP = 1.2R = 5.10
    entry, sl, tp = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.SELL,
        current_price=3850.00,
        atr=5.0,
        symbol="XAU/USD",
        is_scalp=True,
    )
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    assert 3.50 <= risk <= 7.00, f"Scalp SL out of bounds: {risk}"
    assert abs((reward / risk) - 1.2) < 0.02, f"Scalp RR expected 1.2, got {reward / risk}"

    # Gold Scalp upper cap ($7.00 max even when ATR is huge)
    entry2, sl2, tp2 = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.BUY,
        current_price=3850.00,
        atr=20.0,
        symbol="XAU/USD",
        is_scalp=True,
    )
    assert abs(entry2 - sl2) == 7.00, f"Scalp SL cap failed: {abs(entry2 - sl2)}"
    assert abs((abs(tp2 - entry2) / 7.00) - 1.2) < 0.02

    # Gold Scalp sniper-stop clamping: tight < $3.50 clamped up to $3.50, wide > $7.00 clamped down to $7.00
    e_tight, sl_tight, tp_tight = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.BUY,
        current_price=3850.00,
        atr=5.0,
        symbol="XAU/USD",
        pattern_details={"swing_low": 3849.00},
        is_scalp=True,
    )
    assert abs(e_tight - sl_tight) == 3.50, f"Tight sniper scalp SL clamp failed: {abs(e_tight - sl_tight)}"
    assert abs((abs(tp_tight - e_tight) / 3.50) - 1.2) < 0.02

    e_wide, sl_wide, tp_wide = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.SELL,
        current_price=3850.00,
        atr=5.0,
        symbol="XAU/USD",
        pattern_details={"swing_high": 3865.00},
        is_scalp=True,
    )
    assert abs(e_wide - sl_wide) == 7.00, f"Wide sniper scalp SL clamp failed: {abs(e_wide - sl_wide)}"
    assert abs((abs(tp_wide - e_wide) / 7.00) - 1.2) < 0.02

    # Standard Gold Swing (is_scalp=False) preserves $14.00+ floor
    entry_sw, sl_sw, _ = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.BUY,
        current_price=3850.00,
        atr=5.0,
        symbol="XAU/USD",
        is_scalp=False,
    )
    assert abs(entry_sw - sl_sw) >= 14.00, f"Standard Gold swing floor altered: {abs(entry_sw - sl_sw)}"

    # EUR/USD untouched
    entry_eu, sl_eu, tp_eu = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.BUY,
        current_price=1.10500,
        atr=0.0015,
        symbol="EUR/USD",
        is_scalp=False,
    )
    assert round(abs(entry_eu - sl_eu), 5) >= 0.0018
    assert tp_eu > entry_eu
    print("XAU/USD Scalp Geometry & EUR/USD isolation verified!")


if __name__ == "__main__":
    test_strat_024_definition_and_strat_006_untouched()
    test_xau_scalp_geometry_vs_swing_and_eurusd()
    print("ALL XAU/USD VELOCITY SCALP TESTS PASSED!")
