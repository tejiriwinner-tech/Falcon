"""
Unit tests for Risk Management Engine
Tests institutional-grade risk evaluation.
"""
import unittest
from datetime import datetime, timezone
from app.services.risk.risk_management_engine import RiskManagementEngine
from app.services.risk.risk_repository import RiskRepository
from app.schemas.risk_models import RiskDecision, RiskAssessment, RiskStatistics
from app.schemas.signal_models import TradeSetup, SignalType, SignalStatus, TradeManagement
from app.schemas.signal_settings import SignalSettings
from app.schemas.decision_models import DecisionType, AIDecisionResult
from app.schemas.trend_models import TrendResult, TrendDirection, TrendStrength
from app.schemas.confluence_models import MultiTimeframeConfluenceResult


class TestRiskManagementEngine(unittest.TestCase):
    """Unit tests for RiskManagementEngine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.settings = SignalSettings()
        self.engine = RiskManagementEngine(self.settings)
    
    def _create_trade_setup(
        self,
        signal_type: str = "BUY",
        entry_price: float = 2020.0,
        stop_loss: float = 2010.0,
        rr: float = 3.0,
        confidence: float = 90.0
    ) -> TradeSetup:
        """Helper to create a trade setup."""
        return TradeSetup(
            signalId="SIG-20260802-000001",
            symbol="XAUUSD",
            timeframe="H1",
            signalType=SignalType(signal_type),
            entryPrice=entry_price,
            stopLoss=stop_loss,
            takeProfit1=2030.0,
            takeProfit2=2040.0,
            takeProfit3=2050.0,
            riskRewardRatio=rr,
            confidence=confidence,
            quality="EXCELLENT",
            expectedHoldTime="8 Hours",
            status=SignalStatus.ACTIVE,
            decision="BUY",
            reasoning=["Test"],
            warnings=[],
            tradeManagement=TradeManagement(
                moveStopToBreakevenAt="TP1",
                partialCloseAtTP1=50,
                partialCloseAtTP2=30,
                leaveRunner=20
            ),
            generatedAt=datetime.now(timezone.utc),
            expiresAt=datetime.now(timezone.utc)
        )
    
    def _create_ai_decision(
        self,
        decision: str = "BUY",
        confidence: float = 92.0,
        signal_score: float = 88.0
    ) -> AIDecisionResult:
        """Helper to create an AI decision."""
        return AIDecisionResult(
            symbol="XAUUSD",
            timeframe="H1",
            decision=DecisionType(decision),
            confidence=confidence,
            signalScore=signal_score,
            trendDirection="BULLISH",
            trendStrength="STRONG",
            structureBias="BULLISH",
            liquidityBias="BULLISH",
            confluenceScore=75.0,
            riskRating="LOW",
            reasoning=["Test"],
            warnings=[]
        )
    
    def _create_trend_result(self, direction: str = "BULLISH") -> TrendResult:
        """Helper to create a trend result."""
        return TrendResult(
            symbol="XAUUSD",
            timeframe="H1",
            direction=TrendDirection(direction),
            strength=TrendStrength.STRONG,
            confidence=85.0,
            ema_alignment=80.0,
            price_above_ema20=True,
            price_above_ema50=True,
            price_above_ema200=True,
            higher_highs=5,
            higher_lows=4,
            lower_highs=1,
            lower_lows=2,
            analysis="Test"
        )
    
    def _create_confluence_result(self, score: float = 75.0) -> MultiTimeframeConfluenceResult:
        """Helper to create a confluence result."""
        return MultiTimeframeConfluenceResult(
            symbol="XAUUSD",
            overallConfluenceScore=score,
            timeframeAnalysis=[],
            recommendation="BUY",
            recommendationReason="Strong bullish confluence",
            confidence=80.0
        )
    
    def test_rr_validation_above_minimum(self):
        """Test RR validation when above minimum."""
        trade_setup = self._create_trade_setup(rr=2.5)
        result = self.engine._validate_risk_reward(trade_setup.riskRewardRatio)
        self.assertEqual(result, (True, False))
    
    def test_rr_validation_below_minimum(self):
        """Test RR validation when below minimum."""
        trade_setup = self._create_trade_setup(rr=1.0)
        result = self.engine._validate_risk_reward(trade_setup.riskRewardRatio)
        self.assertEqual(result, (False, False))
    
    def test_rr_validation_below_preferred(self):
        """Test RR validation when below preferred but above minimum."""
        trade_setup = self._create_trade_setup(rr=1.8)
        result = self.engine._validate_risk_reward(trade_setup.riskRewardRatio)
        self.assertEqual(result, (True, True))
    
    def test_stop_loss_distance_valid(self):
        """Test stop loss distance validation when valid."""
        trade_setup = self._create_trade_setup(entry_price=1.2020, stop_loss=1.2010)
        result = self.engine._validate_stop_loss_distance(trade_setup.entryPrice, trade_setup.stopLoss)
        self.assertTrue(result[0])
        self.assertAlmostEqual(result[1], 10.0, places=2)
    
    def test_stop_loss_distance_invalid(self):
        """Test stop loss distance validation when invalid."""
        trade_setup = self._create_trade_setup(entry_price=1.2020, stop_loss=1.1820)
        result = self.engine._validate_stop_loss_distance(trade_setup.entryPrice, trade_setup.stopLoss)
        self.assertFalse(result[0])
        self.assertAlmostEqual(result[1], 200.0, places=2)
    
    def test_confidence_validation_valid(self):
        """Test confidence validation when valid."""
        result = self.engine._validate_confidence(80.0)
        self.assertTrue(result)
    
    def test_confidence_validation_invalid(self):
        """Test confidence validation when invalid."""
        result = self.engine._validate_confidence(60.0)
        self.assertFalse(result)
    
    def test_ai_confidence_validation_valid(self):
        """Test AI confidence validation when valid."""
        result = self.engine._validate_ai_confidence(80.0)
        self.assertTrue(result)
    
    def test_ai_confidence_validation_invalid(self):
        """Test AI confidence validation when invalid."""
        result = self.engine._validate_ai_confidence(70.0)
        self.assertFalse(result)
    
    def test_signal_score_validation_valid(self):
        """Test signal score validation when valid."""
        result = self.engine._validate_signal_score(80.0)
        self.assertTrue(result)
    
    def test_signal_score_validation_invalid(self):
        """Test signal score validation when invalid."""
        result = self.engine._validate_signal_score(60.0)
        self.assertFalse(result)
    
    def test_confluence_validation_valid(self):
        """Test confluence validation when valid."""
        result = self.engine._validate_confluence(70.0)
        self.assertTrue(result)
    
    def test_confluence_validation_invalid(self):
        """Test confluence validation when invalid."""
        result = self.engine._validate_confluence(50.0)
        self.assertFalse(result)
    
    def test_trend_validation_counter_trend_rejected(self):
        """Test trend validation rejects counter-trend when not allowed."""
        self.settings.allow_counter_trend_trades = False
        result = self.engine._validate_trend("BUY", "BEARISH")
        self.assertFalse(result)
    
    def test_trend_validation_counter_trend_allowed(self):
        """Test trend validation allows counter-trend when allowed."""
        self.settings.allow_counter_trend_trades = True
        result = self.engine._validate_trend("BUY", "BEARISH")
        self.assertTrue(result)
    
    def test_trend_validation_aligned(self):
        """Test trend validation accepts aligned trend."""
        result = self.engine._validate_trend("BUY", "BULLISH")
        self.assertTrue(result)
    
    def test_position_risk_calculation(self):
        """Test position risk calculation."""
        risk_percent = self.engine._calculate_position_risk(2020.0, 2010.0, 100000.0, 1.0)
        self.assertEqual(risk_percent, 0.01)  # 10 pips / 100000 * 100
    
    def test_daily_risk_validation_valid(self):
        """Test daily risk validation when valid."""
        self.engine._daily_risk_accumulated = 1.0
        result = self.engine._validate_daily_risk(0.5)
        self.assertTrue(result)
    
    def test_daily_risk_validation_invalid(self):
        """Test daily risk validation when invalid."""
        self.engine._daily_risk_accumulated = 1.8
        result = self.engine._validate_daily_risk(0.5)
        self.assertFalse(result)
    
    def test_portfolio_exposure_calculation(self):
        """Test portfolio exposure calculation."""
        self.engine._daily_risk_accumulated = 1.0
        exposure = self.engine._calculate_portfolio_exposure(0.5)
        self.assertEqual(exposure, 1.5)
    
    def test_portfolio_exposure_validation_valid(self):
        """Test portfolio exposure validation when valid."""
        self.engine._daily_risk_accumulated = 2.0
        result = self.engine._validate_portfolio_exposure(2.5)
        self.assertTrue(result)
    
    def test_portfolio_exposure_validation_invalid(self):
        """Test portfolio exposure validation when invalid."""
        self.engine._daily_risk_accumulated = 4.0
        exposure = self.engine._calculate_portfolio_exposure(2.0)
        result = self.engine._validate_portfolio_exposure(exposure)
        self.assertFalse(result)  # 6.0 > 5.0
    
    def test_correlation_level_low(self):
        """Test correlation level determination for low correlation."""
        self.engine._open_positions = []
        level = self.engine._determine_correlation_level("XAUUSD")
        self.assertEqual(level, "LOW")
    
    def test_correlation_level_medium(self):
        """Test correlation level determination for medium correlation."""
        self.engine._open_positions = ["EURUSD"]
        level = self.engine._determine_correlation_level("GBPUSD")
        self.assertEqual(level, "MEDIUM")
    
    def test_correlation_level_high(self):
        """Test correlation level determination for high correlation."""
        self.engine._open_positions = ["EURUSD", "GBPUSD", "AUDUSD"]
        level = self.engine._determine_correlation_level("NZDUSD")
        self.assertEqual(level, "HIGH")
    
    def test_correlation_validation_valid(self):
        """Test correlation validation when valid."""
        self.engine._open_positions = []
        result = self.engine._validate_correlation("XAUUSD")
        self.assertTrue(result)
    
    def test_correlation_validation_invalid(self):
        """Test correlation validation when invalid."""
        self.engine._open_positions = ["EURUSD", "GBPUSD", "AUDUSD"]
        result = self.engine._validate_correlation("NZDUSD")
        self.assertFalse(result)
    
    def test_configuration_override_allow_counter_trend(self):
        """Test configuration override for counter-trend trades."""
        custom_settings = SignalSettings(allow_counter_trend_trades=True)
        custom_engine = RiskManagementEngine(custom_settings)
        
        trade_setup = self._create_trade_setup(rr=3.0, confidence=90.0)
        ai_decision = self._create_ai_decision(confidence=92.0, signal_score=88.0)
        trend_result = self._create_trend_result("BEARISH")  # Counter-trend
        confluence_result = self._create_confluence_result(75.0)
        
        assessment = custom_engine.evaluate(
            trade_setup, ai_decision, trend_result, confluence_result,
            account_balance=100000.0, position_size=1.0
        )
        
        # Should be approved since counter-trend is allowed
        self.assertEqual(assessment.decision, RiskDecision.APPROVED)
    
    def test_configuration_override_minimum_rr(self):
        """Test configuration override for minimum RR."""
        custom_settings = SignalSettings(minimum_rr=2.0)
        custom_engine = RiskManagementEngine(custom_settings)
        
        trade_setup = self._create_trade_setup(rr=1.8, confidence=90.0)
        ai_decision = self._create_ai_decision(confidence=92.0, signal_score=88.0)
        trend_result = self._create_trend_result("BULLISH")
        confluence_result = self._create_confluence_result(75.0)
        
        assessment = custom_engine.evaluate(
            trade_setup, ai_decision, trend_result, confluence_result,
            account_balance=100000.0, position_size=1.0
        )
        
        self.assertEqual(assessment.decision, RiskDecision.REJECTED)
    
    def test_statistics_tracking(self):
        """Test statistics tracking."""
        trade_setup = self._create_trade_setup(rr=3.0, confidence=90.0)
        ai_decision = self._create_ai_decision(confidence=92.0, signal_score=88.0)
        trend_result = self._create_trend_result("BULLISH")
        confluence_result = self._create_confluence_result(75.0)
        
        self.engine.evaluate(
            trade_setup, ai_decision, trend_result, confluence_result,
            account_balance=100000.0, position_size=1.0
        )
        
        stats = self.engine.get_statistics()
        self.assertEqual(stats['totalAssessments'], 1)
        self.assertEqual(stats['approvedCount'], 1)
    
    def test_statistics_reset(self):
        """Test statistics reset."""
        trade_setup = self._create_trade_setup(rr=3.0, confidence=90.0)
        ai_decision = self._create_ai_decision(confidence=92.0, signal_score=88.0)
        trend_result = self._create_trend_result("BULLISH")
        confluence_result = self._create_confluence_result(75.0)
        
        self.engine.evaluate(
            trade_setup, ai_decision, trend_result, confluence_result,
            account_balance=100000.0, position_size=1.0
        )
        
        self.engine.reset_statistics()
        stats = self.engine.get_statistics()
        self.assertEqual(stats['totalAssessments'], 0)
        self.assertEqual(stats['approvedCount'], 0)
    
    def test_performance_requirement(self):
        """Test that risk evaluation completes within 2ms."""
        import time
        
        trade_setup = self._create_trade_setup(rr=3.0, confidence=90.0)
        ai_decision = self._create_ai_decision(confidence=92.0, signal_score=88.0)
        trend_result = self._create_trend_result("BULLISH")
        confluence_result = self._create_confluence_result(75.0)
        
        start_time = time.perf_counter()
        self.engine.evaluate(
            trade_setup, ai_decision, trend_result, confluence_result,
            account_balance=100000.0, position_size=1.0
        )
        end_time = time.perf_counter()
        
        execution_time_ms = (end_time - start_time) * 1000
        self.assertLess(execution_time_ms, 2.0, f"Risk evaluation took {execution_time_ms:.2f}ms, expected < 2ms")


class TestRiskRepository(unittest.TestCase):
    """Unit tests for RiskRepository."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.repository = RiskRepository(":memory:")
    
    def test_save_assessment(self):
        """Test saving a risk assessment."""
        assessment = RiskAssessment(
            signalId="SIG-20260802-000001",
            symbol="XAUUSD",
            timeframe="H1",
            decision=RiskDecision.APPROVED,
            overallRiskScore=10.0,
            riskPercent=1.5,
            rr=3.0,
            dailyExposure=1.5,
            portfolioExposure=3.0,
            correlationLevel="LOW",
            approved=True,
            reasons=["RR acceptable"],
            warnings=[]
        )
        
        result = self.repository.save_assessment(assessment)
        self.assertTrue(result)
    
    def test_get_assessment(self):
        """Test getting a risk assessment by ID."""
        assessment = RiskAssessment(
            signalId="SIG-20260802-000001",
            symbol="XAUUSD",
            timeframe="H1",
            decision=RiskDecision.APPROVED,
            overallRiskScore=10.0,
            riskPercent=1.5,
            rr=3.0,
            dailyExposure=1.5,
            portfolioExposure=3.0,
            correlationLevel="LOW",
            approved=True,
            reasons=["RR acceptable"],
            warnings=[]
        )
        
        self.repository.save_assessment(assessment)
        retrieved = self.repository.get_assessment("SIG-20260802-000001")
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.signalId, "SIG-20260802-000001")
        self.assertEqual(retrieved.decision, RiskDecision.APPROVED)
    
    def test_list_assessments(self):
        """Test listing risk assessments."""
        assessment1 = RiskAssessment(
            signalId="SIG-20260802-000001",
            symbol="XAUUSD",
            timeframe="H1",
            decision=RiskDecision.APPROVED,
            overallRiskScore=10.0,
            riskPercent=1.5,
            rr=3.0,
            dailyExposure=1.5,
            portfolioExposure=3.0,
            correlationLevel="LOW",
            approved=True,
            reasons=["RR acceptable"],
            warnings=[]
        )
        
        assessment2 = RiskAssessment(
            signalId="SIG-20260802-000002",
            symbol="GBPUSD",
            timeframe="H1",
            decision=RiskDecision.REJECTED,
            overallRiskScore=60.0,
            riskPercent=2.0,
            rr=1.0,
            dailyExposure=0.0,
            portfolioExposure=0.0,
            correlationLevel="LOW",
            approved=False,
            reasons=["RR below minimum"],
            warnings=[]
        )
        
        self.repository.save_assessment(assessment1)
        self.repository.save_assessment(assessment2)
        
        assessments = self.repository.list_assessments()
        self.assertEqual(len(assessments), 2)
    
    def test_approved_assessments(self):
        """Test getting approved assessments."""
        assessment1 = RiskAssessment(
            signalId="SIG-20260802-000001",
            symbol="XAUUSD",
            timeframe="H1",
            decision=RiskDecision.APPROVED,
            overallRiskScore=10.0,
            riskPercent=1.5,
            rr=3.0,
            dailyExposure=1.5,
            portfolioExposure=3.0,
            correlationLevel="LOW",
            approved=True,
            reasons=["RR acceptable"],
            warnings=[]
        )
        
        assessment2 = RiskAssessment(
            signalId="SIG-20260802-000002",
            symbol="GBPUSD",
            timeframe="H1",
            decision=RiskDecision.REJECTED,
            overallRiskScore=60.0,
            riskPercent=2.0,
            rr=1.0,
            dailyExposure=0.0,
            portfolioExposure=0.0,
            correlationLevel="LOW",
            approved=False,
            reasons=["RR below minimum"],
            warnings=[]
        )
        
        self.repository.save_assessment(assessment1)
        self.repository.save_assessment(assessment2)
        
        approved = self.repository.approved_assessments()
        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0].signalId, "SIG-20260802-000001")
    
    def test_rejected_assessments(self):
        """Test getting rejected assessments."""
        assessment1 = RiskAssessment(
            signalId="SIG-20260802-000001",
            symbol="XAUUSD",
            timeframe="H1",
            decision=RiskDecision.APPROVED,
            overallRiskScore=10.0,
            riskPercent=1.5,
            rr=3.0,
            dailyExposure=1.5,
            portfolioExposure=3.0,
            correlationLevel="LOW",
            approved=True,
            reasons=["RR acceptable"],
            warnings=[]
        )
        
        assessment2 = RiskAssessment(
            signalId="SIG-20260802-000002",
            symbol="GBPUSD",
            timeframe="H1",
            decision=RiskDecision.REJECTED,
            overallRiskScore=60.0,
            riskPercent=2.0,
            rr=1.0,
            dailyExposure=0.0,
            portfolioExposure=0.0,
            correlationLevel="LOW",
            approved=False,
            reasons=["RR below minimum"],
            warnings=[]
        )
        
        self.repository.save_assessment(assessment1)
        self.repository.save_assessment(assessment2)
        
        rejected = self.repository.rejected_assessments()
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0].signalId, "SIG-20260802-000002")
    
    def test_statistics(self):
        """Test repository statistics."""
        assessment1 = RiskAssessment(
            signalId="SIG-20260802-000001",
            symbol="XAUUSD",
            timeframe="H1",
            decision=RiskDecision.APPROVED,
            overallRiskScore=10.0,
            riskPercent=1.5,
            rr=3.0,
            dailyExposure=1.5,
            portfolioExposure=3.0,
            correlationLevel="LOW",
            approved=True,
            reasons=["RR acceptable"],
            warnings=[]
        )
        
        assessment2 = RiskAssessment(
            signalId="SIG-20260802-000002",
            symbol="GBPUSD",
            timeframe="H1",
            decision=RiskDecision.REJECTED,
            overallRiskScore=60.0,
            riskPercent=2.0,
            rr=1.0,
            dailyExposure=0.0,
            portfolioExposure=0.0,
            correlationLevel="LOW",
            approved=False,
            reasons=["RR below minimum"],
            warnings=[]
        )
        
        self.repository.save_assessment(assessment1)
        self.repository.save_assessment(assessment2)
        
        stats = self.repository.statistics()
        self.assertEqual(stats['totalAssessments'], 2)
        self.assertEqual(stats['approvedCount'], 1)
        self.assertEqual(stats['rejectedCount'], 1)


if __name__ == '__main__':
    unittest.main()
