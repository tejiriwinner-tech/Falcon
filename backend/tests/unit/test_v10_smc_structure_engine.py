"""
Falcon V10 Unit Tests — Pillar 1: SMC Institutional Perception Engine.

Tests:
1. Order Block Detection & Mitigation:
   - Bullish Order Block detection (last opposing candle before displacement breaking swing high)
   - Bullish Order Block mitigation state tracking (unmitigated vs re-entered)
   - Bearish Order Block detection (last opposing candle before displacement breaking swing low)
   - Bearish Order Block mitigation state tracking (unmitigated vs re-entered)
   - Boundary conditions (too few candles, flat candles, no BOS, deduplication)

2. Fair Value Gap (FVG) Detection & Mitigation:
   - Bullish FVG (3-bar sequence: Bar 1 High < Bar 3 Low)
   - Bearish FVG (3-bar sequence: Bar 1 Low > Bar 3 High)
   - Top, bottom, and size_pips across FX (EURUSD) and Gold (XAUUSD)
   - FVG mitigation tracking (unmitigated vs re-entered)
   - Overlapping candles (no FVG) and boundary conditions (<3 bars)

3. Session Liquidity Sweeps:
   - Asian High swept during London Open, closing back inside (HIGH_SWEEP)
   - Asian Low swept during London Open, closing back inside (LOW_SWEEP)
   - Breakout candle closing outside (not a sweep)
   - Normal candle contained within session (not a sweep)
   - Boundary conditions (empty candles, None session)

4. Composite Conviction Score Calculation:
   - Full confluence bullish setup (Bullish OB + FVG + Low Sweep + London + DXY Bearish + tight spread)
   - Full confluence bearish setup (Bearish OB + FVG + High Sweep + NY + DXY Bullish + tight spread)
   - Macro DXY correlation variations (aligned, conflicting, neutral/unassigned)
   - Session timing killzones (London, NY, Asian, off-hours)
   - Spread penalty scaling (tight, moderate, elevated, wide)
   - Contradicting structure penalty
   - Neutral / empty inputs baseline
   - Mathematical boundary assertions (all sub-scores and total in [0, 100])

5. Schema Invariants & Property Helpers:
   - OrderBlock, FairValueGap, LiquiditySweep, SessionLevels, CompositeConvictionScore
"""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.api import api_router
from app.api.v1.smc import router as smc_router
from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.smc_structure_engine import SMCStructureEngine, _get_pip_size
from app.core.services.market_history_service import PriceBar, market_history_service
from app.schemas.smc_structure import (
    CompositeConvictionScore,
    ConvictionBias,
    FairValueGap,
    FairValueGapType,
    LiquiditySweep,
    OrderBlock,
    OrderBlockType,
    SessionLevels,
    SMCStructureResponse,
    SMCSweepsResponse,
    SweepType,
)


@pytest.fixture
def engine() -> SMCStructureEngine:
    """Provides a fresh SMCStructureEngine instance."""
    return SMCStructureEngine()


# ============================================================================
# 1. ORDER BLOCK DETECTION & MITIGATION TESTS
# ============================================================================

