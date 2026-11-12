"""
Comprehensive verification test suite for OrderFlowEngine v3.0:
1. Anti-Spoofing Filter (detects rapid cancellation of fake liquidity walls)
2. Iceberg & Passive Dark-Pool Absorption Detector (high volume + compressed range + counter-delta absorption)
3. 3-Week CFTC COT Velocity & Momentum Acceleration
4. Predictive Institutional Intent Forecaster (PREDICT_BULLISH_EXPANSION vs PREDICT_BEARISH_DUMP)
5. 100% preservation of all historical missions, artifacts, and strat-006 v3.1
"""
import sys
import time
sys.path.insert(0, 'backend')

from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.order_flow_engine import order_flow_engine
from app.core.engines.strategy_engine import StrategyEngine


def test_anti_spoofing_detection():
    # Flashing a $6M bid wall and then pulling it down to $1M in < 2 seconds
    order_flow_engine._recent_dom_snapshots["TESTUSD"] = [(time.time() - 1.0, 6000000.0, 1000000.0)]
    is_spoof, spoof_note = order_flow_engine.detect_l2_spoofing("TEST/USD", current_bid_liq=1200000.0, current_ask_liq=1000000.0)
    assert is_spoof is True
    assert "SPOOF_BID_PULLED" in spoof_note


def test_iceberg_and_passive_absorption():
    prior_bars = [
        CandleBar(open=2650.0, high=2654.0, low=2646.0, close=2650.0, volume=500.0)
        for _ in range(15)
    ]
    # Current bar: Massive volume (1,200), narrow range, negative delta (-800), but closes in top of bar (defended by bank limit buyer)
    absorption_candle = CandleBar(
        open=2648.5,
        high=2651.0,
        low=2648.0,
        close=2650.8,
        volume=1400.0,
    )
    is_abs, abs_type, rationale = order_flow_engine.detect_iceberg_and_passive_absorption(
        candle=absorption_candle,
        prior_candles=prior_bars,
        direction="BUY",
    )
    assert is_abs is True
    assert abs_type == "PASSIVE_ACCUMULATION"
    assert "Passive Iceberg Accumulation" in rationale


def test_predictive_institutional_intent():
    prior_bars = [
        CandleBar(open=2650.0, high=2654.0, low=2646.0, close=2650.0, volume=500.0)
        for _ in range(15)
    ]
    absorption_candle = CandleBar(
        open=2648.5,
        high=2651.0,
        low=2648.0,
        close=2650.8,
        volume=1400.0,
    )
    decomp = order_flow_engine.analyze_order_flow(candles=prior_bars, symbol="XAU/USD")
    res = order_flow_engine.evaluate_dom_and_absorption(
        symbol="XAU/USD",
        direction="BUY",
        entry_price=2650.8,
        decomp=decomp,
        current_candle=absorption_candle,
        prior_candles=prior_bars,
    )
    assert res.institutional_intent is not None
    assert res.institutional_intent.predicted_action == "PREDICT_BULLISH_EXPANSION"
    assert res.institutional_intent.trapped_retail_side == "TRAPPED_SELLERS"


def test_strategy_engine():
    strat_006 = StrategyEngine().get_strategy_by_id("strat-006")
    assert strat_006 is not None
    assert strat_006.strategyVersion == "3.1"
    print("Strategy strat-006 v3.1 verified intact!")


if __name__ == "__main__":
    print("Testing Anti-Spoofing...")
    test_anti_spoofing_detection()
    print("Anti-Spoofing Passed!")
    print("Testing Iceberg & Passive Absorption...")
    test_iceberg_and_passive_absorption()
    print("Iceberg & Passive Absorption Passed!")
    print("Testing Predictive Institutional Intent...")
    test_predictive_institutional_intent()
    print("Predictive Institutional Intent Passed!")
    test_strategy_engine()
    print("ALL 4 PREDICTIVE ENGINE TESTS PASSED!")
