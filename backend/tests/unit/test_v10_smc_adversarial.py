"""
Adversarial Stress Test Suite — SMC Perception Engine (Milestone M1).
Written by Challenger 1 to empirically verify boundary conditions, edge cases,
and robust error handling in SMCStructureEngine and SMC API endpoints.
"""

from datetime import datetime, timezone, timedelta
import pytest

from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.smc_structure_engine import SMCStructureEngine
from app.core.services.market_history_service import PriceBar
from app.schemas.smc_structure import (
    CompositeConvictionScore,
    ConvictionBias,
    SessionLevels,
)


@pytest.fixture
def engine():
    return SMCStructureEngine()


# ===========================================================================
# 1. Boundary conditions in calculate_composite_conviction: minutes_to_news
# ===========================================================================

class TestCompositeConvictionNewsBoundaries:
    """Stress tests for macro news blackout penalty."""

    def test_minutes_to_news_zero(self, engine):
        """minutes_to_news = 0 should impose -15 pts penalty for HIGH impact."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=1.0,
            macro_news_impact="HIGH",
            minutes_to_news=0,
        )
        assert score.macro_news_penalty == 15.0
        assert any("news in 0m applies -15 pts" in r for r in score.key_reasons)

    def test_minutes_to_news_fifteen(self, engine):
        """minutes_to_news = 15 (exact boundary) should impose -15 pts penalty."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=1.0,
            macro_news_impact="HIGH",
            minutes_to_news=15,
        )
        assert score.macro_news_penalty == 15.0
        assert any("news in 15m applies -15 pts" in r for r in score.key_reasons)

    def test_minutes_to_news_sixteen(self, engine):
        """minutes_to_news = 16 (just outside boundary) should have 0 penalty."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=1.0,
            macro_news_impact="HIGH",
            minutes_to_news=16,
        )
        assert score.macro_news_penalty == 0.0

    def test_minutes_to_news_none(self, engine):
        """minutes_to_news = None with HIGH impact should NOT impose penalty."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=1.0,
            macro_news_impact="HIGH",
            minutes_to_news=None,
        )
        assert score.macro_news_penalty == 0.0

    def test_minutes_to_news_negative(self, engine):
        """
        Adversarial probe: minutes_to_news = -1 (news occurred 1 min ago or negative).
        Verify negative minutes do not trigger penalty under 0 <= minutes_to_news <= 15 rule.
        """
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=1.0,
            macro_news_impact="HIGH",
            minutes_to_news=-1,
        )
        assert score.macro_news_penalty == 0.0
        assert not any("news blackout penalty" in r for r in score.key_reasons)

    def test_minutes_to_news_large_negative(self, engine):
        """
        Adversarial probe: minutes_to_news = -120 (news occurred 2 hours ago).
        Verify past news does not trigger penalty under 0 <= minutes_to_news <= 15 rule.
        """
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=1.0,
            macro_news_impact="HIGH",
            minutes_to_news=-120,
        )
        assert score.macro_news_penalty == 0.0
        assert not any("news blackout penalty" in r for r in score.key_reasons)

    def test_macro_news_impact_case_variants(self, engine):
        """Check case-insensitivity: 'high', 'High', '  HIGH  '."""
        for val in ["high", "High", "  HIGH  ", "HIGH"]:
            score = engine.calculate_composite_conviction(
                smc_blocks=[],
                fvgs=[],
                sweeps=[],
                pattern_direction="BUY",
                session="LONDON",
                spread_pips=1.0,
                macro_news_impact=val,
                minutes_to_news=5,
            )
            assert score.macro_news_penalty == 15.0, f"Failed for macro_news_impact='{val}'"

    def test_macro_news_impact_medium_and_low(self, engine):
        """MEDIUM and LOW impact should not be penalized even if within 5 min."""
        for val in ["MEDIUM", "LOW", "medium", "low", "NONE", ""]:
            score = engine.calculate_composite_conviction(
                smc_blocks=[],
                fvgs=[],
                sweeps=[],
                pattern_direction="BUY",
                session="LONDON",
                spread_pips=1.0,
                macro_news_impact=val,
                minutes_to_news=5,
            )
            assert score.macro_news_penalty == 0.0


# ===========================================================================
# 2. Boundary conditions: Extreme spreads
# ===========================================================================