class TestOrderBlockDetection:
    """Verifies Bullish and Bearish Order Block algorithmic detection and mitigation tracking."""

    def test_bullish_order_block_detection_unmitigated(self, engine: SMCStructureEngine):
        """
        Tests detection of a Bullish Order Block that remains unmitigated.
        Structure:
        - c0: Base candle (100 -> 101)
        - c1: Swing High (101 -> 105, High=106)
        - c2: Opposing Bearish candle (105 -> 102, High=105, Low=102) -> BULLISH OB
        - c3: Bullish displacement breaking c1 high (102 -> 107, High=108, Close=107 > 106)
        - c4: Continuation candle staying above OB (107 -> 108, Low=106 > 105)
        """
        c0 = CandleBar(open=100.0, high=102.0, low=99.0, close=101.0, timestamp=1000)
        c1 = CandleBar(open=101.0, high=106.0, low=100.0, close=105.0, timestamp=1001)
        c2 = CandleBar(open=105.0, high=105.0, low=102.0, close=102.0, timestamp=1002)
        c3 = CandleBar(open=102.0, high=108.0, low=102.0, close=107.0, timestamp=1003)
        c4 = CandleBar(open=107.0, high=109.0, low=106.0, close=108.0, timestamp=1004)

        candles = [c0, c1, c2, c3, c4]
        obs = engine.detect_order_blocks(candles, symbol="EURUSD", timeframe="15m")

        assert len(obs) == 1
        ob = obs[0]
        assert ob.symbol == "EURUSD"
        assert ob.timeframe == "15m"
        assert ob.block_type == OrderBlockType.BULLISH
        assert ob.is_bullish is True
        assert ob.is_bearish is False
        assert ob.high == 105.0
        assert ob.low == 102.0
        assert ob.open_price == 105.0
        assert ob.close_price == 102.0
        assert ob.is_mitigated is False
        assert ob.formed_at == 1002

    def test_bullish_order_block_mitigated(self, engine: SMCStructureEngine):
        """
        Tests that when subsequent price action re-enters the OB range (Low <= OB.high),
        is_mitigated transitions to True.
        """
        c0 = CandleBar(open=100.0, high=102.0, low=99.0, close=101.0, timestamp=1000)
        c1 = CandleBar(open=101.0, high=106.0, low=100.0, close=105.0, timestamp=1001)
        c2 = CandleBar(open=105.0, high=105.0, low=102.0, close=102.0, timestamp=1002)
        c3 = CandleBar(open=102.0, high=108.0, low=102.0, close=107.0, timestamp=1003)
        c4 = CandleBar(open=107.0, high=109.0, low=106.0, close=108.0, timestamp=1004)
        # c5 pulls back into the OB: Low=104.0 <= OB High (105.0)
        c5 = CandleBar(open=108.0, high=108.0, low=104.0, close=105.0, timestamp=1005)

        candles = [c0, c1, c2, c3, c4, c5]
        obs = engine.detect_order_blocks(candles, symbol="EURUSD", timeframe="15m")

        assert len(obs) == 1
        assert obs[0].is_mitigated is True

    def test_bearish_order_block_detection_unmitigated(self, engine: SMCStructureEngine):
        """
        Tests detection of a Bearish Order Block that remains unmitigated.
        Structure:
        - c0: Base candle (105 -> 105)
        - c1: Swing Low (105 -> 101, Low=100)
        - c2: Opposing Bullish candle (101 -> 103, High=103, Low=101) -> BEARISH OB
        - c3: Bearish displacement breaking c1 low (103 -> 98, Low=98, Close=98 < 100)
        - c4: Continuation candle staying below OB (98 -> 97, High=99 < 101)
        """
        c0 = CandleBar(open=105.0, high=106.0, low=104.0, close=105.0, timestamp=1000)
        c1 = CandleBar(open=105.0, high=105.0, low=100.0, close=101.0, timestamp=1001)
        c2 = CandleBar(open=101.0, high=103.0, low=101.0, close=103.0, timestamp=1002)
        c3 = CandleBar(open=103.0, high=103.0, low=98.0, close=98.0, timestamp=1003)
        c4 = CandleBar(open=98.0, high=99.0, low=97.0, close=97.0, timestamp=1004)

        candles = [c0, c1, c2, c3, c4]
        obs = engine.detect_order_blocks(candles, symbol="EURUSD", timeframe="15m")

        assert len(obs) == 1
        ob = obs[0]
        assert ob.symbol == "EURUSD"
        assert ob.timeframe == "15m"
        assert ob.block_type == OrderBlockType.BEARISH
        assert ob.is_bearish is True
        assert ob.is_bullish is False
        assert ob.high == 103.0
        assert ob.low == 101.0
        assert ob.open_price == 101.0
        assert ob.close_price == 103.0
        assert ob.is_mitigated is False
        assert ob.formed_at == 1002

    def test_bearish_order_block_mitigated(self, engine: SMCStructureEngine):
        """
        Tests that when subsequent price action re-enters the Bearish OB range (High >= OB.low),
        is_mitigated transitions to True.
        """
        c0 = CandleBar(open=105.0, high=106.0, low=104.0, close=105.0, timestamp=1000)
        c1 = CandleBar(open=105.0, high=105.0, low=100.0, close=101.0, timestamp=1001)
        c2 = CandleBar(open=101.0, high=103.0, low=101.0, close=103.0, timestamp=1002)
        c3 = CandleBar(open=103.0, high=103.0, low=98.0, close=98.0, timestamp=1003)
        c4 = CandleBar(open=98.0, high=99.0, low=97.0, close=97.0, timestamp=1004)
        # c5 rallies into the OB: High=102.0 >= OB Low (101.0)
        c5 = CandleBar(open=97.0, high=102.0, low=97.0, close=100.0, timestamp=1005)

        candles = [c0, c1, c2, c3, c4, c5]
        obs = engine.detect_order_blocks(candles, symbol="EURUSD", timeframe="15m")

        assert len(obs) == 1
        assert obs[0].is_mitigated is True

    def test_order_block_edge_cases(self, engine: SMCStructureEngine):
        """Tests insufficient candles (<3), flat candles, and no structure break."""
        # Insufficient candles
        assert engine.detect_order_blocks([], "EURUSD", "5m") == []
        c1 = CandleBar(open=100.0, high=101.0, low=99.0, close=100.0)
        c2 = CandleBar(open=100.0, high=101.0, low=99.0, close=100.0)
        assert engine.detect_order_blocks([c1, c2], "EURUSD", "5m") == []

        # Flat candles (no swing points, no breaks)
        flat_candles = [CandleBar(open=100.0, high=100.5, low=99.5, close=100.0) for _ in range(10)]
        assert engine.detect_order_blocks(flat_candles, "EURUSD", "5m") == []


# ============================================================================
# 2. FAIR VALUE GAP DETECTION & MITIGATION TESTS
# ============================================================================

