import unittest
from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.htf_structure_engine import MultiTimeframeStructureEngine


class TestHTFStructureEngine(unittest.TestCase):
    def setUp(self):
        self.engine = MultiTimeframeStructureEngine()

    def test_aggregate_h1_to_h4(self):
        bars_1h = [
            CandleBar(open=1.1000 + i * 0.0005, high=1.1010 + i * 0.0005, low=1.0995 + i * 0.0005, close=1.1008 + i * 0.0005, volume=100.0)
            for i in range(12)
        ]
        h4_bars = self.engine.aggregate_h1_to_h4(bars_1h)
        self.assertEqual(len(h4_bars), 3)  # 12 H1 bars = 3 H4 bars
        self.assertEqual(h4_bars[0].open, bars_1h[0].open)
        self.assertEqual(h4_bars[0].close, bars_1h[3].close)
        self.assertEqual(h4_bars[0].high, max(b.high for b in bars_1h[:4]))
        self.assertEqual(h4_bars[0].low, min(b.low for b in bars_1h[:4]))

    def test_htf_bullish_alignment(self):
        # 40 bars of steady uptrend
        bars_1h = [
            CandleBar(open=1.1000 + i * 0.001, high=1.1015 + i * 0.001, low=1.0990 + i * 0.001, close=1.1010 + i * 0.001, volume=200.0)
            for i in range(40)
        ]
        result = self.engine.check_htf_alignment(
            symbol="EURUSD",
            direction="BUY",
            entry_price=bars_1h[-1].close,
            bars_1h=bars_1h,
        )
        self.assertTrue(result.is_aligned)
        self.assertEqual(result.htf_trend_bias, "BULLISH_FLOW")
        self.assertFalse(result.barrier_conflict)


if __name__ == "__main__":
    unittest.main()
