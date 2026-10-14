import unittest
from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.order_flow_engine import OrderFlowEngine
from app.core.services.local_candle_aggregator import LocalCandleAggregator


class TestOrderFlowEngine(unittest.TestCase):
    def setUp(self):
        self.engine = OrderFlowEngine()

    def test_intra_bar_delta_calculation(self):
        # Candle where Close is near High -> strong positive delta
        c_bull = CandleBar(open=1.1000, high=1.1050, low=1.0990, close=1.1045, volume=1000.0)
        delta_bull = self.engine.calculate_bar_delta(c_bull)
        self.assertGreater(delta_bull, 0)
        self.assertLessEqual(delta_bull, 1000.0)

        # Candle where Close is near Low -> strong negative delta
        c_bear = CandleBar(open=1.1040, high=1.1050, low=1.0990, close=1.0995, volume=1000.0)
        delta_bear = self.engine.calculate_bar_delta(c_bear)
        self.assertLess(delta_bear, 0)
        self.assertGreaterEqual(delta_bear, -1000.0)

        # Flat / Doji Candle -> zero / neutral delta
        c_doji = CandleBar(open=1.1000, high=1.1020, low=1.0980, close=1.1000, volume=500.0)
        delta_doji = self.engine.calculate_bar_delta(c_doji)
        self.assertAlmostEqual(delta_doji, 0.0, places=1)

    def test_rolling_cvd_accumulation(self):
        candles = [
            CandleBar(open=1.1000 + i * 0.001, high=1.1010 + i * 0.001, low=1.0995 + i * 0.001, close=1.1008 + i * 0.001, volume=100.0)
            for i in range(25)
        ]
        cvd_series = self.engine.calculate_cvd(candles, window=20)
        self.assertEqual(len(cvd_series), 25)
        # In a consistent upward drift, CVD should be strongly positive
        self.assertGreater(cvd_series[-1], 0)

    def test_absorption_wick_detection(self):
        # Long upper wick (50% of range) with high volume (1500 vs avg 500) -> upper absorption
        c_upper_abs = CandleBar(open=1.1000, high=1.1100, low=1.0990, close=1.1020, volume=1500.0)
        u_ratio, l_ratio, is_u_abs, is_l_abs = self.engine.detect_absorption_wicks(c_upper_abs, avg_volume=500.0)
        self.assertGreaterEqual(u_ratio, 0.40)
        self.assertTrue(is_u_abs)
        self.assertFalse(is_l_abs)

        # Long lower wick (50% of range) with high volume -> lower absorption
        c_lower_abs = CandleBar(open=1.1080, high=1.1090, low=1.0980, close=1.1060, volume=1500.0)
        u_ratio, l_ratio, is_u_abs, is_l_abs = self.engine.detect_absorption_wicks(c_lower_abs, avg_volume=500.0)
        self.assertGreaterEqual(l_ratio, 0.40)
        self.assertTrue(is_l_abs)
        self.assertFalse(is_u_abs)

    def test_local_candle_aggregator_live_delta(self):
        agg = LocalCandleAggregator()
        # Simulate ticks: 5 upticks, 2 downticks
        agg.on_tick("EURUSD", 1.1000, 1.1001, 1.1000, 1000)
        agg.on_tick("EURUSD", 1.1002, 1.1003, 1.1002, 1001)
        agg.on_tick("EURUSD", 1.1005, 1.1006, 1.1005, 1002)
        agg.on_tick("EURUSD", 1.1003, 1.1004, 1.1003, 1003)  # down
        agg.on_tick("EURUSD", 1.1007, 1.1008, 1.1007, 1004)  # up
        agg.on_tick("EURUSD", 1.1006, 1.1007, 1.1006, 1005)  # down
        agg.on_tick("EURUSD", 1.1010, 1.1011, 1.1010, 1006)  # up

        of = agg.get_developing_order_flow("EURUSD", "15m")
        self.assertIsNotNone(of)
        self.assertGreater(of["buy_volume"], of["sell_volume"])
        self.assertGreater(of["delta"], 0)
        self.assertIsNotNone(of["poc_price"])


if __name__ == "__main__":
    unittest.main()