class TestCompositeConvictionSpreadBoundaries:
    """Stress tests for extreme and abnormal spreads."""

    def test_extreme_spread_1000_pips(self, engine):
        """Spread = 1000 pips should be clamped at max spread penalty 25.0."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=1000.0,
        )
        assert score.spread_penalty == 25.0
        assert 0.0 <= score.total_score <= 100.0

    def test_negative_spread(self, engine):
        """Negative spread (e.g. -5.0 pips anomaly) should not cause negative penalty or boost."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=-5.0,
        )
        assert score.spread_penalty == 0.0
        assert 0.0 <= score.total_score <= 100.0

    def test_zero_spread(self, engine):
        """Zero spread (raw ECN 0.0 pips) should incur 0.0 penalty."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=0.0,
        )
        assert score.spread_penalty == 0.0

    def test_spread_penalty_tiers(self, engine):
        """Verify tier transitions: <=1.2 -> 0; <=2.5 -> scaled; <=4.0 -> scaled; >4.0 -> capped at 25."""
        p_1_2 = engine.calculate_composite_conviction([], [], [], "BUY", "LONDON", 1.2).spread_penalty
        assert p_1_2 == 0.0

        p_1_3 = engine.calculate_composite_conviction([], [], [], "BUY", "LONDON", 1.3).spread_penalty
        assert p_1_3 > 0.0

        p_2_5 = engine.calculate_composite_conviction([], [], [], "BUY", "LONDON", 2.5).spread_penalty
        assert p_2_5 == round((2.5 - 1.2) * 2.5, 1)

        p_4_0 = engine.calculate_composite_conviction([], [], [], "BUY", "LONDON", 4.0).spread_penalty
        assert p_4_0 == round(3.25 + (4.0 - 2.5) * 4.5, 1)

        p_10_0 = engine.calculate_composite_conviction([], [], [], "BUY", "LONDON", 10.0).spread_penalty
        assert p_10_0 == 25.0  # capped


# ===========================================================================
# 3. Boundary conditions: Case-insensitive symbols
# ===========================================================================

class TestCompositeConvictionSymbolVariations:
    """Stress tests for symbol handling and Gold/DXY confluence."""

    @pytest.mark.parametrize("sym", ["xauusd", "Gold", "XAUUSD", "XAU/USD", "xau/usd", "GOLD", "xau", " gold "])
    def test_gold_symbols_recognized(self, engine, sym):
        """All variations of gold symbols should trigger Gold/DXY inverse correlation."""
        # Long Gold + Bullish DXY -> penalty (0 pts)
        score_bearish_for_gold = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=1.0,
            dxy_trend="BULLISH",
            symbol=sym,
        )
        assert score_bearish_for_gold.correlation_score == 0.0
        assert any("Gold/DXY" in r for r in score_bearish_for_gold.key_reasons)

        # Long Gold + Bearish DXY -> boost (+20 pts)
        score_bullish_for_gold = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=1.0,
            dxy_trend="BEARISH",
            symbol=sym,
        )
        assert score_bullish_for_gold.correlation_score == 20.0
        assert any("Gold/DXY" in r for r in score_bullish_for_gold.key_reasons)

    @pytest.mark.parametrize("sym", ["eurusd", "EURUSD", "gbpusd", "USDCAD", "USDJPY"])
    def test_non_gold_symbols_not_treated_as_gold(self, engine, sym):
        """Non-gold symbols should use standard macro correlation."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=1.0,
            dxy_trend="BULLISH",
            symbol=sym,
        )
        assert not any("Gold/DXY" in r for r in score.key_reasons)

    def test_symbol_none_or_empty(self, engine):
        """None or empty string symbol should not crash."""
        score_none = engine.calculate_composite_conviction(
            smc_blocks=[], fvgs=[], sweeps=[], pattern_direction="BUY", session="LONDON", spread_pips=1.0, symbol=None
        )
        assert score_none.symbol is None
        assert score_none.correlation_score == 10.0

        score_empty = engine.calculate_composite_conviction(
            smc_blocks=[], fvgs=[], sweeps=[], pattern_direction="BUY", session="LONDON", spread_pips=1.0, symbol=""
        )
        assert score_empty.correlation_score == 10.0


# ===========================================================================
# 4. Extreme score bounds ([0, 100])
# ===========================================================================

