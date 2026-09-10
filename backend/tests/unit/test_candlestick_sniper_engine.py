"""
Unit tests for CandlestickPatternEngine and Sniper Entry Mechanics.
Tests patterns learned from Headway, TradingSim, Rayner Teo, BrokerXplorer, and FX-List.
"""

import unittest
from app.core.engines.candlestick_pattern_engine import (
    CandlestickPatternEngine, CandleBar, PatternType, SignalDirection
)


class TestCandlestickSniperEngine(unittest.TestCase):
    def setUp(self):
        self.engine = CandlestickPatternEngine()

    def test_bullish_hammer_detection(self):
        """
        Headway Rule: Lower shadow >= 60% of total range, body <= 30%, upper shadow <= 15%.
        Rejects lower prices and confirms BUY.
        """
        # Range: 2000.0 to 2010.0 (range = 10.0)
        # Open: 2008.0, Close: 2009.5 (body = 1.5, body_ratio = 0.15)
        # Low: 2000.0 (lower shadow = 8.0, ratio = 0.80)
        # High: 2010.0 (upper shadow = 0.5, ratio = 0.05)
        hammer_bar = CandleBar(open=2008.0, high=2010.0, low=2000.0, close=2009.5)
        prev1 = CandleBar(open=2015.0, high=2016.0, low=2007.0, close=2008.0)
        prev2 = CandleBar(open=2020.0, high=2021.0, low=2014.0, close=2015.0)

        results = self.engine.analyze_patterns([prev2, prev1, hammer_bar])
        patterns = [r.pattern_type for r in results]
        
        self.assertIn(PatternType.BULLISH_HAMMER, patterns)
        hammer_res = next(r for r in results if r.pattern_type == PatternType.BULLISH_HAMMER)
        self.assertEqual(hammer_res.direction, SignalDirection.BUY)
        self.assertGreaterEqual(hammer_res.conviction_score, 0.88)
        self.assertEqual(hammer_res.invalidation_level, 2000.0)
        self.assertGreater(hammer_res.recommended_target, hammer_bar.close)

    def test_bearish_shooting_star_detection(self):
        """
        Headway Rule: Upper shadow >= 60% of range, body <= 30%, lower shadow <= 15%.
        Rejection of higher prices at swing high.
        """
        # Range: 1.1000 to 1.1050 (50 pips)
        # Low: 1.1000, Open: 1.1010, Close: 1.1005 (body = 5 pips, lower = 5 pips)
        # High: 1.1050 (upper shadow = 40 pips = 80%)
        star_bar = CandleBar(open=1.1010, high=1.1050, low=1.1000, close=1.1005)
        prev1 = CandleBar(open=1.0950, high=1.1015, low=1.0945, close=1.1010)
        prev2 = CandleBar(open=1.0900, high=1.0960, low=1.0895, close=1.0950)

        results = self.engine.analyze_patterns([prev2, prev1, star_bar])
        patterns = [r.pattern_type for r in results]

        self.assertIn(PatternType.BEARISH_SHOOTING_STAR, patterns)
        star_res = next(r for r in results if r.pattern_type == PatternType.BEARISH_SHOOTING_STAR)
        self.assertEqual(star_res.direction, SignalDirection.SELL)
        self.assertEqual(star_res.invalidation_level, 1.1050)
        self.assertLess(star_res.recommended_target, star_bar.close)

    def test_bullish_engulfing_detection(self):
        """
        Headway Rule: Previous candle bearish, current candle bullish engulfing the entire body.
        """
        prev = CandleBar(open=1.2050, high=1.2055, low=1.2000, close=1.2010)
        curr = CandleBar(open=1.2005, high=1.2080, low=1.2000, close=1.2070)
        prev2 = CandleBar(open=1.2080, high=1.2090, low=1.2040, close=1.2050)

        results = self.engine.analyze_patterns([prev2, prev, curr])
        patterns = [r.pattern_type for r in results]

        self.assertIn(PatternType.BULLISH_ENGULFING, patterns)
        engulf_res = next(r for r in results if r.pattern_type == PatternType.BULLISH_ENGULFING)
        self.assertEqual(engulf_res.direction, SignalDirection.BUY)
        self.assertGreaterEqual(engulf_res.conviction_score, 0.90)

    def test_morning_star_reversal(self):
        """
        Headway & Institutional 3-bar reversal:
        1. Strong Bearish candle
        2. Small Doji/Star candle
        3. Strong Bullish candle closing > 50% into candle 1.
        """
        bar1 = CandleBar(open=100.0, high=101.0, low=90.0, close=91.0)  # Body = 9.0
        bar2 = CandleBar(open=90.5, high=91.5, low=89.5, close=90.8)   # Small star body = 0.3
        bar3 = CandleBar(open=91.0, high=98.0, low=90.8, close=97.5)   # Closes well above 50% midpoint (95.5)

        results = self.engine.analyze_patterns([bar1, bar2, bar3])
        patterns = [r.pattern_type for r in results]

        self.assertIn(PatternType.MORNING_STAR, patterns)
        ms_res = next(r for r in results if r.pattern_type == PatternType.MORNING_STAR)
        self.assertEqual(ms_res.direction, SignalDirection.BUY)
        self.assertGreaterEqual(ms_res.conviction_score, 0.92)

    def test_rayner_false_breakout_trap(self):
        """
        Rayner Teo Sniper Entry: Price pierces resistance to trap breakout traders,
        then violently snaps back below resistance on candle close.
        """
        resistance = 2050.0
        # High swept to 2054.0 but closed at 2047.0 (inside range)
        trap_bar = CandleBar(open=2048.0, high=2054.0, low=2045.0, close=2047.0)
        bars = [
            CandleBar(open=2040.0, high=2044.0, low=2039.0, close=2043.0),
            CandleBar(open=2043.0, high=2046.0, low=2042.0, close=2045.0),
            CandleBar(open=2045.0, high=2048.0, low=2044.0, close=2047.0),
            CandleBar(open=2047.0, high=2049.5, low=2046.0, close=2048.0),
            trap_bar
        ]

        results = self.engine.analyze_patterns(bars, key_resistance=resistance)
        patterns = [r.pattern_type for r in results]

        self.assertIn(PatternType.FALSE_BREAKOUT_TRAP, patterns)
        trap_res = next(r for r in results if r.pattern_type == PatternType.FALSE_BREAKOUT_TRAP)
        self.assertEqual(trap_res.direction, SignalDirection.SELL)
        self.assertEqual(trap_res.invalidation_level, 2054.0)

    def test_brokerxplorer_15m_5m_breakout_alignment(self):
        """
        BrokerXplorer Multi-Timeframe Strategy:
        15M closed bar establishes reference high/low.
        5M bar closes decisively above the 15M high -> sniper breakout trigger.
        """
        bar_15m_prev = CandleBar(open=1.0800, high=1.0850, low=1.0790, close=1.0840)
        bar_15m_curr = CandleBar(open=1.0840, high=1.0890, low=1.0835, close=1.0880)

        # 5M closes at 1.0865 (above 15M high 1.0850)
        bar_5m_1 = CandleBar(open=1.0835, high=1.0845, low=1.0830, close=1.0842)
        bar_5m_2 = CandleBar(open=1.0842, high=1.0855, low=1.0840, close=1.0852)
        bar_5m_curr = CandleBar(open=1.0852, high=1.0870, low=1.0850, close=1.0865)

        results = self.engine.analyze_patterns(
            candles_5m=[bar_5m_1, bar_5m_2, bar_5m_curr],
            candles_15m=[bar_15m_prev, bar_15m_curr],
        )
        patterns = [r.pattern_type for r in results]

        self.assertIn(PatternType.TIMEFRAME_15M_5M_BREAKOUT, patterns)
        bo_res = next(r for r in results if r.pattern_type == PatternType.TIMEFRAME_15M_5M_BREAKOUT)
        self.assertEqual(bo_res.direction, SignalDirection.BUY)
        self.assertEqual(bo_res.invalidation_level, bar_15m_prev.low)


if __name__ == "__main__":
    unittest.main()