class TestFairValueGapDetection:
    """Verifies Bullish and Bearish Fair Value Gap (FVG) detection and mitigation."""

    def test_bullish_fvg_detection_unmitigated(self, engine: SMCStructureEngine):
        """
        Tests 3-bar sequence where Bar 1 High < Bar 3 Low (Bullish FVG).
        Subsequent candle remains above top boundary (unmitigated).
        """
        b1 = CandleBar(open=1.0800, high=1.0820, low=1.0795, close=1.0810, timestamp=1000)
        b2 = CandleBar(open=1.0810, high=1.0890, low=1.0805, close=1.0885, timestamp=1001)
        b3 = CandleBar(open=1.0885, high=1.0920, low=1.0850, close=1.0910, timestamp=1002)
        # b4 stays above FVG top (1.0850)
        b4 = CandleBar(open=1.0910, high=1.0950, low=1.0880, close=1.0940, timestamp=1003)

        fvgs = engine.detect_fair_value_gaps([b1, b2, b3, b4], symbol="EURUSD", timeframe="15m")

        assert len(fvgs) == 1
        fvg = fvgs[0]
        assert fvg.symbol == "EURUSD"
        assert fvg.timeframe == "15m"
        assert fvg.gap_type == FairValueGapType.BULLISH
        assert fvg.is_bullish is True
        assert fvg.is_bearish is False
        assert fvg.top == 1.0850
        assert fvg.bottom == 1.0820
        assert fvg.size_pips == 30.0  # (1.0850 - 1.0820) / 0.0001
        assert fvg.is_mitigated is False
        assert fvg.bar1_time == 1000
        assert fvg.bar3_time == 1002

    def test_bullish_fvg_mitigated(self, engine: SMCStructureEngine):
        """
        Tests that when subsequent candle dips into the gap (Low <= FVG.top),
        is_mitigated is set to True.
        """
        b1 = CandleBar(open=1.0800, high=1.0820, low=1.0795, close=1.0810, timestamp=1000)
        b2 = CandleBar(open=1.0810, high=1.0890, low=1.0805, close=1.0885, timestamp=1001)
        b3 = CandleBar(open=1.0885, high=1.0920, low=1.0850, close=1.0910, timestamp=1002)
        b4 = CandleBar(open=1.0910, high=1.0950, low=1.0880, close=1.0940, timestamp=1003)
        # b5 retraces into the gap: Low=1.0840 <= top (1.0850)
        b5 = CandleBar(open=1.0940, high=1.0940, low=1.0840, close=1.0860, timestamp=1004)

        fvgs = engine.detect_fair_value_gaps([b1, b2, b3, b4, b5], symbol="EURUSD", timeframe="15m")

        assert len(fvgs) == 1
        assert fvgs[0].is_mitigated is True

    def test_bearish_fvg_detection_unmitigated(self, engine: SMCStructureEngine):
        """
        Tests 3-bar sequence where Bar 1 Low > Bar 3 High (Bearish FVG).
        Subsequent candle remains below bottom boundary (unmitigated).
        """
        b1 = CandleBar(open=1.0900, high=1.0910, low=1.0880, close=1.0890, timestamp=1000)
        b2 = CandleBar(open=1.0890, high=1.0895, low=1.0810, close=1.0815, timestamp=1001)
        b3 = CandleBar(open=1.0815, high=1.0850, low=1.0780, close=1.0790, timestamp=1002)
        # b4 stays below FVG bottom (1.0850)
        b4 = CandleBar(open=1.0790, high=1.0820, low=1.0770, close=1.0780, timestamp=1003)

        fvgs = engine.detect_fair_value_gaps([b1, b2, b3, b4], symbol="EURUSD", timeframe="15m")

        assert len(fvgs) == 1
        fvg = fvgs[0]
        assert fvg.symbol == "EURUSD"
        assert fvg.timeframe == "15m"
        assert fvg.gap_type == FairValueGapType.BEARISH
        assert fvg.is_bearish is True
        assert fvg.is_bullish is False
        assert fvg.top == 1.0880
        assert fvg.bottom == 1.0850
        assert fvg.size_pips == 30.0
        assert fvg.is_mitigated is False
        assert fvg.bar1_time == 1000
        assert fvg.bar3_time == 1002

    def test_bearish_fvg_mitigated(self, engine: SMCStructureEngine):
        """
        Tests that when subsequent candle rallies into the gap (High >= FVG.bottom),
        is_mitigated is set to True.
        """
        b1 = CandleBar(open=1.0900, high=1.0910, low=1.0880, close=1.0890, timestamp=1000)
        b2 = CandleBar(open=1.0890, high=1.0895, low=1.0810, close=1.0815, timestamp=1001)
        b3 = CandleBar(open=1.0815, high=1.0850, low=1.0780, close=1.0790, timestamp=1002)
        b4 = CandleBar(open=1.0790, high=1.0820, low=1.0770, close=1.0780, timestamp=1003)
        # b5 rallies into gap: High=1.0860 >= bottom (1.0850)
        b5 = CandleBar(open=1.0780, high=1.0860, low=1.0780, close=1.0850, timestamp=1004)

        fvgs = engine.detect_fair_value_gaps([b1, b2, b3, b4, b5], symbol="EURUSD", timeframe="15m")

        assert len(fvgs) == 1
        assert fvgs[0].is_mitigated is True

    def test_fvg_gold_symbol_pip_size(self, engine: SMCStructureEngine):
        """Tests that Gold (XAUUSD) pip size is correctly resolved to 0.1."""
        b1 = CandleBar(open=2000.0, high=2002.0, low=1999.0, close=2001.0, timestamp=1000)
        b2 = CandleBar(open=2001.0, high=2015.0, low=2000.5, close=2014.0, timestamp=1001)
        b3 = CandleBar(open=2014.0, high=2020.0, low=2008.0, close=2018.0, timestamp=1002)

        fvgs = engine.detect_fair_value_gaps([b1, b2, b3], symbol="XAUUSD", timeframe="1h")
        assert len(fvgs) == 1
        # Top = 2008.0, Bottom = 2002.0. Difference = 6.0. In pips (0.1/pip) = 60.0 pips
        assert fvgs[0].top == 2008.0
        assert fvgs[0].bottom == 2002.0
        assert fvgs[0].size_pips == 60.0

    def test_fvg_overlapping_no_gap(self, engine: SMCStructureEngine):
        """Tests that normal overlapping candles produce zero FVGs."""
        b1 = CandleBar(open=100.0, high=105.0, low=98.0, close=102.0)
        b2 = CandleBar(open=102.0, high=106.0, low=101.0, close=104.0)
        b3 = CandleBar(open=104.0, high=107.0, low=103.0, close=106.0)

        # Bar 1 High (105.0) > Bar 3 Low (103.0) -> No Bullish FVG
        # Bar 1 Low (98.0) < Bar 3 High (107.0) -> No Bearish FVG
        fvgs = engine.detect_fair_value_gaps([b1, b2, b3], symbol="EURUSD", timeframe="5m")
        assert len(fvgs) == 0

    def test_fvg_insufficient_candles(self, engine: SMCStructureEngine):
        """Tests that fewer than 3 candles returns empty list."""
        assert engine.detect_fair_value_gaps([], "EURUSD", "5m") == []
        c1 = CandleBar(open=100.0, high=101.0, low=99.0, close=100.0)
        c2 = CandleBar(open=100.0, high=101.0, low=99.0, close=100.0)
        assert engine.detect_fair_value_gaps([c1, c2], "EURUSD", "5m") == []


