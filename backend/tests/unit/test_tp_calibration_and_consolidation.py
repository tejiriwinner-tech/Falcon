import pytest
from datetime import datetime, time as dt_time, timezone, timedelta
from app.schemas.signal_candidate import CandidateDirection
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.session_breakout_engine import SessionBreakoutEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.schemas.strategy import StrategyStatus


def test_signal_generation_engine_calibrated_atr_and_rr():
    """Verify stop loss scales to 1.0x ATR and eff_rr floor is 1.5R."""
    # Test EURUSD with 0.0020 ATR (20 pips)
    current_price = 1.1000
    atr = 0.0020

    entry, sl, tp = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.BUY,
        current_price=current_price,
        atr=atr,
        symbol="EURUSD",
        rr=1.5,
    )

    # 1.0 * ATR = 0.0020. SL = 1.09800
    assert abs(sl - 1.09800) < 1e-4
    # Risk = 0.0020. TP at 1.5R = 1.10300
    assert abs(tp - 1.10300) < 1e-4

    # Test Gold with $10 ATR
    gold_price = 2650.00
    gold_atr = 10.00
    entry_g, sl_g, tp_g = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.BUY,
        current_price=gold_price,
        atr=gold_atr,
        symbol="XAUUSD",
        rr=1.5,
    )
    # 1.0 * ATR = $10.00. SL = $2640.00
    assert abs(sl_g - 2640.00) < 1e-2
    # 1.5R = $15.00. TP = $2665.00
    assert abs(tp_g - 2665.00) < 1e-2


def test_session_breakout_engine_tp1_and_tp2_levels():
    """Verify TP1 is calibrated to +1.0R and TP2 is calibrated to +1.5R."""
    engine = SessionBreakoutEngine()
    entry = 1.3000
    effective_risk = 0.0030
    structure_sl = entry - effective_risk  # 1.2970

    sl, tp1, tp2, trail_buf, atr = engine.calculate_trade_levels(
        symbol="GBPUSD",
        direction="BUY",
        entry_price=entry,
        candles=[],
        structure_sl=structure_sl,
    )

    # Effective risk = 0.0030
    # TP1 (+1.0R) = 1.3030
    assert abs(tp1 - (entry + effective_risk)) < 1e-4
    # TP2 (+1.5R) = 1.3045
    assert abs(tp2 - (entry + 1.5 * effective_risk)) < 1e-4


def test_strategy_consolidation_active_vs_incubation():
    """Verify exactly 6 flagships are ACTIVE and the 12 other strategies are in INCUBATION."""
    engine = StrategyEngine()
    flagship_ids = {"strat-004", "strat-007", "strat-012", "strat-013", "strat-016", "strat-017"}

    active_count = 0
    incubation_count = 0

    for s in engine._strategies:
        if s.id in flagship_ids:
            assert s.status == StrategyStatus.ACTIVE, f"{s.id} should be ACTIVE"
            assert s.readyForExecution is True, f"{s.id} should be readyForExecution"
            assert s.minimumRiskReward <= 1.8, f"{s.id} minimumRiskReward should be <= 1.8"
            active_count += 1
        else:
            assert s.status == StrategyStatus.INCUBATION, f"{s.id} should be in INCUBATION"
            assert s.readyForExecution is False, f"{s.id} should not be readyForExecution"
            incubation_count += 1

    assert active_count == 6
    assert incubation_count == 12
    assert len(engine._strategies) == 18
