"""
Unit tests verifying the regression fixes for Falcon signal generation,
session breakout verification, sniper setup reactivation, and outcome resolution.
"""

import unittest
from datetime import datetime, timezone, timedelta
from app.core.engines.candlestick_pattern_engine import CandleBar, PatternType, SignalDirection
from app.core.engines.session_breakout_engine import SessionBreakoutEngine, SessionStatus, SessionName
from app.schemas.strategy import StrategyItem, StrategyType, StrategyStatus, RiskLevel, StrategyHealth, StrategyCategory
from app.schemas.market_state import MarketState, MarketPrice
from app.schemas.signal_candidate import CandidateDirection, CandidateStatus
from app.core.engines.signal_generation_engine import SignalGenerationEngine


class TestSignalGenerationRegressions(unittest.TestCase):
    def setUp(self):
        self.session_engine = SessionBreakoutEngine()
        self.signal_engine = SignalGenerationEngine()

    def test_candle_bar_accepts_timestamp_and_time(self):
        """CandleBar dataclass must gracefully accept both timestamp and time without error."""
        now = datetime.now(timezone.utc)
        bar = CandleBar(
            open=1.1000,
            high=1.1020,
            low=1.0990,
            close=1.1015,
            volume=500.0,
            timestamp=int(now.timestamp()),
            time=now,
        )
        self.assertEqual(bar.open, 1.1000)
        self.assertEqual(bar.timestamp, int(now.timestamp()))
        self.assertEqual(bar.time, now)

    def test_compute_session_corridors_no_benchmark_in_live_mode(self):
        """When allow_benchmark=False, empty candles or candles without timestamps must return [] instead of fake corridors."""
        # 1. Empty candles
        corridors_empty = self.session_engine.compute_session_corridors("XAUUSD", [], allow_benchmark=False)
        self.assertEqual(corridors_empty, [])

        # 2. Benchmark explicitly allowed for UI / chart fallback
        corridors_bm = self.session_engine.compute_session_corridors("XAUUSD", [], allow_benchmark=True)
        self.assertGreater(len(corridors_bm), 0)

        # 3. Candles without timestamps must NOT return benchmark fake corridors when allow_benchmark=False
        bars_no_time = [
            CandleBar(open=1.1000, high=1.1050, low=1.0980, close=1.1020, volume=1000.0)
            for _ in range(25)
        ]
        corridors_no_time = self.session_engine.compute_session_corridors("EURUSD", bars_no_time, allow_benchmark=False)
        self.assertEqual(corridors_no_time, [])

    def test_compute_session_corridors_with_real_timestamps(self):
        """When candles have timestamps, authentic session high/low corridors are formed."""
        now = datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)
        bars = []
        # Create 10 bars spanning Asian session (00:00 to 07:00 UTC)
        for h in range(10):
            t = datetime(2026, 10, 13, h, 0, tzinfo=timezone.utc)
            bars.append(
                CandleBar(
                    open=1.1000 + (h * 0.0005),
                    high=1.1020 + (h * 0.0005),
                    low=1.0990 + (h * 0.0005),
                    close=1.1010 + (h * 0.0005),
                    volume=1500.0,
                    timestamp=int(t.timestamp()),
                    time=t,
                )
            )

        corridors = self.session_engine.compute_session_corridors("EURUSD", bars, allow_benchmark=False)
        self.assertGreater(len(corridors), 0)
        asian = next((c for c in corridors if c.session_name == SessionName.ASIAN), None)
        self.assertIsNotNone(asian)
        self.assertGreater(asian.high, asian.low)

    def test_calculate_trade_levels_bounds_tp1_to_take_profit(self):
        """TP1 must never exceed or overshoot the primary take_profit target."""
        # BUY trade with entry 1.3200, SL 1.3180 (risk 20 pips), and final TP 1.3250
        sl, tp1, tp2, trail_buf, atr = self.session_engine.calculate_trade_levels(
            symbol="GBPUSD",
            direction="BUY",
            entry_price=1.3200,
            candles=[],
            structure_sl=1.3180,
            take_profit=1.3250,
        )
        self.assertLessEqual(tp1, 1.3250)
        self.assertGreater(tp1, 1.3200)
        self.assertEqual(tp2, 1.3250)

        # SELL trade with entry 1.3200, SL 1.3220, and final TP 1.3150
        sl_s, tp1_s, tp2_s, _, _ = self.session_engine.calculate_trade_levels(
            symbol="GBPUSD",
            direction="SELL",
            entry_price=1.3200,
            candles=[],
            structure_sl=1.3220,
            take_profit=1.3150,
        )
        self.assertGreaterEqual(tp1_s, 1.3150)
        self.assertLess(tp1_s, 1.3200)
        self.assertEqual(tp2_s, 1.3150)

    def test_unconfirmed_setups_do_not_become_generated_status(self):
        """A strategy candidate with no confirmed sniper pattern or volume breakout MUST stay WAITING_CONFIRMATION."""
        now = datetime.now(timezone.utc)
        from app.core.engines.strategy_engine import StrategyEngine
        strat = StrategyEngine().get_strategy_by_id("strat-001")
        self.assertIsNotNone(strat)

        market_state = MarketState(
            session="London",
            marketSentimentLabel="Bullish",
            overallMarketConfidence=70,
            volatility="Moderate",
            timestamp=now,
            dataAgeSeconds=10,
            prices={
                "XAUUSD": MarketPrice(
                    symbol="XAUUSD",
                    currentPrice=2650.5,
                    bid=2650.0,
                    ask=2651.0,
                    spread=1.0,
                    timestamp=now,
                    provider="test",
                )
            },
            calendar=[],
        )

        candidates = self.signal_engine.generate_candidates(
            market_state=market_state,
            strategies=[strat],
            as_of=now,
        )

        self.assertEqual(len(candidates), 1)
        cand = candidates[0]
        # Without an authentic volume surge and corridor breakout, must NOT be GENERATED
        self.assertNotEqual(cand.status, CandidateStatus.GENERATED)
        self.assertIn(cand.status, [CandidateStatus.WAITING_CONFIRMATION, CandidateStatus.REJECTED])

    def test_session_mismatch_prevents_readiness_pass(self):
        """When current session does not match strategy's preferredSessions, session_cond must fail."""
        now = datetime.now(timezone.utc)
        from app.core.engines.strategy_engine import StrategyEngine
        strat = StrategyEngine().get_strategy_by_id("strat-002")
        self.assertIsNotNone(strat)

        # Market is in Asian session
        market_state = MarketState(
            session="Asian",
            marketSentimentLabel="Neutral",
            overallMarketConfidence=50,
            volatility="Moderate",
            timestamp=now,
            dataAgeSeconds=10,
            prices={
                "XAUUSD": MarketPrice(
                    symbol="XAUUSD",
                    currentPrice=2650.5,
                    bid=2650.0,
                    ask=2651.0,
                    spread=1.0,
                    timestamp=now,
                    provider="test",
                )
            },
            calendar=[],
        )

        candidates = self.signal_engine.generate_candidates(
            market_state=market_state,
            strategies=[strat],
            as_of=now,
        )

        self.assertEqual(len(candidates), 1)
        cand = candidates[0]
        session_cond = next((c for c in cand.conditions if c.title == "Session Match"), None)
        self.assertIsNotNone(session_cond)
        self.assertFalse(session_cond.passed)
        self.assertNotEqual(cand.status, CandidateStatus.GENERATED)


if __name__ == "__main__":
    unittest.main()
