"""
Unit tests for SignalScoringEngine
Tests signal quality scoring logic.
"""
import unittest
from app.services.signals.signal_scoring_engine import SignalScoringEngine
from app.schemas.signal_score_models import (
    SignalQuality, SignalRecommendation, RiskRating
)
from app.schemas.trend_models import TrendResult, TrendDirection as TrendDir, TrendStrength
from app.schemas.market_structure_models import (
    MarketStructureResult, StructureDirection, StructureEvent
)
from app.schemas.indicator_models import IndicatorResponse
from app.schemas.confluence_models import MultiTimeframeConfluenceResult, MultiTimeframeRecommendation


class TestSignalScoringEngine(unittest.TestCase):
    """Test cases for SignalScoringEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = SignalScoringEngine()
    
    def _create_trend_result(self, direction: str = "BULLISH", strength: str = "STRONG", confidence: float = 85.0) -> TrendResult:
        """Create a mock trend result."""
        return TrendResult(
            symbol="XAUUSD",
            timeframe="H1",
            direction=TrendDir(direction),
            strength=TrendStrength(strength),
            confidence=confidence,
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
        event: str = "BOS",
        confidence: float = 78.5
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
            confidence=confidence,
            analysis="Test structure"
        )
    
    def _create_indicator_result(
        self,
        rsi: float = 55.0,
        macd_line: float = 5.0,
        macd_signal: float = 4.0,
        atr: float = 15.0
    ) -> IndicatorResponse:
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
            rsi_14=rsi,
            atr_14=atr,
            macd_line=macd_line,
            macd_signal=macd_signal,
            macd_histogram=1.0,
            bb_upper=2035.0,
            bb_middle=2020.0,
            bb_lower=2005.0,
            trend="BULLISH",
            signal="BUY",
            strength=65.0
        )
    
    def _create_mt_confluence_result(self, score: float = 89.0, recommendation: str = "BUY") -> MultiTimeframeConfluenceResult:
        """Create a mock MT confluence result."""
        return MultiTimeframeConfluenceResult(
            symbol="XAUUSD",
            analyses=[],
            alignedTimeframes=[],
            conflictingTimeframes=[],
            overallConfluenceScore=score,
            recommendation=MultiTimeframeRecommendation(recommendation),
            recommendationReason="Test reason"
        )
    
    def test_excellent_setup(self):
        """Test excellent signal setup (high score)."""
        trend_result = self._create_trend_result("BULLISH", "VERY_STRONG", 95.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 90.0)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(95.0, "BUY")
        
        result = self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(result.timeframe, "H1")
        self.assertGreaterEqual(result.overallScore, 70.0)
        self.assertEqual(result.quality, SignalQuality.GOOD)
        self.assertEqual(result.recommendation, SignalRecommendation.BUY)
    
    def test_good_setup(self):
        """Test good signal setup (70-84 score)."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 80.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 75.0)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(80.0, "BUY")
        
        result = self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(result.timeframe, "H1")
        self.assertGreaterEqual(result.overallScore, 70.0)
        self.assertLess(result.overallScore, 85.0)
        self.assertEqual(result.quality, SignalQuality.GOOD)
        self.assertEqual(result.recommendation, SignalRecommendation.BUY)
    
    def test_poor_setup(self):
        """Test poor signal setup (< 55 score)."""
        trend_result = self._create_trend_result("SIDEWAYS", "WEAK", 40.0)
        structure_result = self._create_structure_result("NEUTRAL", "NONE", 40.0)
        indicator_result = self._create_indicator_result(25.0, -2.0, -1.0, 5.0)
        mt_confluence_result = self._create_mt_confluence_result(40.0, "NO_TRADE")
        
        result = self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(result.timeframe, "H1")
        self.assertLess(result.overallScore, 55.0)
        self.assertEqual(result.quality, SignalQuality.POOR)
        self.assertEqual(result.recommendation, SignalRecommendation.NO_SIGNAL)
    
    def test_strong_buy_recommendation(self):
        """Test BUY recommendation (strong setup)."""
        trend_result = self._create_trend_result("BULLISH", "VERY_STRONG", 95.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 90.0)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(95.0, "BUY")
        
        result = self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        self.assertEqual(result.recommendation, SignalRecommendation.BUY)
    
    def test_strong_sell_recommendation(self):
        """Test SELL recommendation (strong setup)."""
        trend_result = self._create_trend_result("BEARISH", "VERY_STRONG", 95.0)
        structure_result = self._create_structure_result("BEARISH", "BOS", 90.0)
        indicator_result = self._create_indicator_result(45.0, -5.0, -4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(95.0, "SELL")
        
        result = self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        self.assertEqual(result.recommendation, SignalRecommendation.SELL)
    
    def test_wait_recommendation(self):
        """Test WAIT recommendation."""
        trend_result = self._create_trend_result("BULLISH", "MODERATE", 60.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 60.0)
        indicator_result = self._create_indicator_result(55.0, 2.0, 1.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(60.0, "BUY")
        
        result = self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        self.assertEqual(result.recommendation, SignalRecommendation.WAIT)
    
    def test_component_scores(self):
        """Test that all component scores are calculated."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 78.5)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(89.0, "BUY")
        
        result = self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        self.assertEqual(len(result.componentScores), 6)
        component_names = [cs.componentName for cs in result.componentScores]
        self.assertIn("Trend", component_names)
        self.assertIn("Structure", component_names)
        self.assertIn("SupportResistance", component_names)
        self.assertIn("Momentum", component_names)
        self.assertIn("Liquidity", component_names)
        self.assertIn("MultiTimeframeConfluence", component_names)
    
    def test_explainability(self):
        """Test that each component has an explanation."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 78.5)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(89.0, "BUY")
        
        result = self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        for component in result.componentScores:
            self.assertIsNotNone(component.explanation)
            self.assertGreater(len(component.explanation), 0)
    
    def test_risk_rating_low(self):
        """Test LOW risk rating."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 80.0)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 10.0)  # Low ATR
        mt_confluence_result = self._create_mt_confluence_result(85.0, "BUY")
        
        result = self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        self.assertEqual(result.riskRating, RiskRating.LOW)
    
    def test_risk_rating_high(self):
        """Test HIGH risk rating."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 50.0)  # Low confidence
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 50.0)  # High ATR
        mt_confluence_result = self._create_mt_confluence_result(60.0, "BUY")  # Low confluence
        
        result = self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        self.assertEqual(result.riskRating, RiskRating.HIGH)
    
    def test_cache_behavior(self):
        """Test cache behavior."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 78.5)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(89.0, "BUY")
        
        # First call - cache miss
        result1 = self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        # Second call - cache hit
        result2 = self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        self.assertEqual(result1.symbol, result2.symbol)
        self.assertEqual(result1.overallScore, result2.overallScore)
        
        stats = self.engine.get_statistics()
        self.assertEqual(stats['cacheHits'], 1)
        self.assertEqual(stats['cacheMisses'], 1)
    
    def test_statistics_tracking(self):
        """Test statistics tracking."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 78.5)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(89.0, "BUY")
        
        # Perform calculation
        self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        # Check statistics
        stats = self.engine.get_statistics()
        
        self.assertEqual(stats['calculations'], 1)
        self.assertGreater(stats['averageExecutionTime'], 0)
        self.assertIsNotNone(stats['highestScore'])
        self.assertIsNotNone(stats['lowestScore'])
    
    def test_statistics_reset(self):
        """Test statistics reset."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 78.5)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(89.0, "BUY")
        
        # Perform calculation
        self.engine.calculate_signal_score(
            "XAUUSD", "H1", trend_result, structure_result, indicator_result, mt_confluence_result, 2045.0
        )
        
        # Reset statistics
        self.engine.reset_statistics()
        
        # Check statistics are reset
        stats = self.engine.get_statistics()
        
        self.assertEqual(stats['calculations'], 0)
        self.assertEqual(stats['cacheHits'], 0)
        self.assertEqual(stats['cacheMisses'], 0)
        self.assertEqual(stats['averageExecutionTime'], 0.0)
        self.assertIsNone(stats['highestScore'])
        self.assertIsNone(stats['lowestScore'])
    
    def test_no_data(self):
        """Test with no data (invalid setup)."""
        result = self.engine.calculate_signal_score("XAUUSD", "H1")
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(result.timeframe, "H1")
        self.assertEqual(result.overallScore, 0.0)
        self.assertEqual(result.quality, SignalQuality.INVALID)
        self.assertEqual(result.recommendation, SignalRecommendation.NO_SIGNAL)


if __name__ == '__main__':
    unittest.main()
