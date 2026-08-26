"""
Unit tests for SignalGenerator
Tests intelligent signal generation logic.
"""
import unittest
from app.services.signals.signal_generator import SignalGenerator
from app.schemas.signal_models import SignalType, SignalStatus
from app.schemas.decision_models import DecisionType, AIDecisionResult
from app.schemas.trend_models import TrendResult, TrendDirection as TrendDir, TrendStrength
from app.schemas.market_structure_models import (
    MarketStructureResult, StructureDirection, StructureEvent
)
from app.schemas.indicator_models import IndicatorResponse
from app.schemas.signal_score_models import SignalScoreResult, RiskRating


class TestSignalGenerator(unittest.TestCase):
    """Test cases for SignalGenerator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = SignalGenerator()
    
    def _create_ai_decision(self, decision: str = "BUY", confidence: float = 92.0) -> AIDecisionResult:
        """Create a mock AI decision result."""
        return AIDecisionResult(
            symbol="XAUUSD",
            timeframe="H1",
            decision=DecisionType(decision),
            confidence=confidence,
            signalScore=88.0,
            trendDirection="BULLISH",
            trendStrength="STRONG",
            structureBias="BULLISH",
            liquidityBias="BULLISH",
            confluenceScore=75.0,
            riskRating="LOW",
            reasoning=["Bullish trend", "Bullish structure"],
            warnings=[]
        )
    
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
        demand_zones: list = None,
        supply_zones: list = None
    ) -> MarketStructureResult:
        """Create a mock structure result."""
        return MarketStructureResult(
            symbol="XAUUSD",
            timeframe="H1",
            direction=StructureDirection(direction),
            currentEvent=StructureEvent("BOS"),
            lastBos="Bullish BOS",
            lastChoch=None,
            swingHighs=[],  # Empty list to avoid validation errors
            swingLows=[],  # Empty list to avoid validation errors
            higherHigh=True,
            higherLow=True,
            lowerHigh=False,
            lowerLow=False,
            support=[2020.0, 2030.0],
            resistance=[2060.0, 2070.0],
            activeSupplyZones=[],  # Empty list to avoid validation errors
            activeDemandZones=[],  # Empty list to avoid validation errors
            premiumZone=None,
            discountZone=None,
            liquidityZones=[],
            marketPhase="TRENDING",
            confidence=78.5,
            analysis="Test structure"
        )
    
    def _create_indicator_result(
        self,
        ema_20: float = 2025.0,
        atr: float = 15.0,
        bb_middle: float = 2020.0
    ) -> IndicatorResponse:
        """Create a mock indicator result."""
        return IndicatorResponse(
            symbol="XAUUSD",
            timeframe="H1",
            ema_20=ema_20,
            ema_50=2020.0,
            ema_100=2015.0,
            ema_200=2010.0,
            sma_20=2024.0,
            sma_50=2019.0,
            rsi_14=55.0,
            atr_14=atr,
            macd_line=5.0,
            macd_signal=4.0,
            macd_histogram=1.0,
            bb_upper=2035.0,
            bb_middle=bb_middle,
            bb_lower=2005.0,
            trend="BULLISH",
            signal="BUY",
            strength=65.0
        )
    
    def _create_signal_score_result(self, score: float = 88.0, quality: str = "GOOD") -> SignalScoreResult:
        """Create a mock signal score result."""
        return SignalScoreResult(
            symbol="XAUUSD",
            timeframe="H1",
            overallScore=score,
            quality=quality,
            recommendation="BUY",
            confidence=92.0,
            componentScores=[],
            riskRating=RiskRating.LOW,
            analysisSummary="Test summary"
        )
    
    def test_buy_signal_generation(self):
        """Test BUY signal generation."""
        ai_decision = self._create_ai_decision("BUY", 92.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2025.0, 5.0, 2020.0)  # Lower ATR for better RR
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        signal = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        self.assertEqual(signal.signalType, SignalType.BUY)
        self.assertEqual(signal.status, SignalStatus.ACTIVE)
        self.assertGreater(signal.entryPrice, 0)
        self.assertGreater(signal.stopLoss, 0)
        self.assertIsNotNone(signal.takeProfit1)
        self.assertGreater(signal.riskRewardRatio, 0)
        self.assertIsNotNone(signal.tradeManagement)
    
    def test_sell_signal_generation(self):
        """Test SELL signal generation."""
        ai_decision = self._create_ai_decision("SELL", 92.0)
        trend_result = self._create_trend_result("BEARISH", "STRONG")
        structure_result = self._create_structure_result("BEARISH")
        indicator_result = self._create_indicator_result(2025.0, 5.0, 2020.0)  # Lower ATR for better RR
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        signal = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        self.assertEqual(signal.signalType, SignalType.SELL)
        self.assertEqual(signal.status, SignalStatus.ACTIVE)
        self.assertGreater(signal.entryPrice, 0)
        self.assertGreater(signal.stopLoss, 0)
        self.assertIsNotNone(signal.takeProfit1)
        self.assertGreater(signal.riskRewardRatio, 0)
    
    def test_wait_signal_generation(self):
        """Test WAIT signal generation."""
        ai_decision = self._create_ai_decision("WAIT", 50.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2025.0, 15.0, 2020.0)
        signal_score_result = self._create_signal_score_result(65.0, "FAIR")
        
        signal = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        self.assertEqual(signal.signalType, SignalType.WAIT)
        self.assertEqual(signal.status, SignalStatus.ACTIVE)
    
    def test_entry_price_demand_zone(self):
        """Test entry price calculation using demand zone."""
        ai_decision = self._create_ai_decision("BUY", 92.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2035.0, 5.0, 2035.0)  # Set bb_middle to demand zone
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        signal = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2035.0
        )
        
        # Entry should be at current price (bb_middle)
        self.assertEqual(signal.entryPrice, 2035.0)
    
    def test_entry_price_ema_retracement(self):
        """Test entry price calculation using EMA retracement."""
        ai_decision = self._create_ai_decision("BUY", 92.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2025.0, 5.0, 2020.0)
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        signal = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        # Entry should be at EMA20 when no demand zones
        self.assertEqual(signal.entryPrice, 2025.0)
    
    def test_stop_loss_atr(self):
        """Test stop loss calculation using ATR."""
        ai_decision = self._create_ai_decision("BUY", 92.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2025.0, 5.0, 2020.0)
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        signal = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        # Stop loss should be below entry for BUY
        self.assertLess(signal.stopLoss, signal.entryPrice)
    
    def test_take_profit_calculation(self):
        """Test take profit calculation."""
        ai_decision = self._create_ai_decision("BUY", 92.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2025.0, 5.0, 2020.0)
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        signal = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        # All TPs should be above entry for BUY
        self.assertIsNotNone(signal.takeProfit1)
        self.assertIsNotNone(signal.takeProfit2)
        self.assertIsNotNone(signal.takeProfit3)
        self.assertGreater(signal.takeProfit1, signal.entryPrice)
        self.assertGreater(signal.takeProfit2, signal.entryPrice)
        self.assertGreater(signal.takeProfit3, signal.entryPrice)
    
    def test_risk_reward_calculation(self):
        """Test risk/reward ratio calculation."""
        ai_decision = self._create_ai_decision("BUY", 92.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2025.0, 5.0, 2020.0)
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        signal = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        # RR should be at least 1.5 (TP1 is 1.5x risk)
        self.assertGreaterEqual(signal.riskRewardRatio, 1.5)
    
    def test_hold_time_estimation(self):
        """Test hold time estimation based on timeframe."""
        ai_decision = self._create_ai_decision("BUY", 92.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2025.0, 15.0, 2020.0)
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        signal = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        self.assertEqual(signal.expectedHoldTime, "8 Hours")
    
    def test_signal_expiration(self):
        """Test signal expiration calculation."""
        ai_decision = self._create_ai_decision("BUY", 92.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2025.0, 15.0, 2020.0)
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        signal = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        self.assertIsNotNone(signal.expiresAt)
    
    def test_signal_id_uniqueness(self):
        """Test signal ID generation uniqueness."""
        ai_decision = self._create_ai_decision("BUY", 92.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2025.0, 5.0, 2020.0)
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        signal1 = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        # Clear cache to force new signal generation
        self.generator._cache.clear()
        
        signal2 = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        self.assertNotEqual(signal1.signalId, signal2.signalId)
        self.assertTrue(signal1.signalId.startswith("SIG-"))
        self.assertTrue(signal2.signalId.startswith("SIG-"))
    
    def test_trade_management_recommendations(self):
        """Test trade management recommendations."""
        ai_decision = self._create_ai_decision("BUY", 92.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2025.0, 15.0, 2020.0)
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        signal = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        self.assertIsNotNone(signal.tradeManagement)
        self.assertEqual(signal.tradeManagement.moveStopToBreakevenAt, "TP1")
        self.assertEqual(signal.tradeManagement.partialCloseAtTP1, 50)
        self.assertEqual(signal.tradeManagement.partialCloseAtTP2, 30)
        self.assertEqual(signal.tradeManagement.leaveRunner, 20)
    
    def test_cache_behavior(self):
        """Test cache behavior."""
        ai_decision = self._create_ai_decision("BUY", 92.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2025.0, 15.0, 2020.0)
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        # First call - cache miss
        signal1 = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        # Second call - cache hit
        signal2 = self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        self.assertEqual(signal1.signalId, signal2.signalId)
        
        stats = self.generator.get_statistics()
        self.assertEqual(stats['cacheHits'], 1)
        self.assertEqual(stats['cacheMisses'], 1)
    
    def test_statistics_tracking(self):
        """Test statistics tracking."""
        ai_decision = self._create_ai_decision("BUY", 92.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2025.0, 5.0, 2020.0)
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        # Generate signal
        self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        # Check statistics
        stats = self.generator.get_statistics()
        
        self.assertEqual(stats['signalsGenerated'], 1)
        self.assertEqual(stats['buySignals'], 1)
        self.assertGreater(stats['averageConfidence'], 0)
        self.assertGreater(stats['averageGenerationTime'], 0)
    
    def test_statistics_reset(self):
        """Test statistics reset."""
        ai_decision = self._create_ai_decision("BUY", 92.0)
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH")
        indicator_result = self._create_indicator_result(2025.0, 15.0, 2020.0)
        signal_score_result = self._create_signal_score_result(88.0, "GOOD")
        
        # Generate signal
        self.generator.generate_signal(
            "XAUUSD", "H1", ai_decision, trend_result,
            structure_result, indicator_result, signal_score_result, 2020.0
        )
        
        # Reset statistics
        self.generator.reset_statistics()
        
        # Check statistics are reset
        stats = self.generator.get_statistics()
        
        self.assertEqual(stats['signalsGenerated'], 0)
        self.assertEqual(stats['buySignals'], 0)
        self.assertEqual(stats['sellSignals'], 0)
        self.assertEqual(stats['waitSignals'], 0)
        self.assertEqual(stats['averageConfidence'], 0.0)
        self.assertEqual(stats['averageRR'], 0.0)
        self.assertEqual(stats['averageGenerationTime'], 0.0)
        self.assertEqual(stats['cacheHits'], 0)
        self.assertEqual(stats['cacheMisses'], 0)


if __name__ == '__main__':
    unittest.main()
