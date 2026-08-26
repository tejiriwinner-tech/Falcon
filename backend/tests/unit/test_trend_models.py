"""
Unit tests for Trend models
Tests trend detection schema models.
"""
import unittest
from datetime import datetime, timezone
from app.schemas.trend_models import TrendDirection, TrendStrength, TrendResult, TrendStatistics


class TestTrendDirection(unittest.TestCase):
    """Test cases for TrendDirection enum."""
    
    def test_trend_direction_values(self):
        """Test trend direction enum values."""
        self.assertEqual(TrendDirection.BULLISH.value, "BULLISH")
        self.assertEqual(TrendDirection.BEARISH.value, "BEARISH")
        self.assertEqual(TrendDirection.SIDEWAYS.value, "SIDEWAYS")
        self.assertEqual(TrendDirection.UNKNOWN.value, "UNKNOWN")


class TestTrendStrength(unittest.TestCase):
    """Test cases for TrendStrength enum."""
    
    def test_trend_strength_values(self):
        """Test trend strength enum values."""
        self.assertEqual(TrendStrength.VERY_WEAK.value, "VERY_WEAK")
        self.assertEqual(TrendStrength.WEAK.value, "WEAK")
        self.assertEqual(TrendStrength.MODERATE.value, "MODERATE")
        self.assertEqual(TrendStrength.STRONG.value, "STRONG")
        self.assertEqual(TrendStrength.VERY_STRONG.value, "VERY_STRONG")


class TestTrendResult(unittest.TestCase):
    """Test cases for TrendResult model."""
    
    def test_create_trend_result(self):
        """Test creating a trend result."""
        result = TrendResult(
            symbol="XAUUSD",
            timeframe="H1",
            direction=TrendDirection.BULLISH,
            strength=TrendStrength.STRONG,
            confidence=82.5,
            ema_alignment=90.0,
            price_above_ema20=True,
            price_above_ema50=True,
            price_above_ema200=True,
            higher_highs=5,
            higher_lows=4,
            lower_highs=1,
            lower_lows=2,
            analysis="Strong bullish trend with EMA alignment"
        )
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(result.timeframe, "H1")
        self.assertEqual(result.direction, TrendDirection.BULLISH)
        self.assertEqual(result.strength, TrendStrength.STRONG)
        self.assertEqual(result.confidence, 82.5)
    
    def test_confidence_validation(self):
        """Test confidence score validation (0-100)."""
        # Valid confidence values
        result1 = TrendResult(
            symbol="XAUUSD",
            timeframe="H1",
            direction=TrendDirection.BULLISH,
            strength=TrendStrength.MODERATE,
            confidence=0.0,
            ema_alignment=50.0,
            price_above_ema20=False,
            price_above_ema50=False,
            price_above_ema200=False,
            higher_highs=0,
            higher_lows=0,
            lower_highs=0,
            lower_lows=0,
            analysis="Test"
        )
        
        result2 = TrendResult(
            symbol="XAUUSD",
            timeframe="H1",
            direction=TrendDirection.BULLISH,
            strength=TrendStrength.STRONG,
            confidence=100.0,
            ema_alignment=90.0,
            price_above_ema20=True,
            price_above_ema50=True,
            price_above_ema200=True,
            higher_highs=5,
            higher_lows=4,
            lower_highs=1,
            lower_lows=2,
            analysis="Test"
        )
        
        self.assertEqual(result1.confidence, 0.0)
        self.assertEqual(result2.confidence, 100.0)
    
    def test_swing_counts_validation(self):
        """Test swing count validation (non-negative)."""
        result = TrendResult(
            symbol="XAUUSD",
            timeframe="H1",
            direction=TrendDirection.BULLISH,
            strength=TrendStrength.MODERATE,
            confidence=50.0,
            ema_alignment=50.0,
            price_above_ema20=False,
            price_above_ema50=False,
            price_above_ema200=False,
            higher_highs=0,
            higher_lows=0,
            lower_highs=0,
            lower_lows=0,
            analysis="Test"
        )
        
        self.assertEqual(result.higher_highs, 0)
        self.assertEqual(result.higher_lows, 0)
        self.assertEqual(result.lower_highs, 0)
        self.assertEqual(result.lower_lows, 0)


class TestTrendStatistics(unittest.TestCase):
    """Test cases for TrendStatistics model."""
    
    def test_create_trend_statistics(self):
        """Test creating trend statistics."""
        stats = TrendStatistics(
            calculations=200,
            average_execution_time=1.5,
            cache_hits=150,
            cache_misses=50,
            last_calculation=datetime.now(timezone.utc)
        )
        
        self.assertEqual(stats.calculations, 200)
        self.assertEqual(stats.average_execution_time, 1.5)
        self.assertEqual(stats.cache_hits, 150)
        self.assertEqual(stats.cache_misses, 50)
    
    def test_trend_statistics_defaults(self):
        """Test trend statistics default values."""
        stats = TrendStatistics()
        
        self.assertEqual(stats.calculations, 0)
        self.assertEqual(stats.average_execution_time, 0.0)
        self.assertEqual(stats.cache_hits, 0)
        self.assertEqual(stats.cache_misses, 0)
        self.assertIsNone(stats.last_calculation)


if __name__ == '__main__':
    unittest.main()
