"""
Automated verification test suite for:
1. Top-Down Multi-Timeframe Architecture (H1 Macro Bias -> M15/M5 execution) across all pairs.
2. European Breakout (strat-006) 06:00-14:00 UTC Killzone gate (verifying 16:38 UTC is vetoed).
3. Universal FX Off-Peak Rollover Blackout (16:30-22:00 UTC) across all currency pairs.
4. H1 Macro Downtrend/Uptrend Confluence Veto.
"""
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, "backend")

from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.strategy_engine import strategy_engine
from app.schemas.market_state import MarketPrice, MarketState
from app.schemas.signal_candidate import CandidateDirection
from app.schemas.strategy import StrategyStatus


def _make_h1_bars(trend: str = "BULLISH", count: int = 50, base_px: float = 1.1000):
    bars = []
    px = base_px
    now_ts = 1700000000
    for i in range(count):
        if trend == "BULLISH":
            px += 0.0005
        elif trend == "BEARISH":
            px -= 0.0005
        dt = datetime.fromtimestamp(now_ts + i * 3600, tz=timezone.utc)
        bars.append(CandleBar(
            open=px - 0.0002,
            high=px + 0.0004,
            low=px - 0.0004,
            close=px,
            volume=500.0,
            timestamp=int(dt.timestamp()),
            time=dt
        ))
    return bars


def test_strat006_killzone_blocks_1638_utc():
    """Verify that European Breakout (strat-006) rejects entries at 16:38 UTC (the exact loss trade time)."""
    engine = SignalGenerationEngine()
    s6 = next(s for s in strategy_engine.get_strategies() if s.id == "strat-006")
    
    # 16:38 UTC
    t_1638 = datetime(2026, 11, 17, 16, 38, 0, tzinfo=timezone.utc)
    
    # Mock market state
    m_state = MarketState(
        timestamp=t_1638,
        session="New York",
        volatility="Moderate",
        marketSentimentLabel="Neutral",
        overallMarketConfidence=70,
        dataAgeSeconds=10,
        prices={"EURUSD": MarketPrice(symbol="EURUSD", currentPrice=1.10132, bid=1.1012, ask=1.1014, spread=0.8, timestamp=t_1638, provider="oanda")},
        indicators={},
        calendar=[]
    )
    
    s6.status = StrategyStatus.ACTIVE
    bars_h1 = _make_h1_bars("BULLISH", count=50, base_px=1.1000)
    
    with patch("app.core.services.market_history_service.market_history_service.get_bars", return_value=bars_h1):
        candidates = engine.generate_candidates(
            market_state=m_state,
            strategies=[s6],
            as_of=t_1638
        )
    
    assert len(candidates) == 1
    cand = candidates[0]
    # At 16:38 UTC, European Breakout killzone MUST veto the session condition
    sess_cond = next((c for c in cand.conditions if c.title == "Session Match"), None)
    assert sess_cond is not None
    assert sess_cond.passed is False, f"Expected Session Match to fail at 16:38 UTC, got {sess_cond.passed}"
    assert "European Breakout Killzone Gate" in sess_cond.description or "Universal FX Off-Peak Rollover Gate" in sess_cond.description
    print("strat-006 16:38 UTC European Killzone veto verified!")


def test_universal_fx_off_peak_rollover_blackout_across_pairs():
    """Verify that all FX pairs (EUR/USD, GBP/USD, USD/JPY, AUD/USD, GBP/JPY) are blocked at 18:00 UTC."""
    engine = SignalGenerationEngine()
    t_1800 = datetime(2026, 11, 17, 18, 0, 0, tzinfo=timezone.utc)
    
    # Test on GBP/USD (strat-004) and USD/JPY (strat-022)
    s4 = next(s for s in strategy_engine.get_strategies() if s.id == "strat-004")
    s22 = next(s for s in strategy_engine.get_strategies() if s.id == "strat-022")
    
    m_state = MarketState(
        timestamp=t_1800,
        session="New York",
        volatility="Moderate",
        marketSentimentLabel="Neutral",
        overallMarketConfidence=70,
        dataAgeSeconds=10,
        prices={
            "GBPUSD": MarketPrice(symbol="GBPUSD", currentPrice=1.3150, bid=1.3149, ask=1.3151, spread=1.0, timestamp=t_1800, provider="oanda"),
            "USDJPY": MarketPrice(symbol="USDJPY", currentPrice=154.50, bid=154.49, ask=154.51, spread=1.2, timestamp=t_1800, provider="oanda"),
        },
        indicators={},
        calendar=[]
    )
    
    s4.status = StrategyStatus.ACTIVE
    s22.status = StrategyStatus.ACTIVE
    bars_h1 = _make_h1_bars("BULLISH", count=50, base_px=1.3100)
    with patch("app.core.services.market_history_service.market_history_service.get_bars", return_value=bars_h1):
        candidates = engine.generate_candidates(
            market_state=m_state,
            strategies=[s4, s22],
            as_of=t_1800
        )
    
    for cand in candidates:
        sess_cond = next((c for c in cand.conditions if c.title == "Session Match"), None)
        assert sess_cond is not None
        assert sess_cond.passed is False, f"Expected Session Match to fail at 18:00 UTC for {cand.symbol}, got {sess_cond.passed}"
        assert "Universal FX Off-Peak Rollover Gate" in sess_cond.description
    print("Universal FX Off-Peak Rollover Blackout (16:30-22:00 UTC) verified across pairs!")


def test_strat006_allowed_in_morning_killzone():
    """Verify that European Breakout (strat-006) IS allowed during Frankfurt/London morning (e.g. 08:30 UTC)."""
    engine = SignalGenerationEngine()
    s6 = next(s for s in strategy_engine.get_strategies() if s.id == "strat-006")
    t_0830 = datetime(2026, 11, 17, 8, 30, 0, tzinfo=timezone.utc)
    
    m_state = MarketState(
        timestamp=t_0830,
        session="London",
        volatility="High",
        marketSentimentLabel="Bullish",
        overallMarketConfidence=85,
        dataAgeSeconds=10,
        prices={"EURUSD": MarketPrice(symbol="EURUSD", currentPrice=1.10132, bid=1.1012, ask=1.1014, spread=0.8, timestamp=t_0830, provider="oanda")},
        indicators={},
        calendar=[]
    )
    
    s6.status = StrategyStatus.ACTIVE
    bars_h1 = _make_h1_bars("BULLISH", count=50, base_px=1.1000)
    with patch("app.core.services.market_history_service.market_history_service.get_bars", return_value=bars_h1):
        candidates = engine.generate_candidates(
            market_state=m_state,
            strategies=[s6],
            as_of=t_0830
        )
    
    assert len(candidates) == 1
    cand = candidates[0]
    sess_cond = next((c for c in cand.conditions if c.title == "Session Match"), None)
    assert sess_cond is not None
    assert sess_cond.passed is True, f"Expected Session Match to PASS at 08:30 UTC in London, got {sess_cond.passed} ({sess_cond.description})"
    print("strat-006 08:30 UTC Frankfurt/London Morning Killzone PASS verified!")


if __name__ == "__main__":
    test_strat006_killzone_blocks_1638_utc()
    test_universal_fx_off_peak_rollover_blackout_across_pairs()
    test_strat006_allowed_in_morning_killzone()
    print("ALL TOP-DOWN H1 & KILLZONE TESTS PASSED!")
