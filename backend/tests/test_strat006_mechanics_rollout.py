"""
Verification test suite for extending strat-006 Corridor, Retest & Whipsaw mechanics
across intraday strategies while keeping EUR/USD (strat-006) and XAU/USD Velocity Scalp (strat-024) untouched:
1. Retest-Price Entry Framing & Opposite-Corridor Structural Stop (_resolve_corridor_retest_and_stop)
2. Double-Break Whipsaw Detection (Asian BROKEN_UP & London BROKEN_DOWN simultaneously)
3. Exact isolation of strat-006 (EUR/USD v3.1) and strat-024 (XAU/USD Velocity Scalp v3.2)
"""
import sys
from datetime import datetime, timezone
sys.path.insert(0, "backend")

from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.session_breakout_engine import session_breakout_engine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.schemas.session_breakout import SessionStatus
from app.schemas.signal_candidate import CandidateDirection
from app.schemas.strategy import RiskLevel, StrategyCategory


def _bar(hour: int, o: float, h: float, l: float, c: float, vol: float = 1000.0) -> CandleBar:
    dt = datetime(2026, 11, 17, hour, 0, tzinfo=timezone.utc)
    return CandleBar(open=o, high=h, low=l, close=c, volume=vol, timestamp=int(dt.timestamp()), time=dt)


def test_retest_entry_framing_and_opposite_corridor_stop():
    # Construct Asian corridor (00:00 - 06:00 UTC): low = 1.32100, high = 1.32350 (25 pips)
    # Followed by London breakout bar at 08:00 UTC closing at 1.32480 (13 pips above Asian High)
    candles = [
        _bar(1, 1.3220, 1.3230, 1.3215, 1.3225),
        _bar(3, 1.3225, 1.3235, 1.3210, 1.3230),
        _bar(5, 1.3230, 1.3232, 1.3218, 1.3228),
        _bar(8, 1.3232, 1.3252, 1.3230, 1.3248, vol=2500.0),
    ]
    framed_entry, struct_sl, note = SignalGenerationEngine._resolve_corridor_retest_and_stop(
        symbol="GBPUSD",
        direction=CandidateDirection.BUY,
        entry_price=1.32480,
        candles=candles,
        atr_val=0.0030,  # 30 pips ATR -> max_cap = 2.5 * 30 = 75 pips
        min_dist=0.0018,
        pip_u=0.0001,
        dec_p=5,
    )
    # Retest price should frame entry at Asian High (1.32350) instead of chasing 1.32480
    assert framed_entry == 1.32350, f"Expected retest framing at 1.32350, got {framed_entry}"
    # Opposite-Corridor SL should anchor 2 pips below Asian Low (1.32100 - 0.00020 = 1.32080)
    assert struct_sl == 1.32080, f"Expected opposite-corridor SL at 1.32080, got {struct_sl}"
    assert note is not None and "Opposite-Corridor SL" in note
    print(f"Retest Framing ({framed_entry}) & Opposite-Corridor SL ({struct_sl}) verified!")


def test_double_break_whipsaw_detection():
    # Asian range (01:00 - 05:00): [1.3210, 1.3230]
    # London range (07:00 - 09:00): [1.3240, 1.3280]
    # Latest bar (12:00) at 1.3235 -> above Asian High (BROKEN_UP) AND below London Low (BROKEN_DOWN)!
    candles = [
        _bar(1, 1.3215, 1.3230, 1.3210, 1.3225),
        _bar(5, 1.3220, 1.3228, 1.3212, 1.3225),
        _bar(7, 1.3245, 1.3280, 1.3240, 1.3270),
        _bar(12, 1.3265, 1.3270, 1.3230, 1.3235),
    ]
    corridors = session_breakout_engine.compute_session_corridors("GBPUSD", candles, allow_benchmark=False)
    broken_up = any(c.status == SessionStatus.BROKEN_UP for c in corridors)
    broken_down = any(c.status == SessionStatus.BROKEN_DOWN for c in corridors)
    assert broken_up and broken_down, "Expected simultaneous BROKEN_UP and BROKEN_DOWN whipsaw condition"
    print("Double-break whipsaw detection verified!")


def test_scalp_strategies_strictly_untouched():
    engine = StrategyEngine()
    s06 = engine.get_strategy_by_id("strat-006")
    assert s06 is not None
    assert s06.symbol == "EUR/USD"
    assert s06.category == StrategyCategory.SCALPING
    assert s06.strategyVersion == "3.1"

    s24 = engine.get_strategy_by_id("strat-024")
    assert s24 is not None
    assert s24.symbol == "XAU/USD"
    assert s24.category == StrategyCategory.SCALPING
    assert s24.minimumRiskReward == 1.2
    assert s24.riskLevel == RiskLevel.MEDIUM

    # Ensure strat-024 tight scalp geometry ($3.50-$7.00 SL, 1.2R TP) unaffected
    e, sl, tp = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.BUY,
        current_price=3850.00,
        atr=5.0,
        symbol="XAU/USD",
        is_scalp=True,
    )
    assert 3.50 <= abs(e - sl) <= 7.00
    assert abs((abs(tp - e) / abs(e - sl)) - 1.2) < 0.02
    print("strat-006 (EUR/USD) & strat-024 (XAU/USD) isolation verified!")


if __name__ == "__main__":
    test_retest_entry_framing_and_opposite_corridor_stop()
    test_double_break_whipsaw_detection()
    test_scalp_strategies_strictly_untouched()
    print("ALL STRAT-006 MECHANICS ROLLOUT TESTS PASSED!")