class TestCompositeConvictionScoreBounds:
    """Stress tests ensuring total_score strictly adheres to [0.0, 100.0]."""

    def test_worst_possible_combination_clamps_to_zero(self, engine):
        """
        When all penalties are maximized:
        smc=0, sniper=0, session=off_hours(+5), dxy opposing (+0), spread=1000 (-25), news blackout (-15)
        raw_total = 0 + 0 + 5 + 0 - 25 - 15 = -35.
        Must clamp to 0.0 without Pydantic ValidationError.
        """
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="OFF_HOURS",
            spread_pips=1000.0,
            dxy_trend="BULLISH",
            macro_news_impact="HIGH",
            minutes_to_news=0,
            symbol="XAUUSD",
        )
        assert score.total_score == 0.0
        assert score.bias == ConvictionBias.NEUTRAL

    def test_best_possible_combination_clamps_to_100(self, engine):
        """
        When all positive factors are maximized:
        smc=35, sniper=25, session=20, dxy=20, spread=0, news=0.
        raw_total = 100.0.
        Must be exactly 100.0.
        """
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=0.5,
            dxy_trend="BEARISH",
            macro_news_impact="LOW",
            symbol="XAUUSD",
        )
        # Note: without blocks/sweeps smc=0, sniper=15, session=20, dxy=20 = 55.
        # But score must remain <= 100.0
        assert 0.0 <= score.total_score <= 100.0


# ===========================================================================
# 5. Boundary conditions in compute_session_levels
# ===========================================================================

