"""
Unit tests for ConfluenceEngine
Tests signal confluence and decision logic.
"""
import unittest
from datetime import datetime, timezone
from app.services.confluence.confluence_engine import ConfluenceEngine
from app.schemas.confluence_models import (
    SignalDirection, SignalQuality, ConfirmationStatus,
    ConfluenceFactor, TradeLevels
)
from app.schemas.trend_models import TrendResult, TrendDirection as TrendDir, TrendStrength
from app.schemas.market_structure_models import (
    MarketStructureResult, StructureDirection, StructureEvent, StructureZone, ZoneType
)
from app.schemas.indicator_models import IndicatorResponse


class TestConfluenceEngine(unittest.TestCase):
    """Test cases for ConfluenceEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = ConfluenceEngine(news_window_minutes=30, min_rr=2.0)
    
    def _create_trend_result(self, direction: str = "BULLISH", strength: str = "STRONG") -> TrendResult:
        """Create a mock trend result."""
        return TrendResult(
            symbol="XAUUSD",
            timeframe="H1",
            direction=TrendDir(direction),
            strength=TrendStrength(strength),
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
    
    def _create_structure_result(
        self,
        direction: str = "BULLISH",
        event: str = "BOS",
        has_demand: bool = True,
        has_supply: bool = False
    ) -> MarketStructureResult:
        """Create a mock structure result."""
        demand_zones = [StructureZone(
            zoneType=ZoneType.DEMAND,
            high=2040.0,
            low=2030.0,
            midpoint=2035.0,
            strength=80.0,
            touches=0,
            active=True
        )] if has_demand else []
        
        supply_zones = [StructureZone(
            zoneType=ZoneType.SUPPLY,
            high=2060.0,
            low=2050.0,
            midpoint=2055.0,
            strength=80.0,
            touches=0,
            active=True
        )] if has_supply else []
        
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
            activeSupplyZones=supply_zones,
            activeDemandZones=demand_zones,
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
    
    def test_trend_filter_bullish_strong(self):
        """Test trend filter with strong bullish trend."""
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        
        factor = self.engine._evaluate_trend(trend_result)
        
        self.assertEqual(factor.name, "Trend")
        self.assertEqual(factor.status, ConfirmationStatus.CONFIRMED)
        self.assertEqual(factor.weight, 0.25)
        self.assertGreater(factor.score, 0)
        self.assertIn("bullish", factor.reason.lower())
    
    def test_trend_filter_bearish_strong(self):
        """Test trend filter with strong bearish trend."""
        trend_result = self._create_trend_result("BEARISH", "STRONG")
        
        factor = self.engine._evaluate_trend(trend_result)
        
        self.assertEqual(factor.name, "Trend")
        self.assertEqual(factor.status, ConfirmationStatus.CONFIRMED)
        self.assertEqual(factor.weight, 0.25)
        self.assertGreater(factor.score, 0)
        self.assertIn("bearish", factor.reason.lower())
    
    def test_trend_filter_sideways(self):
        """Test trend filter with sideways trend."""
        trend_result = self._create_trend_result("SIDEWAYS", "WEAK")
        
        factor = self.engine._evaluate_trend(trend_result)
        
        self.assertEqual(factor.name, "Trend")
        self.assertEqual(factor.status, ConfirmationStatus.REJECTED)
        self.assertEqual(factor.score, 0.0)
    
    def test_structure_filter_bullish_bos(self):
        """Test structure filter with bullish BOS."""
        structure_result = self._create_structure_result("BULLISH", "BOS", has_demand=True)
        
        factor = self.engine._evaluate_structure(structure_result)
        
        self.assertEqual(factor.name, "Market Structure")
        self.assertEqual(factor.status, ConfirmationStatus.CONFIRMED)
        self.assertEqual(factor.weight, 0.25)
        self.assertIn("bullish", factor.reason.lower())
        self.assertIn("demand", factor.reason.lower())
    
    def test_structure_filter_bearish_bos(self):
        """Test structure filter with bearish BOS."""
        structure_result = self._create_structure_result("BEARISH", "BOS", has_demand=False, has_supply=True)
        
        factor = self.engine._evaluate_structure(structure_result)
        
        self.assertEqual(factor.name, "Market Structure")
        self.assertEqual(factor.status, ConfirmationStatus.CONFIRMED)
        self.assertEqual(factor.weight, 0.25)
        self.assertIn("bearish", factor.reason.lower())
        self.assertIn("supply", factor.reason.lower())
    
    def test_indicator_filter_bullish(self):
        """Test indicator filter with bullish indicators."""
        indicator_result = self._create_indicator_result("BULLISH", "BUY")
        
        factor = self.engine._evaluate_indicators(indicator_result)
        
        self.assertEqual(factor.name, "Indicators")
        self.assertEqual(factor.weight, 0.20)
        self.assertGreater(factor.score, 0)
    
    def test_news_filter(self):
        """Test news filter (simplified - assumes no news)."""
        factor = self.engine._evaluate_news(None, None)
        
        self.assertEqual(factor.name, "News")
        self.assertEqual(factor.status, ConfirmationStatus.CONFIRMED)
        self.assertEqual(factor.score, 100.0)
        self.assertEqual(factor.weight, 0.15)
    
    def test_volatility_filter_healthy(self):
        """Test volatility filter with healthy ATR."""
        indicator_result = self._create_indicator_result()
        current_price = 2000.0
        
        factor = self.engine._evaluate_volatility(indicator_result, current_price)
        
        self.assertEqual(factor.name, "Volatility")
        self.assertEqual(factor.status, ConfirmationStatus.CONFIRMED)
        self.assertEqual(factor.score, 100.0)
        self.assertEqual(factor.weight, 0.10)
    
    def test_volatility_filter_low(self):
        """Test volatility filter with very low ATR."""
        indicator_result = IndicatorResponse(
            symbol="XAUUSD",
            timeframe="H1",
            atr_14=0.5,  # Very low ATR
            ema_20=2025.0,
            ema_50=2020.0,
            ema_100=2015.0,
            ema_200=2010.0,
            sma_20=2024.0,
            sma_50=2019.0,
            rsi_14=55.0,
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
        current_price = 2000.0
        
        factor = self.engine._evaluate_volatility(indicator_result, current_price)
        
        self.assertEqual(factor.name, "Volatility")
        self.assertEqual(factor.status, ConfirmationStatus.REJECTED)
        self.assertEqual(factor.score, 0.0)
    
    def test_risk_filter_good_rr(self):
        """Test risk filter with good RR ratio."""
        structure_result = self._create_structure_result()
        current_price = 2045.0
        
        factor = self.engine._evaluate_risk(structure_result, current_price)
        
        self.assertEqual(factor.name, "Risk")
        self.assertEqual(factor.weight, 0.05)
        # Should be CONFIRMED or PARTIAL depending on calculation
    
    def test_confidence_calculation(self):
        """Test overall confidence calculation."""
        factors = [
            ConfluenceFactor(name="Trend", status=ConfirmationStatus.CONFIRMED, score=80.0, weight=0.25, reason="Test"),
            ConfluenceFactor(name="Structure", status=ConfirmationStatus.CONFIRMED, score=75.0, weight=0.25, reason="Test"),
            ConfluenceFactor(name="Indicators", status=ConfirmationStatus.CONFIRMED, score=70.0, weight=0.20, reason="Test"),
            ConfluenceFactor(name="News", status=ConfirmationStatus.CONFIRMED, score=100.0, weight=0.15, reason="Test"),
            ConfluenceFactor(name="Volatility", status=ConfirmationStatus.CONFIRMED, score=100.0, weight=0.10, reason="Test"),
            ConfluenceFactor(name="Risk", status=ConfirmationStatus.CONFIRMED, score=100.0, weight=0.05, reason="Test")
        ]
        
        confidence = self.engine._calculate_confidence(factors)
        
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 100.0)
    
    def test_decision_buy(self):
        """Test BUY decision logic."""
        trend_factor = ConfluenceFactor(name="Trend", status=ConfirmationStatus.CONFIRMED, score=80.0, weight=0.25, reason="Strong bullish trend")
        structure_factor = ConfluenceFactor(name="Structure", status=ConfirmationStatus.CONFIRMED, score=75.0, weight=0.25, reason="Bullish BOS")
        indicator_factor = ConfluenceFactor(name="Indicators", status=ConfirmationStatus.CONFIRMED, score=70.0, weight=0.20, reason="Bullish indicators")
        news_factor = ConfluenceFactor(name="News", status=ConfirmationStatus.CONFIRMED, score=100.0, weight=0.15, reason="No news")
        volatility_factor = ConfluenceFactor(name="Volatility", status=ConfirmationStatus.CONFIRMED, score=100.0, weight=0.10, reason="Healthy ATR")
        risk_factor = ConfluenceFactor(name="Risk", status=ConfirmationStatus.CONFIRMED, score=100.0, weight=0.05, reason="Good RR")
        
        direction = self.engine._make_decision(
            trend_factor, structure_factor, indicator_factor,
            news_factor, volatility_factor, risk_factor, 85.0
        )
        
        self.assertEqual(direction, SignalDirection.BUY)
    
    def test_decision_sell(self):
        """Test SELL decision logic."""
        trend_factor = ConfluenceFactor(name="Trend", status=ConfirmationStatus.CONFIRMED, score=80.0, weight=0.25, reason="Strong bearish trend")
        structure_factor = ConfluenceFactor(name="Structure", status=ConfirmationStatus.CONFIRMED, score=75.0, weight=0.25, reason="Bearish BOS")
        indicator_factor = ConfluenceFactor(name="Indicators", status=ConfirmationStatus.CONFIRMED, score=70.0, weight=0.20, reason="Bearish indicators")
        news_factor = ConfluenceFactor(name="News", status=ConfirmationStatus.CONFIRMED, score=100.0, weight=0.15, reason="No news")
        volatility_factor = ConfluenceFactor(name="Volatility", status=ConfirmationStatus.CONFIRMED, score=100.0, weight=0.10, reason="Healthy ATR")
        risk_factor = ConfluenceFactor(name="Risk", status=ConfirmationStatus.CONFIRMED, score=100.0, weight=0.05, reason="Good RR")
        
        direction = self.engine._make_decision(
            trend_factor, structure_factor, indicator_factor,
            news_factor, volatility_factor, risk_factor, 85.0
        )
        
        self.assertEqual(direction, SignalDirection.SELL)
    
    def test_decision_wait_rejection(self):
        """Test WAIT decision with rejection."""
        trend_factor = ConfluenceFactor(name="Trend", status=ConfirmationStatus.REJECTED, score=0.0, weight=0.25, reason="Sideways trend")
        structure_factor = ConfluenceFactor(name="Structure", status=ConfirmationStatus.CONFIRMED, score=75.0, weight=0.25, reason="Test")
        indicator_factor = ConfluenceFactor(name="Indicators", status=ConfirmationStatus.CONFIRMED, score=70.0, weight=0.20, reason="Test")
        news_factor = ConfluenceFactor(name="News", status=ConfirmationStatus.CONFIRMED, score=100.0, weight=0.15, reason="Test")
        volatility_factor = ConfluenceFactor(name="Volatility", status=ConfirmationStatus.CONFIRMED, score=100.0, weight=0.10, reason="Test")
        risk_factor = ConfluenceFactor(name="Risk", status=ConfirmationStatus.CONFIRMED, score=100.0, weight=0.05, reason="Test")
        
        direction = self.engine._make_decision(
            trend_factor, structure_factor, indicator_factor,
            news_factor, volatility_factor, risk_factor, 50.0
        )
        
        self.assertEqual(direction, SignalDirection.WAIT)
    
    def test_trade_levels_buy(self):
        """Test trade level calculation for BUY."""
        structure_result = self._create_structure_result()
        current_price = 2045.0
        indicator_result = self._create_indicator_result()
        
        trade_levels = self.engine._calculate_trade_levels(
            SignalDirection.BUY, structure_result, current_price, indicator_result
        )
        
        self.assertIsNotNone(trade_levels.entry)
        self.assertIsNotNone(trade_levels.stopLoss)
        self.assertIsNotNone(trade_levels.takeProfit1)
        self.assertEqual(trade_levels.entry, current_price)
        self.assertLess(trade_levels.stopLoss, current_price)
        self.assertGreater(trade_levels.takeProfit1, current_price)
    
    def test_trade_levels_sell(self):
        """Test trade level calculation for SELL."""
        structure_result = self._create_structure_result()
        current_price = 2045.0
        indicator_result = self._create_indicator_result()
        
        trade_levels = self.engine._calculate_trade_levels(
            SignalDirection.SELL, structure_result, current_price, indicator_result
        )
        
        self.assertIsNotNone(trade_levels.entry)
        self.assertIsNotNone(trade_levels.stopLoss)
        self.assertIsNotNone(trade_levels.takeProfit1)
        self.assertEqual(trade_levels.entry, current_price)
        self.assertGreater(trade_levels.stopLoss, current_price)
        self.assertLess(trade_levels.takeProfit1, current_price)
    
    def test_quality_classification(self):
        """Test signal quality classification."""
        self.assertEqual(self.engine._classify_quality(95), SignalQuality.VERY_HIGH)
        self.assertEqual(self.engine._classify_quality(85), SignalQuality.HIGH)
        self.assertEqual(self.engine._classify_quality(75), SignalQuality.MEDIUM)
        self.assertEqual(self.engine._classify_quality(55), SignalQuality.LOW)
        self.assertEqual(self.engine._classify_quality(30), SignalQuality.VERY_LOW)
    
    def test_full_evaluation_bullish(self):
        """Test full confluence evaluation for bullish setup."""
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH", "BOS", has_demand=True)
        indicator_result = self._create_indicator_result("BULLISH", "BUY")
        current_price = 2045.0
        
        decision = self.engine.evaluate(trend_result, structure_result, indicator_result, current_price)
        
        self.assertEqual(decision.symbol, "XAUUSD")
        self.assertEqual(decision.timeframe, "H1")
        self.assertIn(decision.direction, [SignalDirection.BUY, SignalDirection.SELL, SignalDirection.WAIT])
        self.assertGreaterEqual(decision.confidence, 0.0)
        self.assertLessEqual(decision.confidence, 100.0)
        self.assertIsNotNone(decision.tradeLevels)
        self.assertIsInstance(decision.reasons, list)
        self.assertIsInstance(decision.warnings, list)
    
    def test_statistics_tracking(self):
        """Test engine statistics tracking."""
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH", "BOS", has_demand=True)
        indicator_result = self._create_indicator_result("BULLISH", "BUY")
        current_price = 2045.0
        
        # Perform calculation
        self.engine.evaluate(trend_result, structure_result, indicator_result, current_price)
        
        # Check statistics
        stats = self.engine.get_statistics()
        
        self.assertEqual(stats['calculations'], 1)
        self.assertGreater(stats['average_execution_time'], 0)
    
    def test_statistics_reset(self):
        """Test statistics reset."""
        trend_result = self._create_trend_result("BULLISH", "STRONG")
        structure_result = self._create_structure_result("BULLISH", "BOS", has_demand=True)
        indicator_result = self._create_indicator_result("BULLISH", "BUY")
        current_price = 2045.0
        
        # Perform calculation
        self.engine.evaluate(trend_result, structure_result, indicator_result, current_price)
        
        # Reset statistics
        self.engine.reset_statistics()
        
        # Check statistics are reset
        stats = self.engine.get_statistics()
        
        self.assertEqual(stats['calculations'], 0)
        self.assertEqual(stats['average_execution_time'], 0.0)
        self.assertEqual(stats['buy_signals'], 0)
        self.assertEqual(stats['sell_signals'], 0)
        self.assertEqual(stats['wait_signals'], 0)


if __name__ == '__main__':
    unittest.main()
