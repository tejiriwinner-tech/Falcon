"""
Unit tests for AIDecisionEngine
Tests AI decision logic and reasoning.
"""
import unittest
from app.services.decision.decision_engine import AIDecisionEngine
from app.schemas.decision_models import DecisionType
from app.schemas.trend_models import TrendResult, TrendDirection as TrendDir, TrendStrength
from app.schemas.market_structure_models import (
    MarketStructureResult, StructureDirection, StructureEvent
)
from app.schemas.indicator_models import IndicatorResponse
from app.schemas.confluence_models import MultiTimeframeConfluenceResult, MultiTimeframeRecommendation
from app.schemas.signal_score_models import SignalScoreResult, RiskRating


class TestAIDecisionEngine(unittest.TestCase):
    """Test cases for AIDecisionEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = AIDecisionEngine()
    
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
    
    def _create_mt_confluence_result(self, score: float = 91.0, recommendation: str = "BUY") -> MultiTimeframeConfluenceResult:
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
    
    def _create_signal_score_result(
        self,
        score: float = 96.0,
        risk: str = "LOW"
    ) -> SignalScoreResult:
        """Create a mock signal score result."""
        return SignalScoreResult(
            symbol="XAUUSD",
            timeframe="H1",
            overallScore=score,
            quality="EXCELLENT",
            recommendation="BUY",
            confidence=95.0,
            componentScores=[],
            riskRating=RiskRating(risk),
            analysisSummary="Test summary"
        )
    
    def test_strong_buy_decision(self):
        """Test STRONG_BUY decision."""
        trend_result = self._create_trend_result("BULLISH", "VERY_STRONG", 95.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 90.0)
        structure_result.liquidityZones = [2035.0, 2040.0]  # Add liquidity zones
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(91.0, "BUY")
        signal_score_result = self._create_signal_score_result(96.0, "LOW")
        
        result = self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        self.assertEqual(result.decision, DecisionType.STRONG_BUY)
        self.assertEqual(result.confidence, 97.0)
        self.assertGreater(len(result.reasoning), 0)
    
    def test_buy_decision(self):
        """Test BUY decision."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 80.0)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(75.0, "BUY")
        signal_score_result = self._create_signal_score_result(88.0, "LOW")
        
        result = self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        self.assertEqual(result.decision, DecisionType.BUY)
        self.assertEqual(result.confidence, 92.0)
        self.assertGreater(len(result.reasoning), 0)
    
    def test_sell_decision(self):
        """Test SELL decision."""
        trend_result = self._create_trend_result("BEARISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BEARISH", "BOS", 80.0)
        indicator_result = self._create_indicator_result(45.0, -5.0, -4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(75.0, "SELL")
        signal_score_result = self._create_signal_score_result(88.0, "LOW")
        
        result = self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        self.assertEqual(result.decision, DecisionType.SELL)
        self.assertEqual(result.confidence, 92.0)
        self.assertGreater(len(result.reasoning), 0)
    
    def test_strong_sell_decision(self):
        """Test STRONG_SELL decision."""
        trend_result = self._create_trend_result("BEARISH", "VERY_STRONG", 95.0)
        structure_result = self._create_structure_result("BEARISH", "BOS", 90.0)
        structure_result.liquidityZones = [2035.0, 2040.0]  # Add liquidity zones
        indicator_result = self._create_indicator_result(45.0, -5.0, -4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(91.0, "SELL")
        signal_score_result = self._create_signal_score_result(96.0, "LOW")
        
        result = self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        self.assertEqual(result.decision, DecisionType.STRONG_SELL)
        self.assertEqual(result.confidence, 97.0)
        self.assertGreater(len(result.reasoning), 0)
    
    def test_wait_decision_conflict(self):
        """Test WAIT decision due to trend-structure conflict."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BEARISH", "BOS", 80.0)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(60.0, "WAIT")
        signal_score_result = self._create_signal_score_result(65.0, "MEDIUM")
        
        result = self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        self.assertEqual(result.decision, DecisionType.WAIT)
        self.assertEqual(result.confidence, 43.0)
        self.assertIn("conflicts", result.reasoning[0].lower())
    
    def test_wait_decision_low_confluence(self):
        """Test WAIT decision due to low confluence."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 80.0)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(55.0, "BUY")
        signal_score_result = self._create_signal_score_result(75.0, "MEDIUM")
        
        result = self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        self.assertEqual(result.decision, DecisionType.WAIT)
        self.assertIn("confluence", " ".join(result.reasoning).lower())
    
    def test_no_trade_decision(self):
        """Test NO_TRADE decision."""
        trend_result = self._create_trend_result("UNKNOWN", "WEAK", 40.0)
        structure_result = self._create_structure_result("NEUTRAL", "NONE", 40.0)
        indicator_result = self._create_indicator_result(50.0, 0.0, 0.0, 10.0)
        mt_confluence_result = self._create_mt_confluence_result(40.0, "NO_TRADE")
        signal_score_result = self._create_signal_score_result(45.0, "HIGH")
        
        result = self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        self.assertEqual(result.decision, DecisionType.NO_TRADE)
        self.assertEqual(result.confidence, 0.0)
    
    def test_no_trade_unknown_trend(self):
        """Test NO_TRADE decision with unknown trend."""
        trend_result = self._create_trend_result("UNKNOWN", "WEAK", 40.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 80.0)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(75.0, "BUY")
        signal_score_result = self._create_signal_score_result(88.0, "LOW")
        
        result = self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        self.assertEqual(result.decision, DecisionType.NO_TRADE)
        self.assertIn("Unknown trend", result.reasoning[0])
    
    def test_warning_generation(self):
        """Test warning generation."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 55.0)  # Low confidence
        structure_result = self._create_structure_result("BULLISH", "BOS", 80.0)
        indicator_result = self._create_indicator_result(75.0, 5.0, 4.0, 50.0)  # High ATR
        mt_confluence_result = self._create_mt_confluence_result(60.0, "BUY")
        signal_score_result = self._create_signal_score_result(75.0, "HIGH")
        
        result = self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        self.assertGreater(len(result.warnings), 0)
    
    def test_confidence_calculation(self):
        """Test confidence calculation."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 80.0)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(75.0, "BUY")
        signal_score_result = self._create_signal_score_result(88.0, "LOW")
        
        result = self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 100.0)
    
    def test_explainability(self):
        """Test decision explainability."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 80.0)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(75.0, "BUY")
        signal_score_result = self._create_signal_score_result(88.0, "LOW")
        
        result = self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        self.assertGreater(len(result.reasoning), 0)
        for reason in result.reasoning:
            self.assertGreater(len(reason), 0)
    
    def test_cache_behavior(self):
        """Test cache behavior."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 80.0)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(75.0, "BUY")
        signal_score_result = self._create_signal_score_result(88.0, "LOW")
        
        # First call - cache miss
        result1 = self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        # Second call - cache hit
        result2 = self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        self.assertEqual(result1.decision, result2.decision)
        self.assertEqual(result1.confidence, result2.confidence)
        
        stats = self.engine.get_statistics()
        self.assertEqual(stats['cacheHits'], 1)
        self.assertEqual(stats['cacheMisses'], 1)
    
    def test_statistics_tracking(self):
        """Test statistics tracking."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 80.0)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(75.0, "BUY")
        signal_score_result = self._create_signal_score_result(88.0, "LOW")
        
        # Perform decision
        self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        # Check statistics
        stats = self.engine.get_statistics()
        
        self.assertEqual(stats['totalDecisions'], 1)
        self.assertEqual(stats['buyCount'], 1)
        self.assertGreater(stats['averageConfidence'], 0)
        self.assertGreater(stats['averageExecutionTime'], 0)
    
    def test_statistics_reset(self):
        """Test statistics reset."""
        trend_result = self._create_trend_result("BULLISH", "STRONG", 85.0)
        structure_result = self._create_structure_result("BULLISH", "BOS", 80.0)
        indicator_result = self._create_indicator_result(55.0, 5.0, 4.0, 15.0)
        mt_confluence_result = self._create_mt_confluence_result(75.0, "BUY")
        signal_score_result = self._create_signal_score_result(88.0, "LOW")
        
        # Perform decision
        self.engine.make_decision(
            "XAUUSD", "H1", trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        # Reset statistics
        self.engine.reset_statistics()
        
        # Check statistics are reset
        stats = self.engine.get_statistics()
        
        self.assertEqual(stats['totalDecisions'], 0)
        self.assertEqual(stats['buyCount'], 0)
        self.assertEqual(stats['sellCount'], 0)
        self.assertEqual(stats['waitCount'], 0)
        self.assertEqual(stats['averageConfidence'], 0.0)
        self.assertEqual(stats['averageExecutionTime'], 0.0)
        self.assertEqual(stats['cacheHits'], 0)
        self.assertEqual(stats['cacheMisses'], 0)
    
    def test_no_data(self):
        """Test with no data."""
        result = self.engine.make_decision("XAUUSD", "H1")
        
        self.assertEqual(result.decision, DecisionType.NO_TRADE)
        self.assertEqual(result.confidence, 0.0)


if __name__ == '__main__':
    unittest.main()
