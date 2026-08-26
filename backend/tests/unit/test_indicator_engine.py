"""
Unit tests for IndicatorEngine
Tests technical indicator calculations.
"""
import unittest
from app.services.indicators.indicator_engine import IndicatorEngine


class TestIndicatorEngine(unittest.TestCase):
    """Test cases for IndicatorEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = IndicatorEngine()
    
    def test_calculate_ema(self):
        """Test EMA calculation."""
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 
                  111, 112, 113, 114, 115, 116, 117, 118, 119, 120]
        
        result = self.engine.calculate_ema(prices, 20)
        
        # Should return list of same length
        self.assertEqual(len(result), len(prices))
        
        # EMA calculation starts from first element in pandas ewm
        self.assertIsNotNone(result[18])
        
        # Last value should not be None
        self.assertIsNotNone(result[-1])
        
        # EMA should be close to last price for trending data
        self.assertGreater(result[-1], 100)
    
    def test_calculate_sma(self):
        """Test SMA calculation."""
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110,
                  111, 112, 113, 114, 115, 116, 117, 118, 119, 120]
        
        result = self.engine.calculate_sma(prices, 20)
        
        # Should return list of same length
        self.assertEqual(len(result), len(prices))
        
        # First 19 values should be nan (NaN representing missing data in pandas)
        import math
        self.assertTrue(math.isnan(result[18]))
        
        # Last value should not be None
        self.assertIsNotNone(result[-1])
        
        # SMA should be average-like
        self.assertGreater(result[-1], 100)
    
    def test_calculate_rsi(self):
        """Test RSI calculation."""
        prices = [100, 102, 104, 103, 105, 107, 106, 108, 110, 109, 111,
                  113, 112, 114, 116, 115, 117, 119, 118, 120, 122]
        
        result = self.engine.calculate_rsi(prices, 14)
        
        # Should return list of same length
        self.assertEqual(len(result), len(prices))
        
        # First 13 values should be nan (NaN representing missing data in pandas)
        import math
        self.assertTrue(math.isnan(result[12]))
        
        # Last value should not be None
        self.assertIsNotNone(result[-1])
        
        # RSI should be between 0 and 100
        if result[-1] is not None:
            self.assertGreaterEqual(result[-1], 0)
            self.assertLessEqual(result[-1], 100)
    
    def test_calculate_atr(self):
        """Test ATR calculation."""
        highs = [105, 107, 109, 108, 110, 112, 111, 113, 115, 114, 116,
                 118, 117, 119, 121, 120, 122, 124, 123, 125, 127]
        lows = [95, 97, 99, 98, 100, 102, 101, 103, 105, 104, 106,
                108, 107, 109, 111, 110, 112, 114, 113, 115, 117]
        closes = [100, 102, 104, 103, 105, 107, 106, 108, 110, 109, 111,
                  113, 112, 114, 116, 115, 117, 119, 118, 120, 122]
        
        result = self.engine.calculate_atr(highs, lows, closes, 14)
        
        # Should return list of same length
        self.assertEqual(len(result), len(closes))
        
        # First 13 values should be nan (NaN representing missing data in pandas)
        import math
        self.assertTrue(math.isnan(result[12]))
        
        # Last value should not be None
        self.assertIsNotNone(result[-1])
        
        # ATR should be positive
        if result[-1] is not None:
            self.assertGreater(result[-1], 0)
    
    def test_calculate_macd(self):
        """Test MACD calculation."""
        prices = [100 + i for i in range(50)]
        
        macd_line, signal_line, histogram = self.engine.calculate_macd(prices)
        
        # All should return lists of same length
        self.assertEqual(len(macd_line), len(prices))
        self.assertEqual(len(signal_line), len(prices))
        self.assertEqual(len(histogram), len(prices))
        
        # Last values should not be None for sufficient data
        self.assertIsNotNone(macd_line[-1])
        self.assertIsNotNone(signal_line[-1])
        self.assertIsNotNone(histogram[-1])
    
    def test_calculate_bollinger_bands(self):
        """Test Bollinger Bands calculation."""
        prices = [100 + i * 0.5 for i in range(30)]
        
        upper, middle, lower = self.engine.calculate_bollinger_bands(prices, 20, 2.0)
        
        # All should return lists of same length
        self.assertEqual(len(upper), len(prices))
        self.assertEqual(len(middle), len(prices))
        self.assertEqual(len(lower), len(prices))
        
        # Last values should not be None for sufficient data
        self.assertIsNotNone(upper[-1])
        self.assertIsNotNone(middle[-1])
        self.assertIsNotNone(lower[-1])
        
        # Upper should be greater than middle, middle greater than lower
        if upper[-1] and middle[-1] and lower[-1]:
            self.assertGreater(upper[-1], middle[-1])
            self.assertGreater(middle[-1], lower[-1])
    
    def test_insufficient_data(self):
        """Test indicators with insufficient data."""
        short_prices = [100, 101, 102]
        
        # All indicators should handle insufficient data gracefully
        ema = self.engine.calculate_ema(short_prices, 20)
        sma = self.engine.calculate_sma(short_prices, 20)
        rsi = self.engine.calculate_rsi(short_prices, 14)
        
        # Should return lists of None
        self.assertTrue(all(v is None for v in ema))
        self.assertTrue(all(v is None for v in sma))
        self.assertTrue(all(v is None for v in rsi))
    
    def test_get_statistics(self):
        """Test engine statistics."""
        stats = self.engine.get_statistics()
        
        # Should return statistics dict
        self.assertIn('calculation_count', stats)
        self.assertIn('total_execution_time', stats)
        self.assertIn('average_execution_time', stats)
        
        # Initial values should be zero
        self.assertEqual(stats['calculation_count'], 0)
        self.assertEqual(stats['total_execution_time'], 0.0)
    
    def test_reset_statistics(self):
        """Test statistics reset."""
        # Perform a calculation
        prices = [100 + i for i in range(50)]
        self.engine.calculate_ema(prices, 20)
        
        # Reset statistics
        self.engine.reset_statistics()
        
        # Statistics should be reset
        stats = self.engine.get_statistics()
        self.assertEqual(stats['calculation_count'], 0)
        self.assertEqual(stats['total_execution_time'], 0.0)


if __name__ == '__main__':
    unittest.main()
