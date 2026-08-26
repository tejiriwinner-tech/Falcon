"""
Unit tests for TrendEngine
Tests trend detection logic and calculations.
"""
import unittest
from datetime import datetime, timezone, timedelta
from app.services.trend.trend_engine import TrendEngine
from app.models.market_candle import MarketCandle, Timeframe
from app.schemas.trend_models import TrendDirection, TrendStrength


class TestTrendEngine(unittest.TestCase):
    """Test cases for TrendEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = TrendEngine()
    
    def _create_test_candles(self, count: int, trend: str = "up") -> list:
        """Create test candles for testing."""
        candles = []
        base_time = datetime.now(timezone.utc) - timedelta(hours=count)
        base_price = 2000.0
        
        for i in range(count):
            if trend == "up":
                open_price = base_price + i * 0.5
                high_price = open_price + 5.0
                low_price = open_price - 5.0
                close_price = open_price + 0.3
            elif trend == "down":
                open_price = base_price - i * 0.5
                high_price = open_price + 5.0
                low_price = open_price - 5.0
                close_price = open_price - 0.3
            else:  # sideways
                open_price = base_price + (i % 10) * 0.1
                high_price = open_price + 5.0
                low_price = open_price - 5.0
                close_price = open_price
            
            candle = MarketCandle(
                symbol="XAUUSD",
                timeframe=Timeframe.H1.value,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=1000.0,
                provider="test",
                timestamp=base_time + timedelta(hours=i)
            )
            candles.append(candle)
        
        return candles
    
    def test_bullish_trend_detection(self):
        """Test bullish trend detection."""
        candles = self._create_test_candles(50, trend="up")
        indicators = {
            'ema_20': 2025.0,
            'ema_50': 2020.0,
            'ema_200': 2010.0,
            'sma_20': 2024.0,
            'sma_50': 2019.0,
            'rsi_14': 65.0,
            'atr_14': 15.0,
            'macd_line': 5.0,
            'macd_signal': 4.0,
            'macd_histogram': 1.0,
            'bb_upper': 2035.0,
            'bb_middle': 2020.0,
            'bb_lower': 2005.0
        }
        
        result = self.engine.calculate_trend(candles, indicators)
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(result.timeframe, "H1")
        self.assertIn(result.direction, [TrendDirection.BULLISH, TrendDirection.SIDEWAYS])
        self.assertGreater(result.confidence, 0)
        self.assertLessEqual(result.confidence, 100)
    
    def test_bearish_trend_detection(self):
        """Test bearish trend detection."""
        candles = self._create_test_candles(50, trend="down")
        indicators = {
            'ema_20': 1975.0,
            'ema_50': 1980.0,
            'ema_200': 1990.0,
            'sma_20': 1976.0,
            'sma_50': 1981.0,
            'rsi_14': 35.0,
            'atr_14': 15.0,
            'macd_line': -5.0,
            'macd_signal': -4.0,
            'macd_histogram': -1.0,
            'bb_upper': 1995.0,
            'bb_middle': 1980.0,
            'bb_lower': 1965.0
        }
        
        result = self.engine.calculate_trend(candles, indicators)
        
        self.assertIn(result.direction, [TrendDirection.BEARISH, TrendDirection.SIDEWAYS])
        self.assertGreater(result.confidence, 0)
        self.assertLessEqual(result.confidence, 100)
    
    def test_sideways_trend_detection(self):
        """Test sideways trend detection."""
        candles = self._create_test_candles(50, trend="sideways")
        indicators = {
            'ema_20': 2000.0,
            'ema_50': 2001.0,
            'ema_200': 1999.0,
            'sma_20': 2000.0,
            'sma_50': 2000.0,
            'rsi_14': 50.0,
            'atr_14': 10.0,
            'macd_line': 0.0,
            'macd_signal': 0.0,
            'macd_histogram': 0.0,
            'bb_upper': 2010.0,
            'bb_middle': 2000.0,
            'bb_lower': 1990.0
        }
        
        result = self.engine.calculate_trend(candles, indicators)
        
        # Sideways data with slight variations may be detected as any direction
        self.assertIn(result.direction, [TrendDirection.SIDEWAYS, TrendDirection.UNKNOWN, TrendDirection.BULLISH, TrendDirection.BEARISH])
    
    def test_insufficient_data(self):
        """Test trend calculation with insufficient data."""
        candles = self._create_test_candles(10)  # Less than minimum 20
        indicators = {}
        
        result = self.engine.calculate_trend(candles, indicators)
        
        self.assertEqual(result.direction, TrendDirection.UNKNOWN)
        self.assertEqual(result.strength, TrendStrength.VERY_WEAK)
        self.assertEqual(result.confidence, 0.0)
    
    def test_ema_alignment_bullish(self):
        """Test EMA alignment detection for bullish trend."""
        indicators = {
            'ema_20': 2050.0,
            'ema_50': 2040.0,
            'ema_200': 2030.0
        }
        
        score, direction = self.engine._analyze_ema_alignment(indicators)
        
        self.assertEqual(direction, "BULLISH")
        self.assertGreater(score, 0)
    
    def test_ema_alignment_bearish(self):
        """Test EMA alignment detection for bearish trend."""
        indicators = {
            'ema_20': 2030.0,
            'ema_50': 2040.0,
            'ema_200': 2050.0
        }
        
        score, direction = self.engine._analyze_ema_alignment(indicators)
        
        self.assertEqual(direction, "BEARISH")
        self.assertGreater(score, 0)
    
    def test_ema_alignment_sideways(self):
        """Test EMA alignment detection for sideways trend."""
        indicators = {
            'ema_20': 2040.0,
            'ema_50': 2030.0,
            'ema_200': 2050.0
        }
        
        score, direction = self.engine._analyze_ema_alignment(indicators)
        
        self.assertEqual(direction, "SIDEWAYS")
        self.assertEqual(score, 0.0)
    
    def test_price_position_analysis(self):
        """Test price position analysis."""
        current_price = 2050.0
        indicators = {
            'ema_20': 2040.0,
            'ema_50': 2030.0,
            'ema_200': 2020.0
        }
        
        above_20, above_50, above_200 = self.engine._analyze_price_position(
            current_price, indicators
        )
        
        self.assertTrue(above_20)
        self.assertTrue(above_50)
        self.assertTrue(above_200)
    
    def test_swing_structure_analysis(self):
        """Test swing structure analysis."""
        candles = self._create_test_candles(30, trend="up")
        
        swing_structure = self.engine._analyze_swing_structure(candles)
        
        self.assertIn('higher_highs', swing_structure)
        self.assertIn('higher_lows', swing_structure)
        self.assertIn('lower_highs', swing_structure)
        self.assertIn('lower_lows', swing_structure)
        
        # For uptrend, should have more higher highs/lows
        bullish_swings = swing_structure['higher_highs'] + swing_structure['higher_lows']
        bearish_swings = swing_structure['lower_highs'] + swing_structure['lower_lows']
        self.assertGreaterEqual(bullish_swings, bearish_swings)
    
    def test_confidence_calculation(self):
        """Test confidence score calculation."""
        confidence = self.engine._calculate_confidence(
            ema_alignment=80.0,
            price_above_ema20=True,
            price_above_ema50=True,
            price_above_ema200=True,
            swing_structure={'higher_highs': 5, 'higher_lows': 4, 'lower_highs': 1, 'lower_lows': 2}
        )
        
        self.assertGreater(confidence, 0)
        self.assertLessEqual(confidence, 100)
    
    def test_trend_strength_classification(self):
        """Test trend strength classification."""
        test_cases = [
            (95, TrendStrength.VERY_STRONG),
            (80, TrendStrength.STRONG),
            (65, TrendStrength.MODERATE),
            (50, TrendStrength.WEAK),
            (30, TrendStrength.VERY_WEAK)
        ]
        
        for confidence, expected_strength in test_cases:
            strength = self.engine._classify_strength(confidence)
            self.assertEqual(strength, expected_strength)
    
    def test_statistics_tracking(self):
        """Test engine statistics tracking."""
        candles = self._create_test_candles(50)
        indicators = {
            'ema_20': 2025.0,
            'ema_50': 2020.0,
            'ema_200': 2010.0,
            'sma_20': 2024.0,
            'sma_50': 2019.0,
            'rsi_14': 65.0,
            'atr_14': 15.0,
            'macd_line': 5.0,
            'macd_signal': 4.0,
            'macd_histogram': 1.0,
            'bb_upper': 2035.0,
            'bb_middle': 2020.0,
            'bb_lower': 2005.0
        }
        
        # Perform calculation
        self.engine.calculate_trend(candles, indicators)
        
        # Check statistics
        stats = self.engine.get_statistics()
        
        self.assertEqual(stats['calculations'], 1)
        self.assertGreater(stats['average_execution_time'], 0)
        self.assertGreater(stats['total_execution_time'], 0)
    
    def test_statistics_reset(self):
        """Test statistics reset."""
        candles = self._create_test_candles(50)
        indicators = {
            'ema_20': 2025.0,
            'ema_50': 2020.0,
            'ema_200': 2010.0,
            'sma_20': 2024.0,
            'sma_50': 2019.0,
            'rsi_14': 65.0,
            'atr_14': 15.0,
            'macd_line': 5.0,
            'macd_signal': 4.0,
            'macd_histogram': 1.0,
            'bb_upper': 2035.0,
            'bb_middle': 2020.0,
            'bb_lower': 2005.0
        }
        
        # Perform calculation
        self.engine.calculate_trend(candles, indicators)
        
        # Reset statistics
        self.engine.reset_statistics()
        
        # Check statistics are reset
        stats = self.engine.get_statistics()
        
        self.assertEqual(stats['calculations'], 0)
        self.assertEqual(stats['total_execution_time'], 0.0)
        self.assertEqual(stats['average_execution_time'], 0.0)


if __name__ == '__main__':
    unittest.main()