# ============================================================================
# 3. SESSION LIQUIDITY SWEEPS TESTS
# ============================================================================

class TestSessionLiquiditySweeps:
    """Verifies session liquidity sweep detection across Asian, London, and NY ranges."""

    @pytest.fixture
    def asian_session_levels(self) -> SessionLevels:
        return SessionLevels(
            session_name="ASIAN",
            high=1.0850,
            low=1.0800,
            open_price=1.0815,
            close_price=1.0835,
            start_time="2026-09-28T00:00:00Z",
            end_time="2026-09-28T07:00:00Z",
        )

    def test_asian_high_swept_during_london_open(
        self, engine: SMCStructureEngine, asian_session_levels: SessionLevels
    ):
        """
        Tests manipulation wick sweeping Asian High during London Open,
        closing back inside the session range (HIGH_SWEEP / Judas Swing).
        """
        # London open candle: pierces 1.0850 up to 1.0868, but closes at 1.0842 (inside)
        c_sweep = CandleBar(open=1.0835, high=1.0868, low=1.0830, close=1.0842, timestamp=2000)
        # Regular follow-up candle inside range
        c_inside = CandleBar(open=1.0842, high=1.0848, low=1.0825, close=1.0830, timestamp=2001)

        sweeps = engine.detect_session_liquidity_sweeps([c_sweep, c_inside], asian_session_levels, "EURUSD")

        assert len(sweeps) == 1
        s = sweeps[0]
        assert s.symbol == "EURUSD"
        assert s.session_name == "ASIAN"
        assert s.sweep_type == SweepType.HIGH_SWEEP
        assert s.is_high_sweep is True
        assert s.is_low_sweep is False
        assert s.swept_level == 1.0850
        assert s.sweep_wick_extreme == 1.0868
        assert s.candle_close_inside is True
        assert s.close_price == 1.0842
        assert s.timestamp == 2000
        assert abs(s.penetration_distance - 0.0018) < 1e-6

    def test_asian_low_swept_during_london_open(
        self, engine: SMCStructureEngine, asian_session_levels: SessionLevels
    ):
        """
        Tests manipulation wick sweeping Asian Low during London Open,
        closing back inside the session range (LOW_SWEEP / Judas Swing).
        """
        # London open candle: dips below 1.0800 to 1.0782, but closes back inside at 1.0815
        c_sweep = CandleBar(open=1.0830, high=1.0835, low=1.0782, close=1.0815, timestamp=2000)

        sweeps = engine.detect_session_liquidity_sweeps([c_sweep], asian_session_levels, "EURUSD")

        assert len(sweeps) == 1
        s = sweeps[0]
        assert s.symbol == "EURUSD"
        assert s.session_name == "ASIAN"
        assert s.sweep_type == SweepType.LOW_SWEEP
        assert s.is_low_sweep is True
        assert s.is_high_sweep is False
        assert s.swept_level == 1.0800
        assert s.sweep_wick_extreme == 1.0782
        assert s.candle_close_inside is True
        assert s.close_price == 1.0815
        assert abs(s.penetration_distance - 0.0018) < 1e-6

    def test_breakout_candle_closing_outside_not_a_sweep(
        self, engine: SMCStructureEngine, asian_session_levels: SessionLevels
    ):
        """
        A candle that pierces above the session high and closes outside (above high)
        is an expansion breakout, NOT a liquidity sweep.
        """
        c_breakout = CandleBar(open=1.0840, high=1.0890, low=1.0835, close=1.0882, timestamp=2000)

        sweeps = engine.detect_session_liquidity_sweeps([c_breakout], asian_session_levels, "EURUSD")
        assert len(sweeps) == 0

    def test_candle_inside_range_not_a_sweep(
        self, engine: SMCStructureEngine, asian_session_levels: SessionLevels
    ):
        """A candle remaining entirely inside the session boundaries produces no sweep."""
        c_normal = CandleBar(open=1.0820, high=1.0840, low=1.0810, close=1.0830, timestamp=2000)
        sweeps = engine.detect_session_liquidity_sweeps([c_normal], asian_session_levels, "EURUSD")
        assert len(sweeps) == 0

    def test_sweep_empty_or_none_inputs(self, engine: SMCStructureEngine):
        """Verifies graceful handling of empty or None session input."""
        assert engine.detect_session_liquidity_sweeps([], None, "EURUSD") == []
        c = CandleBar(open=1.0, high=1.1, low=0.9, close=1.0)
        assert engine.detect_session_liquidity_sweeps([c], None, "EURUSD") == []


# ============================================================================
# 4. COMPOSITE CONVICTION SCORE TESTS
# ============================================================================

