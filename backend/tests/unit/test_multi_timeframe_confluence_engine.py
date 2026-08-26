"""
Unit tests for MultiTimeframeConfluenceEngine
Tests multi-timeframe confluence analysis logic.
"""
import unittest
from datetime import datetime, timezone
from app.services.confluence.multi_timeframe_confluence_engine import MultiTimeframeConfluenceEngine
from app.schemas.confluence_models import (
    MultiTimeframeRecommendation, TimeframeAnalysis, MultiTimeframeConfluenceResult
)
from app.schemas.trend_models import TrendResult, TrendDirection as TrendDir, TrendStrength
from app.schemas.market_structure_models import (
    MarketStructureResult, StructureDirection, StructureEvent, StructureZone, ZoneType
)
from app.schemas.indicator_models import IndicatorResponse


class TestMultiTimeframeConfluenceEngine(unittest.TestCase):
    """Test cases for MultiTimeframeConfluenceEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = MultiTimeframeConfluenceEngine()
    
    def _create_trend_result(self, direction: str = "BULLISH", strength: str = "STRONG") -> TrendResult:
        """Create a mock trend result."""
        return TrendResult(
            symbol="XAUUSD",
            timeframe="H1",
            direction=TrendDir(direction),
            strength=TrendStrength(strength),
            confidence=85.0,
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
    
    def _create_structure_result(
        self,
        direction: str = "BULLISH",
        event: str = "BOS"
    ) -> MarketStructureResult:
        """Create a mock structure result."""
        return MarketStructureResult(
            symbol="XAUUSD",
            timeframe="H1",
            direction=StructureDirection(direction),
            currentEvent=StructureEvent(event),
            lastBos="Bullish BOS",
            lastChoch=None,
            swingHighs=[],
            swingLows=[],
            higherHigh=True,
            higherLow=True,
            lowerHigh=False,
            lowerLow=False,
            support=[2030.0, 2020.0],
            resistance=[2060.0, 2070.0],
            activeSupplyZones=[],
            activeDemandZones=[],
            premiumZone=None,
            discountZone=None,
            liquidityZones=[],
            marketPhase="TRENDING",
            confidence=78.5,
            analysis="Test structure"
        )
    
    def _create_indicator_result(self, trend: str = "BULLISH", signal: str = "BUY") -> IndicatorResponse:
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
            rsi_14=55.0,
            atr_14=15.0,
            macd_line=5.0,
            macd_signal=4.0,
            macd_histogram=1.0,
            bb_upper=2035.0,
            bb_middle=2020.0,
            bb_lower=2005.0,
            trend=trend,
            signal=signal,
            strength=65.0
        )
    
    def _create_timeframe_data(self, direction: str = "BULLISH") -> dict:
        """Create mock timeframe data."""
        return {
            "trend": self._create_trend_result(direction, "STRONG"),
            "structure": self._create_structure_result(direction, "BOS"),
            "indicator": self._create_indicator_result(direction, "BUY" if direction == "BULLISH" else "SELL")
        }
    
    def test_full_bullish_agreement(self):
        """Test full bullish agreement across all timeframes."""
        timeframe_data = {
            "H4": self._create_timeframe_data("BULLISH"),
            "H1": self._create_timeframe_data("BULLISH"),
            "M15": self._create_timeframe_data("BULLISH"),
            "M5": self._create_timeframe_data("BULLISH")
        }
        
        result = self.engine.calculate_confluence("XAUUSD", timeframe_data)
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(result.recommendation, MultiTimeframeRecommendation.BUY)
        self.assertGreaterEqual(result.overallConfluenceScore, 90)
        self.assertIn("bullish", result.recommendationReason.lower())
        self.assertEqual(len(result.alignedTimeframes), 4)
        self.assertEqual(len(result.conflictingTimeframes), 0)
    
    def test_full_bearish_agreement(self):
        """Test full bearish agreement across all timeframes."""
        timeframe_data = {
            "H4": self._create_timeframe_data("BEARISH"),
            "H1": self._create_timeframe_data("BEARISH"),
            "M15": self._create_timeframe_data("BEARISH"),
            "M5": self._create_timeframe_data("BEARISH")
        }
        
        result = self.engine.calculate_confluence("XAUUSD", timeframe_data)
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(result.recommendation, MultiTimeframeRecommendation.SELL)
        self.assertGreaterEqual(result.overallConfluenceScore, 90)
        self.assertIn("bearish", result.recommendationReason.lower())
        self.assertEqual(len(result.alignedTimeframes), 4)
        self.assertEqual(len(result.conflictingTimeframes), 0)
    
    def test_minor_lower_timeframe_disagreement(self):
        """Test minor lower timeframe disagreement."""
        timeframe_data = {
            "H4": self._create_timeframe_data("BULLISH"),
            "H1": self._create_timeframe_data("BULLISH"),
            "M15": self._create_timeframe_data("BULLISH"),
            "M5": self._create_timeframe_data("BEARISH")  # Minor disagreement
        }
        
        result = self.engine.calculate_confluence("XAUUSD", timeframe_data)
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(result.recommendation, MultiTimeframeRecommendation.BUY)
        self.assertGreaterEqual(result.overallConfluenceScore, 50)  # Adjusted due to mixed signals penalty
        self.assertIn("bullish", result.recommendationReason.lower())
    
    def test_mixed_agreement(self):
        """Test mixed agreement (conflicting timeframes)."""
        timeframe_data = {
            "H4": self._create_timeframe_data("BULLISH"),
            "H1": self._create_timeframe_data("BEARISH"),
            "M15": self._create_timeframe_data("BULLISH"),
            "M5": self._create_timeframe_data("BEARISH")
        }
        
        result = self.engine.calculate_confluence("XAUUSD", timeframe_data)
        
        self.assertEqual(result.symbol, "XAUUSD")
        # H4 (40%) + M15 (20%) = 60% bullish vs H1 (30%) + M5 (10%) = 40% bearish
        # Engine favors higher weight (bullish)
        self.assertEqual(result.recommendation, MultiTimeframeRecommendation.BUY)
    
    def test_sideways_markets(self):
        """Test sideways/neutral markets."""
        timeframe_data = {
            "H4": self._create_timeframe_data("UNKNOWN"),
            "H1": self._create_timeframe_data("UNKNOWN"),
            "M15": self._create_timeframe_data("UNKNOWN"),
            "M5": self._create_timeframe_data("UNKNOWN")
        }
        
        result = self.engine.calculate_confluence("XAUUSD", timeframe_data)
        
        self.assertEqual(result.symbol, "XAUUSD")
        # Unknown trends result in WAIT or NO_TRADE depending on confidence
        self.assertIn(result.recommendation, [MultiTimeframeRecommendation.WAIT, MultiTimeframeRecommendation.NO_TRADE])
    
    def test_missing_timeframe_data(self):
        """Test handling of missing timeframe data."""
        timeframe_data = {
            "H4": self._create_timeframe_data("BULLISH"),
            "H1": self._create_timeframe_data("BULLISH"),
            # M15 and M5 missing
        }
        
        result = self.engine.calculate_confluence("XAUUSD", timeframe_data)
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(len(result.analyses), 2)  # Only 2 timeframes have data
    
    def test_cache_behavior(self):
        """Test cache behavior."""
        timeframe_data = {
            "H4": self._create_timeframe_data("BULLISH"),
            "H1": self._create_timeframe_data("BULLISH"),
            "M15": self._create_timeframe_data("BULLISH"),
            "M5": self._create_timeframe_data("BULLISH")
        }
        
        # First call - cache miss
        result1 = self.engine.calculate_confluence("XAUUSD", timeframe_data)
        
        # Second call - cache hit
        result2 = self.engine.calculate_confluence("XAUUSD", timeframe_data)
        
        self.assertEqual(result1.symbol, result2.symbol)
        self.assertEqual(result1.overallConfluenceScore, result2.overallConfluenceScore)
        
        stats = self.engine.get_statistics()
        self.assertEqual(stats['cacheHits'], 1)
        self.assertEqual(stats['cacheMisses'], 1)
    
    def test_statistics_tracking(self):
        """Test statistics tracking."""
        timeframe_data = {
            "H4": self._create_timeframe_data("BULLISH"),
            "H1": self._create_timeframe_data("BULLISH"),
            "M15": self._create_timeframe_data("BULLISH"),
            "M5": self._create_timeframe_data("BULLISH")
        }
        
        # Perform calculation
        self.engine.calculate_confluence("XAUUSD", timeframe_data)
        
        # Check statistics
        stats = self.engine.get_statistics()
        
        self.assertEqual(stats['calculations'], 1)
        self.assertGreater(stats['averageExecutionTime'], 0)
        self.assertIsNotNone(stats['fastestCalculation'])
        self.assertIsNotNone(stats['slowestCalculation'])
    
    def test_statistics_reset(self):
        """Test statistics reset."""
        timeframe_data = {
            "H4": self._create_timeframe_data("BULLISH"),
            "H1": self._create_timeframe_data("BULLISH"),
            "M15": self._create_timeframe_data("BULLISH"),
            "M5": self._create_timeframe_data("BULLISH")
        }
        
        # Perform calculation
        self.engine.calculate_confluence("XAUUSD", timeframe_data)
        
        # Reset statistics
        self.engine.reset_statistics()
        
        # Check statistics are reset
        stats = self.engine.get_statistics()
        
        self.assertEqual(stats['calculations'], 0)
        self.assertEqual(stats['cacheHits'], 0)
        self.assertEqual(stats['cacheMisses'], 0)
        self.assertEqual(stats['averageExecutionTime'], 0.0)
        self.assertIsNone(stats['fastestCalculation'])
        self.assertIsNone(stats['slowestCalculation'])
    
    def test_weighted_scoring(self):
        """Test weighted scoring with different timeframes."""
        # H4 should have more weight than M5
        timeframe_data = {
            "H4": self._create_timeframe_data("BULLISH"),
            "M5": self._create_timeframe_data("BEARISH")
        }
        
        result = self.engine.calculate_confluence("XAUUSD", timeframe_data)
        
        # Should lean towards H4 (higher weight)
        self.assertEqual(result.recommendation, MultiTimeframeRecommendation.BUY)
    
    def test_custom_timeframes(self):
        """Test with custom timeframes."""
        timeframe_data = {
            "H1": self._create_timeframe_data("BULLISH"),
            "M15": self._create_timeframe_data("BULLISH")
        }
        
        result = self.engine.calculate_confluence("XAUUSD", timeframe_data, ["H1", "M15"])
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(len(result.analyses), 2)
    
    def test_empty_timeframe_data(self):
        """Test with empty timeframe data."""
        result = self.engine.calculate_confluence("XAUUSD", {})
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(result.overallConfluenceScore, 0.0)
        self.assertEqual(result.recommendation, MultiTimeframeRecommendation.NO_TRADE)
        self.assertEqual(len(result.analyses), 0)


if __name__ == '__main__':
    unittest.main()