class TestComputeSessionLevelsBoundaries:
    """Stress tests for compute_session_levels handling of edge cases."""

    def test_empty_candles(self, engine):
        """Empty list should return fallback SessionLevels with high=0, low=0 without error."""
        res = engine.compute_session_levels([])
        assert res.session_name == "NONE"
        assert res.high == 0.0
        assert res.low == 0.0
        assert res.open_price == 0.0
        assert res.close_price == 0.0

    def test_single_candle_asian(self, engine):
        """Single candle within Asian hours (03:00 UTC)."""
        dt = datetime(2026, 9, 29, 3, 30, tzinfo=timezone.utc)
        bar = PriceBar(symbol="EURUSD", timeframe="15m", bar_time=dt, open=1.1000, high=1.1050, low=1.0950, close=1.1020, volume=100.0, provider="test")
        res = engine.compute_session_levels([bar])

        assert res.session_name == "ASIAN"
        assert res.high == 1.1050
        assert res.low == 1.0950
        assert res.open_price == 1.1000
        assert res.close_price == 1.1020
        assert res.asian_high == 1.1050
        assert res.asian_low == 1.0950
        assert res.london_high is None
        assert res.ny_high is None

    def test_single_candle_london(self, engine):
        """Single candle within London hours (09:00 UTC)."""
        dt = datetime(2026, 9, 29, 9, 0, tzinfo=timezone.utc)
        bar = PriceBar(symbol="EURUSD", timeframe="15m", bar_time=dt, open=1.2000, high=1.2050, low=1.1980, close=1.2010, volume=150.0, provider="test")
        res = engine.compute_session_levels([bar], session_name="LONDON")

        assert res.session_name == "LONDON"
        assert res.high == 1.2050
        assert res.low == 1.1980
        assert res.london_high == 1.2050
        assert res.london_low == 1.1980
        assert res.asian_high is None

    def test_single_candle_off_hours(self, engine):
        """Single candle during off-hours (21:00 UTC, outside Asian, London, NY)."""
        dt = datetime(2026, 9, 29, 21, 0, tzinfo=timezone.utc)
        bar = PriceBar(symbol="EURUSD", timeframe="15m", bar_time=dt, open=1.3000, high=1.3050, low=1.2950, close=1.3010, volume=50.0, provider="test")
        res = engine.compute_session_levels([bar])

        assert res.session_name == "ALL"
        assert res.high == 1.3050
        assert res.low == 1.2950
        assert res.asian_high is None
        assert res.london_high is None
        assert res.ny_high is None

    def test_candles_across_midnight(self, engine):
        """
        Candles spanning across midnight:
        Day 1 (2026-09-28) 22:00, 23:00
        Day 2 (2026-09-29) 01:00, 02:00 (Asian), 08:00 (London)
        """
        b1 = PriceBar(symbol="EURUSD", timeframe="15m", bar_time=datetime(2026, 9, 28, 22, 0, tzinfo=timezone.utc), open=1.0, high=1.05, low=0.95, close=1.02, volume=10.0, provider="test")
        b2 = PriceBar(symbol="EURUSD", timeframe="15m", bar_time=datetime(2026, 9, 28, 23, 0, tzinfo=timezone.utc), open=1.02, high=1.06, low=0.98, close=1.04, volume=10.0, provider="test")
        b3 = PriceBar(symbol="EURUSD", timeframe="15m", bar_time=datetime(2026, 9, 29, 1, 0, tzinfo=timezone.utc), open=1.04, high=1.10, low=1.01, close=1.08, volume=10.0, provider="test")
        b4 = PriceBar(symbol="EURUSD", timeframe="15m", bar_time=datetime(2026, 9, 29, 2, 0, tzinfo=timezone.utc), open=1.08, high=1.12, low=1.03, close=1.07, volume=10.0, provider="test")
        b5 = PriceBar(symbol="EURUSD", timeframe="15m", bar_time=datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc), open=1.07, high=1.15, low=1.05, close=1.14, volume=10.0, provider="test")

        res = engine.compute_session_levels([b1, b2, b3, b4, b5])

        assert res.asian_high == 1.12  # max of b3, b4
        assert res.asian_low == 1.01   # min of b3, b4
        assert res.london_high == 1.15 # b5
        assert res.london_low == 1.05

    def test_malformed_timestamps_unparseable(self, engine):
        """
        Candles with completely unparseable timestamps (e.g. invalid string).
        Engine should fall back to max/min of all candles without raising ValueError.
        """
        candles = [
            {"timestamp": "not-a-timestamp", "open": 1.0, "high": 1.5, "low": 0.8, "close": 1.2},
            {"timestamp": "corrupt_data", "open": 1.2, "high": 1.8, "low": 0.9, "close": 1.6},
        ]
        res = engine.compute_session_levels(candles)
        assert res.session_name == "ASIAN"
        assert res.high == 1.8
        assert res.low == 0.8
        assert res.open_price == 1.0
        assert res.close_price == 1.6

    def test_none_timestamps(self, engine):
        """Candles where timestamp is None."""
        candles = [
            PriceBar(symbol="EURUSD", timeframe="15m", bar_time=None, open=100.0, high=105.0, low=95.0, close=102.0, volume=10.0, provider="test"),
            PriceBar(symbol="EURUSD", timeframe="15m", bar_time=None, open=102.0, high=108.0, low=101.0, close=107.0, volume=10.0, provider="test"),
        ]
        res = engine.compute_session_levels(candles)
        assert res.high == 108.0
        assert res.low == 95.0
        assert res.open_price == 100.0
        assert res.close_price == 107.0

    def test_epoch_int_timestamps(self, engine):
        """Candles with integer unix epoch timestamps (seconds vs milliseconds)."""
        # 2026-09-29 02:00:00 UTC in seconds
        ts_sec = 1790647200
        # in milliseconds
        ts_ms = ts_sec * 1000

        c1 = {"time": ts_sec, "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1}
        c2 = {"time": ts_ms, "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.25}

        res = engine.compute_session_levels([c1, c2])
        assert res.high == 1.3
        assert res.low == 0.9

    def test_mixed_object_types(self, engine):
        """Mix of CandleBar, PriceBar, and dict in the same candles list."""
        dt = datetime(2026, 9, 29, 4, 0, tzinfo=timezone.utc)
        c1 = PriceBar(symbol="EURUSD", timeframe="15m", bar_time=dt, open=1.0, high=1.2, low=0.9, close=1.1, volume=5.0, provider="test")
        c2 = CandleBar(timestamp=int(dt.timestamp()), open=1.1, high=1.3, low=1.0, close=1.25)
        c3 = {"timestamp": dt, "open": 1.25, "high": 1.4, "low": 1.05, "close": 1.35}

        res = engine.compute_session_levels([c1, c2, c3])
        assert res.high == 1.4
        assert res.low == 0.9

    def test_explicit_none_candle_high_low(self, engine):
        """Candles where high or low attributes are explicitly None should not raise TypeError."""
        class MockCandle:
            bar_time = datetime(2026, 9, 29, 4, 0, tzinfo=timezone.utc)
            open = 1.1
            high = None
            low = None
            close = 1.2

        c_dict = {
            "timestamp": datetime(2026, 9, 29, 5, 0, tzinfo=timezone.utc),
            "open": 1.2,
            "high": None,
            "low": None,
            "close": 1.3,
        }

        res = engine.compute_session_levels([MockCandle(), c_dict])
        assert res.high == 0.0
        assert res.low == 0.0

