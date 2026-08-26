"""
Falcon Intelligence Engine
The Decision Engine - Combines all analysis engines into final AI trading intelligence
"""
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from app.services.intelligence.market_analyzer import MarketAnalyzer, MarketAnalyzerResult
from app.services.intelligence.signal_scorer import SignalScorer
from app.services.intelligence.risk_engine import RiskEngine, RiskCalculation
from app.services.intelligence.trend_detector import TrendDetector, TrendDetectorResult
from app.services.intelligence.entry_optimizer import EntryOptimizer, EntryOptimization
from app.services.intelligence.volatility_analyzer import VolatilityAnalyzer, VolatilityAnalysis
from app.services.intelligence.confidence_engine import ConfidenceEngine, ConfidenceAssessment
from app.services.intelligence.confluence_analyzer import ConfluenceAnalyzer, ConfluenceAnalysis
from app.schemas.trend_models import TrendResult
from app.schemas.market_structure_models import MarketStructureResult
from app.schemas.indicator_models import IndicatorResponse
from app.schemas.confluence_models import MultiTimeframeConfluenceResult
from app.schemas.signal_score_models import SignalScoreResult


class IntelligenceDecision:
    """Final intelligence decision result."""
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        decision: str,
        confidence: float,
        signal_score: float,
        risk_score: float,
        confluence_score: float,
        market_state: str,
        trend: str,
        entry_quality: str,
        reasoning: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        risk_reward: float,
        timestamp: datetime
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.decision = decision
        self.confidence = confidence
        self.signal_score = signal_score
        self.risk_score = risk_score
        self.confluence_score = confluence_score
        self.market_state = market_state
        self.trend = trend
        self.entry_quality = entry_quality
        self.reasoning = reasoning
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.risk_reward = risk_reward
        self.timestamp = timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'decision': self.decision,
            'confidence': self.confidence,
            'signalScore': self.signal_score,
            'riskScore': self.risk_score,
            'confluenceScore': self.confluence_score,
            'marketState': self.market_state,
            'trend': self.trend,
            'entryQuality': self.entry_quality,
            'reasoning': self.reasoning,
            'entry': self.entry_price,
            'stop': self.stop_loss,
            'target': self.take_profit,
            'riskReward': self.risk_reward,
            'timestamp': self.timestamp.isoformat()
        }


