"""
Unit tests for MarketCandle model
Tests the market candle data model.
"""
import unittest
from datetime import datetime, timezone
from app.models.market_candle import MarketCandle, Timeframe


class TestMarketCandle(unittest.TestCase):
    """Test cases for MarketCandle model."""
    
    def test_create_candle(self):
        """Test creating a market candle."""
        candle = MarketCandle(
            symbol="XAUUSD",
            timeframe=Timeframe.H1.value,
            open=2040.5,
            high=2045.0,
            low=2038.0,
            close=2042.5,
            volume=1000.0,
            provider="test_provider",
            timestamp=datetime.now(timezone.utc)
        )
        
        self.assertEqual(candle.symbol, "XAUUSD")
        self.assertEqual(candle.timeframe, "H1")
        self.assertEqual(candle.open, 2040.5)
        self.assertEqual(candle.high, 2045.0)
        self.assertEqual(candle.low, 2038.0)
        self.assertEqual(candle.close, 2042.5)
        self.assertEqual(candle.volume, 1000.0)
        self.assertEqual(candle.provider, "test_provider")
    
    def test_timeframe_enum(self):
        """Test Timeframe enum values."""
        self.assertEqual(Timeframe.M1.value, "M1")
        self.assertEqual(Timeframe.M5.value, "M5")
        self.assertEqual(Timeframe.M15.value, "M15")
        self.assertEqual(Timeframe.M30.value, "M30")
        self.assertEqual(Timeframe.H1.value, "H1")
        self.assertEqual(Timeframe.H4.value, "H4")
        self.assertEqual(Timeframe.D1.value, "D1")
    
    def test_candle_repr(self):
        """Test candle string representation."""
        candle = MarketCandle(
            symbol="XAUUSD",
            timeframe=Timeframe.H1.value,
            open=2040.5,
            high=2045.0,
            low=2038.0,
            close=2042.5,
            volume=1000.0,
            provider="test_provider",
            timestamp=datetime.now(timezone.utc)
        )
        
        repr_str = repr(candle)
        self.assertIn("XAUUSD", repr_str)
        self.assertIn("H1", repr_str)
        self.assertIn("2042.5", repr_str)


if __name__ == '__main__':
    unittest.main()
