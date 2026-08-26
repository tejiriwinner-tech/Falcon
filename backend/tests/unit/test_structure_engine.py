"""
Unit tests for StructureEngine
Tests market structure detection logic.
"""
import unittest
from datetime import datetime, timezone, timedelta
from app.services.market_structure.structure_engine import StructureEngine
from app.models.market_candle import MarketCandle, Timeframe
from app.schemas.market_structure_models import (
    StructureDirection, StructureEvent, ZoneType, SwingPoint
)
from app.schemas.trend_models import TrendResult, TrendDirection as TrendDir, TrendStrength
from app.schemas.indicator_models import IndicatorResponse


class TestStructureEngine(unittest.TestCase):
    """Test cases for StructureEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = StructureEngine(lookback_left=5, lookback_right=5)
    
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
    
    def _create_trend_result(self, direction: str = "BULLISH") -> TrendResult:
        """Create a mock trend result."""
        return TrendResult(
            symbol="XAUUSD",
            timeframe="H1",
            direction=TrendDir(direction),
            strength=TrendStrength.STRONG,
            confidence=75.0,
            ema_alignment=80.0,
            price_above_ema20=True,
            price_above_ema50=True,
            price_above_ema200=True,
            higher_highs=5,
            higher_lows=4,
            lower_highs=1,
            lower_lows=2,
            analysis="Test trend"
        )
    
    def _create_indicator_result(self) -> IndicatorResponse:
        """Create a mock indicator result."""
        return IndicatorResponse(
            symbol="XAUUSD",
            timeframe="H1",
            ema_20=2025.0,
            ema_50=2020.0,
            ema_100=2015.0,
            ema_200=2010.0,
            sma_20=2024.0,
            sma_50=2019.0,
            rsi_14=65.0,
            atr_14=15.0,
            macd_line=5.0,
            macd_signal=4.0,
            macd_histogram=1.0,
            bb_upper=2035.0,
            bb_middle=2020.0,
            bb_lower=2005.0,
            trend="BULLISH",
            signal="BUY",
            strength=65.0
        )
    
    def test_swing_detection(self):
        """Test swing high and low detection."""
        candles = self._create_test_candles(50, trend="up")
        
        swing_highs, swing_lows = self.engine._detect_swing_points(candles)
        
        # Should detect some swing points
        self.assertIsInstance(swing_highs, list)
        self.assertIsInstance(swing_lows, list)
        
        # Verify swing point structure
        for swing in swing_highs:
            self.assertIsInstance(swing, SwingPoint)
            self.assertEqual(swing.type, "HIGH")
            self.assertGreaterEqual(swing.strength, 0.0)
            self.assertLessEqual(swing.strength, 100.0)
    
    def test_bos_detection(self):
        """Test Break of Structure detection."""
        candles = self._create_test_candles(50, trend="up")
        swing_highs, swing_lows = self.engine._detect_swing_points(candles)
        
        current_event, last_bos, last_choch = self.engine._detect_structural_events(
            candles, swing_highs, swing_lows
        )
        
        # Should return an event
        self.assertIsInstance(current_event, StructureEvent)
        self.assertIn(current_event, [StructureEvent.NONE, StructureEvent.BOS, StructureEvent.CHOCH])
    
    def test_swing_structure_analysis(self):
        """Test swing structure analysis."""
        candles = self._create_test_candles(50, trend="up")
        swing_highs, swing_lows = self.engine._detect_swing_points(candles)
        
        higher_high, higher_low, lower_high, lower_low = self.engine._analyze_swing_structure(
            swing_highs, swing_lows
        )
        
        # For uptrend, should have higher highs
        if len(swing_highs) >= 2:
            self.assertTrue(higher_high or lower_high)
        
        if len(swing_lows) >= 2:
            self.assertTrue(higher_low or lower_low)
    
    def test_support_resistance_detection(self):
        """Test support and resistance detection."""
        candles = self._create_test_candles(50, trend="up")
        swing_highs, swing_lows = self.engine._detect_swing_points(candles)
        
        support, resistance = self.engine._detect_support_resistance(
            candles, swing_highs, swing_lows
        )
        
        # Should return lists
        self.assertIsInstance(support, list)
        self.assertIsInstance(resistance, list)
    
    def test_supply_demand_zones(self):
        """Test supply and demand zone creation."""
        candles = self._create_test_candles(50, trend="up")
        swing_highs, swing_lows = self.engine._detect_swing_points(candles)
        
        supply_zones, demand_zones = self.engine._create_supply_demand_zones(
            candles, swing_highs, swing_lows
        )
        
        # Should return lists
        self.assertIsInstance(supply_zones, list)
        self.assertIsInstance(demand_zones, list)
        
        # Verify zone structure
        for zone in supply_zones:
            self.assertEqual(zone.zoneType, ZoneType.SUPPLY)
            self.assertGreater(zone.high, zone.low)
    
    def test_liquidity_detection(self):
        """Test liquidity zone detection."""
        candles = self._create_test_candles(50, trend="sideways")
        swing_highs, swing_lows = self.engine._detect_swing_points(candles)
        
        liquidity_zones = self.engine._detect_liquidity_zones(
            candles, swing_highs, swing_lows
        )
        
        # Should return list
        self.assertIsInstance(liquidity_zones, list)
    
    def test_premium_discount_calculation(self):
        """Test premium and discount zone calculation."""
        candles = self._create_test_candles(50, trend="up")
        swing_highs, swing_lows = self.engine._detect_swing_points(candles)
        
        premium_zone, discount_zone = self.engine._calculate_premium_discount(
            candles, swing_highs, swing_lows
        )
        
        # Should return zones if swing points exist
        if swing_highs and swing_lows:
            self.assertIsNotNone(premium_zone)
            self.assertIsNotNone(discount_zone)
            self.assertIn("high", premium_zone)
            self.assertIn("low", premium_zone)
            self.assertIn("high", discount_zone)
            self.assertIn("low", discount_zone)
    
    def test_market_phase_classification(self):
        """Test market phase classification."""
        candles = self._create_test_candles(50, trend="up")
        swing_highs, swing_lows = self.engine._detect_swing_points(candles)
        trend_result = self._create_trend_result("BULLISH")
        
        market_phase = self.engine._determine_market_phase(
            trend_result, swing_highs, swing_lows
        )
        
        # Should return a valid phase
        self.assertIn(market_phase, ["TRENDING", "ACCUMULATION", "DISTRIBUTION", "RANGING"])
    
    def test_confidence_calculation(self):
        """Test confidence scoring."""
        candles = self._create_test_candles(50, trend="up")
        swing_highs, swing_lows = self.engine._detect_swing_points(candles)
        trend_result = self._create_trend_result("BULLISH")
        
        confidence = self.engine._calculate_confidence(
            trend_result, swing_highs, swing_lows, StructureEvent.BOS
        )
        
        # Should be between 0 and 100
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 100.0)
    
    def test_insufficient_data(self):
        """Test structure analysis with insufficient data."""
        candles = self._create_test_candles(10)  # Less than minimum 20
        trend_result = self._create_trend_result()
        indicator_result = self._create_indicator_result()
        
        result = self.engine.analyze_structure(candles, trend_result, indicator_result)
        
        self.assertEqual(result.direction, StructureDirection.UNKNOWN)
        self.assertEqual(result.currentEvent, StructureEvent.NONE)
        self.assertEqual(result.confidence, 0.0)
    
    def test_full_structure_analysis(self):
        """Test complete structure analysis."""
        candles = self._create_test_candles(50, trend="up")
        trend_result = self._create_trend_result("BULLISH")
        indicator_result = self._create_indicator_result()
        
        result = self.engine.analyze_structure(candles, trend_result, indicator_result)
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(result.timeframe, "H1")
        self.assertIn(result.direction, [StructureDirection.BULLISH, StructureDirection.BEARISH, StructureDirection.NEUTRAL])
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 100.0)
    
    def test_statistics_tracking(self):
        """Test engine statistics tracking."""
        candles = self._create_test_candles(50, trend="up")
        trend_result = self._create_trend_result("BULLISH")
        indicator_result = self._create_indicator_result()
        
        # Perform calculation
        self.engine.analyze_structure(candles, trend_result, indicator_result)
        
        # Check statistics
        stats = self.engine.get_statistics()
        
        self.assertEqual(stats['calculations'], 1)
        self.assertGreater(stats['average_execution_time'], 0)
        self.assertGreater(stats['total_execution_time'], 0)
    
    def test_statistics_reset(self):
        """Test statistics reset."""
        candles = self._create_test_candles(50, trend="up")
        trend_result = self._create_trend_result("BULLISH")
        indicator_result = self._create_indicator_result()
        
        # Perform calculation
        self.engine.analyze_structure(candles, trend_result, indicator_result)
        
        # Reset statistics
        self.engine.reset_statistics()
        
        # Check statistics are reset
        stats = self.engine.get_statistics()
        
        self.assertEqual(stats['calculations'], 0)
        self.assertEqual(stats['total_execution_time'], 0.0)
        self.assertEqual(stats['average_execution_time'], 0.0)
    
    def test_level_merging(self):
        """Test level merging for support/resistance."""
        levels = [2050.0, 2050.5, 2060.0, 2061.0, 2070.0]
        
        merged = self.engine._merge_levels(levels, threshold=0.002)
        
        # Should merge nearby levels
        self.assertIsInstance(merged, list)
        self.assertLessEqual(len(merged), len(levels))


if __name__ == '__main__':
    unittest.main()