class TestCompositeConvictionScore:
    """Verifies synthesis of Composite Conviction Score (0-100%) and Directional Bias."""

    def test_maximum_conviction_bullish_setup(self, engine: SMCStructureEngine):
        """
        Tests a 100% conviction Bullish Institutional setup:
        - Unmitigated Bullish Order Block (+15 pts)
        - Unmitigated Bullish Fair Value Gap (+10 pts)
        - Asian Low Liquidity Sweep (+10 pts)
        - BUY Sniper Pattern Trigger (+25 pts with sweep confirmation)
        - London Open Killzone (+20 pts)
        - Bearish DXY trend confirming USD weakness (+20 pts)
        - Tight spread 0.8 pips (0 penalty)
        Total = 35 + 25 + 20 + 20 - 0 = 100.0, Bias = BULLISH
        """
        ob = OrderBlock(
            symbol="EURUSD",
            timeframe="15m",
            block_type=OrderBlockType.BULLISH,
            high=1.0850,
            low=1.0820,
            open_price=1.0850,
            close_price=1.0820,
            is_mitigated=False,
        )
        fvg = FairValueGap(
            symbol="EURUSD",
            timeframe="15m",
            gap_type=FairValueGapType.BULLISH,
            top=1.0880,
            bottom=1.0860,
            size_pips=20.0,
            is_mitigated=False,
        )
        sweep = LiquiditySweep(
            symbol="EURUSD",
            session_name="ASIAN",
            sweep_type=SweepType.LOW_SWEEP,
            swept_level=1.0800,
            sweep_wick_extreme=1.0780,
            candle_close_inside=True,
        )

        score = engine.calculate_composite_conviction(
            smc_blocks=[ob],
            fvgs=[fvg],
            sweeps=[sweep],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=0.8,
            dxy_trend="BEARISH",
        )

        assert score.total_score == 100.0
        assert score.bias == ConvictionBias.BULLISH
        assert score.smc_alignment_score == 35.0
        assert score.sniper_pattern_score == 25.0
        assert score.session_timing_score == 20.0
        assert score.correlation_score == 20.0
        assert score.spread_penalty == 0.0
        assert len(score.key_reasons) >= 5

    def test_maximum_conviction_bearish_setup(self, engine: SMCStructureEngine):
        """
        Tests a 100% conviction Bearish Institutional setup:
        - Unmitigated Bearish Order Block (+15 pts)
        - Unmitigated Bearish Fair Value Gap (+10 pts)
        - Asian High Liquidity Sweep (+10 pts)
        - SELL Sniper Pattern Trigger (+25 pts with sweep confirmation)
        - New York Killzone (+20 pts)
        - Bullish DXY trend confirming USD strength (+20 pts)
        - Tight spread 1.0 pips (0 penalty)
        Total = 35 + 25 + 20 + 20 - 0 = 100.0, Bias = BEARISH
        """
        ob = OrderBlock(
            symbol="EURUSD",
            timeframe="15m",
            block_type=OrderBlockType.BEARISH,
            high=1.0920,
            low=1.0890,
            open_price=1.0890,
            close_price=1.0920,
            is_mitigated=False,
        )
        fvg = FairValueGap(
            symbol="EURUSD",
            timeframe="15m",
            gap_type=FairValueGapType.BEARISH,
            top=1.0880,
            bottom=1.0850,
            size_pips=30.0,
            is_mitigated=False,
        )
        sweep = LiquiditySweep(
            symbol="EURUSD",
            session_name="ASIAN",
            sweep_type=SweepType.HIGH_SWEEP,
            swept_level=1.0900,
            sweep_wick_extreme=1.0925,
            candle_close_inside=True,
        )

        score = engine.calculate_composite_conviction(
            smc_blocks=[ob],
            fvgs=[fvg],
            sweeps=[sweep],
            pattern_direction="SELL",
            session="NEW_YORK",
            spread_pips=1.0,
            dxy_trend="BULLISH",
        )

        assert score.total_score == 100.0
        assert score.bias == ConvictionBias.BEARISH
        assert score.smc_alignment_score == 35.0
        assert score.sniper_pattern_score == 25.0
        assert score.session_timing_score == 20.0
        assert score.correlation_score == 20.0
        assert score.spread_penalty == 0.0
        assert len(score.key_reasons) >= 5

    def test_dxy_macro_headwind_reduces_score(self, engine: SMCStructureEngine):
        """
        Tests that an opposing DXY trend (e.g. Bullish DXY against a BUY trade)
        reduces the correlation score to 0.0 pts.
        """
        ob = OrderBlock(
            symbol="EURUSD",
            timeframe="15m",
            block_type=OrderBlockType.BULLISH,
            high=1.0850,
            low=1.0820,
            open_price=1.0850,
            close_price=1.0820,
            is_mitigated=False,
        )
        score = engine.calculate_composite_conviction(
            smc_blocks=[ob],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=1.0,
            dxy_trend="BULLISH",  # Headwind!
        )

        assert score.correlation_score == 0.0
        assert any("Macro Headwind" in r for r in score.key_reasons)

    def test_wide_spread_penalty_applied(self, engine: SMCStructureEngine):
        """Tests that wide spreads apply progressive penalties to conviction."""
        score_tight = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=1.0,
        )
        score_wide = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=4.5,
        )

        assert score_tight.spread_penalty == 0.0
        assert score_wide.spread_penalty > 10.0
        assert score_wide.total_score < score_tight.total_score

    def test_contradicting_structure_penalty(self, engine: SMCStructureEngine):
        """
        Tests that an unmitigated Bearish OB overhead penalizes smc_alignment_score
        when taking a BUY setup.
        """
        bull_ob = OrderBlock(
            symbol="EURUSD",
            timeframe="15m",
            block_type=OrderBlockType.BULLISH,
            high=1.0850,
            low=1.0820,
            open_price=1.0850,
            close_price=1.0820,
            is_mitigated=False,
        )
        bear_ob = OrderBlock(
            symbol="EURUSD",
            timeframe="15m",
            block_type=OrderBlockType.BEARISH,
            high=1.0900,
            low=1.0880,
            open_price=1.0880,
            close_price=1.0900,
            is_mitigated=False,
        )

        score_solo = engine.calculate_composite_conviction(
            smc_blocks=[bull_ob],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=1.0,
        )
        score_with_contra = engine.calculate_composite_conviction(
            smc_blocks=[bull_ob, bear_ob],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON",
            spread_pips=1.0,
        )

        assert score_with_contra.smc_alignment_score < score_solo.smc_alignment_score

    def test_neutral_and_empty_inputs_behavior(self, engine: SMCStructureEngine):
        """Verifies completely empty inputs produce a clean, deterministic NEUTRAL score."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="NEUTRAL",
            session="OFF_HOURS",
            spread_pips=1.0,
            dxy_trend=None,
        )

        assert score.total_score < 40.0
        assert score.bias == ConvictionBias.NEUTRAL
        assert score.smc_alignment_score == 0.0
        assert score.sniper_pattern_score == 0.0
        assert score.session_timing_score == 5.0
        assert score.correlation_score == 10.0
        assert score.spread_penalty == 0.0


# ============================================================================
# 5. SCHEMA INVARIANTS & PROPERTY HELPER TESTS
# ============================================================================

class TestSMCSchemaProperties:
    """Verifies schema helper properties and serialization invariants."""

    def test_order_block_properties(self):
        ob = OrderBlock(
            symbol="EURUSD",
            timeframe="15m",
            block_type=OrderBlockType.BULLISH,
            high=1.0850,
            low=1.0820,
            open_price=1.0850,
            close_price=1.0820,
        )
        assert ob.is_bullish is True
        assert ob.is_bearish is False
        assert abs(ob.range - 0.0030) < 1e-6
        assert abs(ob.mid_price - 1.0835) < 1e-6

    def test_fair_value_gap_properties(self):
        fvg = FairValueGap(
            symbol="EURUSD",
            timeframe="15m",
            gap_type=FairValueGapType.BEARISH,
            top=1.0900,
            bottom=1.0850,
            size_pips=50.0,
        )
        assert fvg.is_bearish is True
        assert fvg.is_bullish is False
        assert abs(fvg.midpoint - 1.0875) < 1e-6

    def test_liquidity_sweep_properties(self):
        sweep = LiquiditySweep(
            symbol="EURUSD",
            session_name="ASIAN",
            sweep_type=SweepType.HIGH_SWEEP,
            swept_level=1.0850,
            sweep_wick_extreme=1.0870,
            candle_close_inside=True,
        )
        assert sweep.is_high_sweep is True
        assert sweep.is_low_sweep is False
        assert abs(sweep.penetration_distance - 0.0020) < 1e-6

    def test_session_levels_properties(self):
        sess = SessionLevels(
            session_name="ASIAN",
            high=1.0850,
            low=1.0800,
            open_price=1.0810,
            close_price=1.0840,
        )
        assert abs(sess.session_range - 0.0050) < 1e-6
        assert abs(sess.mid_price - 1.0825) < 1e-6

    def test_pip_size_helper(self):
        assert _get_pip_size("EURUSD") == 0.0001
        assert _get_pip_size("GBPUSD") == 0.0001
        assert _get_pip_size("USDJPY") == 0.01
        assert _get_pip_size("EURJPY") == 0.01
        assert _get_pip_size("XAUUSD") == 0.1
        assert _get_pip_size("GOLD") == 0.1
        assert _get_pip_size("BTCUSD") == 1.0
        assert _get_pip_size("US30") == 1.0
        assert _get_pip_size("NAS100") == 1.0


# ============================================================================
# 6. MACRO NEWS IMPACT & GOLD/DXY INVERSE CORRELATION TESTS
# ============================================================================

class TestMacroNewsImpactAndGoldDXYCorrelation:
    """Verifies macro news blackout penalty and symbol-aware Gold/DXY inverse correlation."""

    def test_high_impact_news_within_15min_applies_penalty(self, engine: SMCStructureEngine):
        """High-impact macro news within 15 min imposes -15 pts penalty."""
        score_normal = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=1.0,
            macro_news_impact=None,
            minutes_to_news=None,
        )
        score_news = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=1.0,
            macro_news_impact="HIGH",
            minutes_to_news=10,
        )

        assert score_news.macro_news_penalty == 15.0
        assert score_news.total_score == max(0.0, score_normal.total_score - 15.0)
        assert any("news blackout penalty" in r for r in score_news.key_reasons)

    def test_high_impact_news_exact_15min_boundary(self, engine: SMCStructureEngine):
        """Exact 15-minute boundary must trigger the blackout penalty."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=1.0,
            macro_news_impact="HIGH",
            minutes_to_news=15,
        )
        assert score.macro_news_penalty == 15.0

    def test_high_impact_news_further_than_15min_no_penalty(self, engine: SMCStructureEngine):
        """High impact news 16+ minutes away incurs zero penalty."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=1.0,
            macro_news_impact="HIGH",
            minutes_to_news=16,
        )
        assert score.macro_news_penalty == 0.0

    def test_high_impact_news_negative_minutes_past_news_no_penalty(self, engine: SMCStructureEngine):
        """Negative minutes_to_news (e.g. -120 for past news) incurs zero penalty and no reason entry."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=1.0,
            macro_news_impact="HIGH",
            minutes_to_news=-120,
        )
        assert score.macro_news_penalty == 0.0
        assert not any("news blackout penalty" in r for r in score.key_reasons)

    def test_medium_and_low_impact_news_no_penalty(self, engine: SMCStructureEngine):
        """Medium or Low impact news within 10 min does not trigger blackout penalty."""
        score_med = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=1.0,
            macro_news_impact="MEDIUM",
            minutes_to_news=5,
        )
        assert score_med.macro_news_penalty == 0.0

        score_low = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=1.0,
            macro_news_impact="LOW",
            minutes_to_news=5,
        )
        assert score_low.macro_news_penalty == 0.0

    def test_gold_dxy_bullish_penalizes_long_gold(self, engine: SMCStructureEngine):
        """Bullish DXY opposes Long Gold -> penalizes by -10 pts (correlation_score = 0.0)."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=1.0,
            dxy_trend="BULLISH",
            symbol="XAUUSD",
        )
        assert score.correlation_score == 0.0
        assert any("Bullish DXY penalizes Long Gold" in r for r in score.key_reasons)

    def test_gold_dxy_bearish_boosts_long_gold(self, engine: SMCStructureEngine):
        """Bearish DXY confirms Long Gold -> boosts by +10 pts (correlation_score = 20.0)."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=1.0,
            dxy_trend="BEARISH",
            symbol="GOLD",
        )
        assert score.correlation_score == 20.0
        assert any("Bearish DXY boosts Long Gold" in r for r in score.key_reasons)

    def test_gold_dxy_bullish_boosts_short_gold(self, engine: SMCStructureEngine):
        """Bullish DXY reinforces Short Gold -> boosts by +10 pts (correlation_score = 20.0)."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="SELL",
            session="LONDON_OPEN",
            spread_pips=1.0,
            dxy_trend="BULLISH",
            symbol="XAUUSD",
        )
        assert score.correlation_score == 20.0
        assert any("Bullish DXY boosts Short Gold" in r for r in score.key_reasons)

    def test_gold_dxy_bearish_penalizes_short_gold(self, engine: SMCStructureEngine):
        """Bearish DXY opposes Short Gold -> penalizes by -10 pts (correlation_score = 0.0)."""
        score = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="SELL",
            session="LONDON_OPEN",
            spread_pips=1.0,
            dxy_trend="BEARISH",
            symbol="GOLD",
        )
        assert score.correlation_score == 0.0
        assert any("Bearish DXY penalizes Short Gold" in r for r in score.key_reasons)

    def test_gold_neutral_and_unassigned_dxy(self, engine: SMCStructureEngine):
        """Neutral or missing DXY provides baseline 10.0 pts correlation score for Gold."""
        score_neutral = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=1.0,
            dxy_trend="NEUTRAL",
            symbol="XAUUSD",
        )
        assert score_neutral.correlation_score == 10.0

        score_none = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="LONDON_OPEN",
            spread_pips=1.0,
            dxy_trend=None,
            symbol="XAUUSD",
        )
        assert score_none.correlation_score == 10.0

    def test_score_bounded_between_zero_and_hundred(self, engine: SMCStructureEngine):
        """Ensures that compounding penalties keep score bounded at 0.0, and confluence caps at 100.0."""
        score_low = engine.calculate_composite_conviction(
            smc_blocks=[],
            fvgs=[],
            sweeps=[],
            pattern_direction="BUY",
            session="OFF_HOURS",  # 5 pts
            spread_pips=8.0,      # -25 pts penalty
            dxy_trend="BULLISH",  # 0 pts
            macro_news_impact="HIGH",
            minutes_to_news=5,    # -15 pts penalty
            symbol="XAUUSD",
        )
        assert score_low.total_score >= 0.0
        assert score_low.total_score <= 100.0


# ============================================================================
# 7. SESSION LEVELS EXTRACTION TESTS
# ============================================================================

class TestComputeSessionLevels:
    """Verifies automated extraction of Asian, London, and NY high/low levels."""

    def test_extract_asian_london_ny_session_levels(self, engine: SMCStructureEngine):
        """Extracts Asian (00-07 UTC), London (07-12 UTC), and NY (12-20 UTC) ranges."""
        base_date = datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)
        candles = []

        # Asian: hours 0..6
        for h in range(7):
            candles.append(
                PriceBar(
                    symbol="EURUSD",
                    timeframe="1h",
                    bar_time=base_date + timedelta(hours=h),
                    open=1.0800 + h * 0.0005,
                    high=1.0850,
                    low=1.0790,
                    close=1.0820,
                    volume=100.0,
                    provider="test",
                )
            )

        # London: hours 7..11
        for h in range(7, 12):
            candles.append(
                PriceBar(
                    symbol="EURUSD",
                    timeframe="1h",
                    bar_time=base_date + timedelta(hours=h),
                    open=1.0820,
                    high=1.0890,
                    low=1.0810,
                    close=1.0870,
                    volume=150.0,
                    provider="test",
                )
            )

        # NY: hours 12..19
        for h in range(12, 20):
            candles.append(
                PriceBar(
                    symbol="EURUSD",
                    timeframe="1h",
                    bar_time=base_date + timedelta(hours=h),
                    open=1.0870,
                    high=1.0920,
                    low=1.0840,
                    close=1.0900,
                    volume=200.0,
                    provider="test",
                )
            )

        sess_levels = engine.compute_session_levels(candles)

        assert sess_levels.asian_high == 1.0850
        assert sess_levels.asian_low == 1.0790
        assert sess_levels.london_high == 1.0890
        assert sess_levels.london_low == 1.0810
        assert sess_levels.ny_high == 1.0920
        assert sess_levels.ny_low == 1.0840

        # By default primary is Asian range for SMC sweep referencing
        assert sess_levels.session_name == "ASIAN"
        assert sess_levels.high == 1.0850
        assert sess_levels.low == 1.0790
        assert "ASIAN" in sess_levels.sessions
        assert "LONDON" in sess_levels.sessions
        assert "NEW_YORK" in sess_levels.sessions

    def test_compute_session_levels_with_explicit_session_selection(self, engine: SMCStructureEngine):
        """Allows explicit selection of London or NY as primary session bounds."""
        base_date = datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)
        candles = [
            PriceBar(
                symbol="EURUSD",
                timeframe="1h",
                bar_time=base_date + timedelta(hours=2),
                open=1.0800,
                high=1.0850,
                low=1.0790,
                close=1.0820,
                volume=100.0,
                provider="test",
            ),
            PriceBar(
                symbol="EURUSD",
                timeframe="1h",
                bar_time=base_date + timedelta(hours=8),
                open=1.0820,
                high=1.0890,
                low=1.0810,
                close=1.0870,
                volume=150.0,
                provider="test",
            ),
        ]

        sess_london = engine.compute_session_levels(candles, session_name="LONDON")
        assert sess_london.session_name == "LONDON"
        assert sess_london.high == 1.0890
        assert sess_london.low == 1.0810
        assert sess_london.asian_high == 1.0850

    def test_compute_session_levels_empty_candles(self, engine: SMCStructureEngine):
        """Gracefully returns empty SessionLevels on empty input."""
        res = engine.compute_session_levels([])
        assert res.session_name == "NONE"
        assert res.high == 0.0
        assert res.low == 0.0

    def test_compute_session_levels_defensive_none_candle_attributes(self, engine: SMCStructureEngine):
        """Defensively handles candles where high or low attributes are explicitly None."""
        class MockCandle:
            bar_time = datetime(2026, 9, 29, 2, 0, tzinfo=timezone.utc)
            open = 1.0800
            high = None
            low = None
            close = 1.0820

        res = engine.compute_session_levels([MockCandle()])
        assert res.high == 0.0
        assert res.low == 0.0

    def test_session_levels_integration_with_sweep_detector(self, engine: SMCStructureEngine):
        """Ensures SessionLevels from compute_session_levels directly feeds sweep detection."""
        base_date = datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)
        asian_bars = [
            PriceBar(
                symbol="EURUSD",
                timeframe="1h",
                bar_time=base_date + timedelta(hours=3),
                open=1.0820,
                high=1.0850,
                low=1.0800,
                close=1.0830,
                volume=100.0,
                provider="test",
            )
        ]
        sess_levels = engine.compute_session_levels(asian_bars)

        # London Judas sweep candle sweeping Asian low (1.0800) with low=1.0780 and close=1.0810
        london_sweep_candle = CandleBar(
            open=1.0820,
            high=1.0830,
            low=1.0780,
            close=1.0810,
            timestamp=base_date + timedelta(hours=8),
        )

        sweeps = engine.detect_session_liquidity_sweeps([london_sweep_candle], sess_levels, "EURUSD")
        assert len(sweeps) == 1
        assert sweeps[0].sweep_type == SweepType.LOW_SWEEP
        assert sweeps[0].swept_level == 1.0800
        assert sweeps[0].sweep_wick_extreme == 1.0780


# ============================================================================
# 8. SMC REST ENDPOINTS TESTS (R4 READ-ONLY COMPLIANCE)
# ============================================================================

class TestSMCRESTEndpoints:
    """Verifies SMC REST API endpoints and strict R4 read-only adherence."""

    @pytest.fixture(autouse=True)
    def mock_history_bars(self, monkeypatch):
        """Prevents remote database network calls during API unit tests."""
        monkeypatch.setattr(market_history_service, "get_bars", lambda *args, **kwargs: [])

    @pytest.fixture
    def client(self) -> TestClient:
        app = FastAPI()
        app.include_router(smc_router, prefix="/api/v1")
        return TestClient(app)

    def test_router_included_in_main_api_router(self):
        """Verifies smc router is properly mounted in app.api.v1.api.api_router."""
        found = any(
            getattr(route, "original_router", None) is smc_router
            or getattr(route, "router", None) is smc_router
            or (hasattr(route, "path") and "/smc" in getattr(route, "path", ""))
            for route in api_router.routes
        )
        assert found, "SMC router must be included in api_router"

    def test_smc_structure_endpoint_read_only(self, client: TestClient):
        """GET /api/v1/smc/structure returns 200 and SMCStructureResponse schema."""
        response = client.get("/api/v1/smc/structure?symbol=EURUSD&timeframe=15m")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "EURUSD"
        assert data["timeframe"] == "15m"
        assert "order_blocks" in data
        assert "fair_value_gaps" in data
        assert "total_order_blocks" in data
        assert "total_fair_value_gaps" in data

    def test_smc_sweeps_endpoint_read_only(self, client: TestClient):
        """GET /api/v1/smc/sweeps returns 200 and SMCSweepsResponse schema."""
        response = client.get("/api/v1/smc/sweeps?symbol=EURUSD&timeframe=15m")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "EURUSD"
        assert "sweeps" in data
        assert "total_sweeps" in data
        assert "high_sweeps" in data
        assert "low_sweeps" in data

    def test_smc_conviction_endpoint_default(self, client: TestClient):
        """GET /api/v1/smc/conviction returns 200 and CompositeConvictionScore schema."""
        response = client.get("/api/v1/smc/conviction?symbol=EURUSD&direction=BUY")
        assert response.status_code == 200
        data = response.json()
        assert "total_score" in data
        assert "bias" in data
        assert "smc_alignment_score" in data
        assert "session_timing_score" in data
        assert "correlation_score" in data
        assert "spread_penalty" in data
        assert "macro_news_penalty" in data
        assert "key_reasons" in data
        assert 0.0 <= data["total_score"] <= 100.0

    def test_smc_conviction_endpoint_with_macro_news_and_gold(self, client: TestClient):
        """GET /api/v1/smc/conviction handles macro news blackout and Gold/DXY parameters."""
        response = client.get(
            "/api/v1/smc/conviction?symbol=XAUUSD&direction=BUY&macro_news_impact=HIGH&minutes_to_news=10&dxy_trend=BULLISH"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["macro_news_penalty"] == 15.0
        assert data["correlation_score"] == 0.0  # Bullish DXY penalizes Long Gold by -10 pts
        assert any("news blackout penalty" in r for r in data["key_reasons"])
        assert any("Bullish DXY penalizes Long Gold" in r for r in data["key_reasons"])

    def test_smc_conviction_endpoint_negative_minutes_rejected(self, client: TestClient):
        """GET /api/v1/smc/conviction with negative minutes_to_news is rejected with 422 Unprocessable Entity."""
        response = client.get("/api/v1/smc/conviction?minutes_to_news=-120")
        assert response.status_code == 422

    def test_smc_endpoints_r4_read_only_compliance(self, client: TestClient):
        """Strictly enforces Requirement R4: All endpoints are GET-only, POST/PUT/DELETE return 405 Method Not Allowed."""
        resp_post_struct = client.post("/api/v1/smc/structure", json={})
        assert resp_post_struct.status_code == 405

        resp_post_sweeps = client.post("/api/v1/smc/sweeps", json={})
        assert resp_post_sweeps.status_code == 405

        resp_post_conv = client.post("/api/v1/smc/conviction", json={})
        assert resp_post_conv.status_code == 405

