"""
Unit tests for Indicator models
Tests indicator result schemas.
"""
import unittest
from datetime import datetime, timezone
from app.schemas.indicator_models import IndicatorResult, IndicatorResponse, IndicatorStatistics


class TestIndicatorResult(unittest.TestCase):
    """Test cases for IndicatorResult model."""
    
    def test_create_indicator_result(self):
        """Test creating an indicator result."""
        result = IndicatorResult(
            name="RSI_14",
            value=65.5,
            signal="NEUTRAL",
            strength=35.0,
            timestamp=datetime.now(timezone.utc)
        )
        
        self.assertEqual(result.name, "RSI_14")
        self.assertEqual(result.value, 65.5)
        self.assertEqual(result.signal, "NEUTRAL")
        self.assertEqual(result.strength, 35.0)
    
    def test_indicator_result_defaults(self):
        """Test indicator result default values."""
        result = IndicatorResult(name="TEST")
        
        self.assertEqual(result.signal, "NEUTRAL")
        self.assertEqual(result.strength, 0.0)
        self.assertIsNone(result.value)
    
    def test_strength_validation(self):
        """Test strength validation (0-100)."""
        # Valid strengths
        result1 = IndicatorResult(name="TEST", strength=0.0)
        result2 = IndicatorResult(name="TEST", strength=50.0)
        result3 = IndicatorResult(name="TEST", strength=100.0)
        
        self.assertEqual(result1.strength, 0.0)
        self.assertEqual(result2.strength, 50.0)
        self.assertEqual(result3.strength, 100.0)


class TestIndicatorResponse(unittest.TestCase):
    """Test cases for IndicatorResponse model."""
    
    def test_create_indicator_response(self):
        """Test creating an indicator response."""
        response = IndicatorResponse(
            symbol="XAUUSD",
            timeframe="H1",
            ema_20=2040.5,
            ema_50=2035.2,
            rsi_14=58.3,
            atr_14=15.2,
            trend="BULLISH",
            signal="BUY",
            strength=65.0
        )
        
        self.assertEqual(response.symbol, "XAUUSD")
        self.assertEqual(response.timeframe, "H1")
        self.assertEqual(response.ema_20, 2040.5)
        self.assertEqual(response.trend, "BULLISH")
        self.assertEqual(response.signal, "BUY")
        self.assertEqual(response.strength, 65.0)
    
    def test_indicator_response_defaults(self):
        """Test indicator response default values."""
        response = IndicatorResponse(
            symbol="XAUUSD",
            timeframe="H1"
        )
        
        self.assertEqual(response.trend, "NEUTRAL")
        self.assertEqual(response.signal, "NEUTRAL")
        self.assertEqual(response.strength, 0.0)
        self.assertIsNone(response.ema_20)
        self.assertIsNone(response.rsi_14)


class TestIndicatorStatistics(unittest.TestCase):
    """Test cases for IndicatorStatistics model."""
    
    def test_create_indicator_statistics(self):
        """Test creating indicator statistics."""
        stats = IndicatorStatistics(
            calculation_count=100,
            total_execution_time=2.5,
            average_execution_time=0.025,
            cache_hits=80,
            cache_misses=20
        )
        
        self.assertEqual(stats.calculation_count, 100)
        self.assertEqual(stats.total_execution_time, 2.5)
        self.assertEqual(stats.average_execution_time, 0.025)
        self.assertEqual(stats.cache_hits, 80)
        self.assertEqual(stats.cache_misses, 20)
    
    def test_indicator_statistics_defaults(self):
        """Test indicator statistics default values."""
        stats = IndicatorStatistics()
        
        self.assertEqual(stats.calculation_count, 0)
        self.assertEqual(stats.total_execution_time, 0.0)
        self.assertEqual(stats.average_execution_time, 0.0)
        self.assertEqual(stats.cache_hits, 0)
        self.assertEqual(stats.cache_misses, 0)


if __name__ == '__main__':
    unittest.main()