class IntelligenceEngine:
    """
    Intelligence Engine - Falcon's AI Brain.
    
    Orchestrates all analysis engines:
    - Market Analyzer
    - Signal Scorer
    - Risk Engine
    - Trend Detector
    - Entry Optimizer
    - Volatility Analyzer
    - Confidence Engine
    - Confluence Analyzer
    
    Produces final trading decision: BUY/SELL/WAIT/AVOID
    """
    
    def __init__(self):
        """Initialize the intelligence engine."""
        self.market_analyzer = MarketAnalyzer()
        self.signal_scorer = SignalScorer()
        self.risk_engine = RiskEngine()
        self.trend_detector = TrendDetector()
        self.entry_optimizer = EntryOptimizer()
        self.volatility_analyzer = VolatilityAnalyzer()
        self.confidence_engine = ConfidenceEngine()
        self.confluence_analyzer = ConfluenceAnalyzer()
        
        self._decision_count = 0
    
    def make_decision(
        self,
        symbol: str,
        timeframe: str,
        trend_result: Optional[TrendResult],
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse],
        mt_confluence_result: Optional[MultiTimeframeConfluenceResult],
        current_price: float
    ) -> IntelligenceDecision:
        """
        Make final AI trading decision.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe
            trend_result: Trend analysis
            structure_result: Market structure analysis
            indicator_result: Indicator analysis
            mt_confluence_result: Multi-timeframe confluence
            current_price: Current market price
            
        Returns:
            IntelligenceDecision with complete AI intelligence
        """
        self._decision_count += 1
        
        market_analysis = self.market_analyzer.analyze_market(
            symbol, timeframe, trend_result, structure_result, indicator_result, current_price
        )
        
        signal_score_result = self.signal_scorer.score_signal(
            symbol, timeframe, trend_result, structure_result,
            indicator_result, mt_confluence_result, current_price
        )
        
        trend_detection = self.trend_detector.detect_trends(
            symbol, timeframe, trend_result
        )
        
        volatility_analysis = self.volatility_analyzer.analyze_volatility(
            symbol, timeframe, indicator_result, current_price
        )
        
        confidence_assessment = self.confidence_engine.calculate_confidence(
            symbol, timeframe, trend_result, structure_result,
            indicator_result, mt_confluence_result, signal_score_result
        )
        
        confluence_analysis = self.confluence_analyzer.analyze_confluence(
            symbol, timeframe, trend_result, structure_result,
            indicator_result, mt_confluence_result, current_price
        )
        
        decision, reasoning = self._make_final_decision(
            market_analysis, signal_score_result, confidence_assessment,
            confluence_analysis, volatility_analysis
        )
        
        entry_optimization = None
        risk_calculation = None
        
        if decision in ["BUY", "SELL"]:
            entry_optimization = self.entry_optimizer.optimize_entry(
                symbol, timeframe, decision, current_price,
                structure_result, indicator_result
            )
            
            risk_calculation = self.risk_engine.calculate_risk(
                symbol, timeframe, decision, current_price,
                structure_result, indicator_result
            )
        
        entry_price = risk_calculation.entry_price if risk_calculation else current_price
        stop_loss = risk_calculation.stop_loss if risk_calculation else current_price * 0.99
        take_profit = risk_calculation.take_profit_1 if risk_calculation else current_price * 1.02
        risk_reward = risk_calculation.risk_reward_ratio if risk_calculation else 0.0
        
        risk_score = self._calculate_risk_score(
            risk_calculation, volatility_analysis
        )
        
        return IntelligenceDecision(
            symbol=symbol,
            timeframe=timeframe,
            decision=decision,
            confidence=confidence_assessment.confidence_percentage,
            signal_score=signal_score_result.overallScore,
            risk_score=risk_score,
            confluence_score=confluence_analysis.confluence_score,
            market_state=market_analysis.market_state.value,
            trend=f"{market_analysis.trend_direction} ({market_analysis.trend_strength})",
            entry_quality=entry_optimization.entry_quality.value if entry_optimization else "N/A",
            reasoning=reasoning,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=risk_reward,
            timestamp=datetime.now(timezone.utc)
        )
    
    def _make_final_decision(
        self,
        market_analysis: MarketAnalyzerResult,
        signal_score_result: SignalScoreResult,
        confidence_assessment: ConfidenceAssessment,
        confluence_analysis: ConfluenceAnalysis,
        volatility_analysis: VolatilityAnalysis
    ) -> tuple[str, str]:
        """Make final trading decision."""
        if confidence_assessment.confidence_percentage < 60:
            return "AVOID", "Confidence too low for trading"
        
        if signal_score_result.overallScore < 70:
            return "WAIT", "Signal quality below threshold"
        
        if confluence_analysis.confluence_score < 60:
            return "WAIT", "Insufficient confluence"
        
        if volatility_analysis.volatility_state == "EXTREME":
            return "AVOID", "Extreme volatility detected"
        
        if market_analysis.market_state == "BULLISH":
            if signal_score_result.overallScore >= 90:
                return "BUY", f"Strong bullish setup with {signal_score_result.overallScore:.0f}% signal quality"
            else:
                return "BUY", f"Bullish setup with {signal_score_result.overallScore:.0f}% signal quality"
        
        elif market_analysis.market_state == "BEARISH":
            if signal_score_result.overallScore >= 90:
                return "SELL", f"Strong bearish setup with {signal_score_result.overallScore:.0f}% signal quality"
            else:
                return "SELL", f"Bearish setup with {signal_score_result.overallScore:.0f}% signal quality"
        
        elif market_analysis.market_state == "BREAKOUT":
            if confidence_assessment.confidence_percentage >= 80:
                if market_analysis.trend_direction == "BULLISH":
                    return "BUY", "Bullish breakout confirmed"
                else:
                    return "SELL", "Bearish breakout confirmed"
            else:
                return "WAIT", "Breakout not yet confirmed"
        
        elif market_analysis.market_state == "REVERSAL":
            if confluence_analysis.confluence_score >= 75:
                if market_analysis.momentum in ["STRONG_BULLISH"]:
                    return "BUY", "Potential bullish reversal"
                elif market_analysis.momentum in ["STRONG_BEARISH"]:
                    return "SELL", "Potential bearish reversal"
            return "WAIT", "Reversal pattern forming, awaiting confirmation"
        
        else:
            return "WAIT", f"Market in {market_analysis.market_state} state, no clear setup"
    
    def _calculate_risk_score(
        self,
        risk_calculation: Optional[RiskCalculation],
        volatility_analysis: VolatilityAnalysis
    ) -> float:
        """Calculate overall risk score (0-100, lower is better)."""
        if not risk_calculation:
            return 50.0
        
        risk_factors = []
        
        risk_level_scores = {
            "LOW": 20.0,
            "MEDIUM": 40.0,
            "HIGH": 70.0,
            "EXTREME": 90.0
        }
        risk_factors.append(risk_level_scores.get(risk_calculation.risk_level.value, 50.0))
        
        volatility_scores = {
            "DORMANT": 10.0,
            "LOW": 20.0,
            "NORMAL": 30.0,
            "HIGH": 60.0,
            "EXTREME": 90.0
        }
        risk_factors.append(volatility_scores.get(volatility_analysis.volatility_state.value, 50.0))
        
        if risk_calculation.risk_reward_ratio < 2.0:
            risk_factors.append(60.0)
        else:
            risk_factors.append(20.0)
        
        return sum(risk_factors) / len(risk_factors)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            'decisionCount': self._decision_count,
            'marketAnalyzer': self.market_analyzer.get_statistics(),
            'signalScorer': self.signal_scorer.get_statistics(),
            'riskEngine': self.risk_engine.get_statistics(),
            'trendDetector': self.trend_detector.get_statistics(),
            'entryOptimizer': self.entry_optimizer.get_statistics(),
            'volatilityAnalyzer': self.volatility_analyzer.get_statistics(),
            'confidenceEngine': self.confidence_engine.get_statistics(),
            'confluenceAnalyzer': self.confluence_analyzer.get_statistics()
        }
