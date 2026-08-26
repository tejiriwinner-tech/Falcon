"""
Falcon AI Decision Engine
Evaluates all analytical engines and produces intelligent trading decisions.
"""
import time
from typing import Optional, List
from datetime import datetime, timezone
from app.schemas.decision_models import DecisionType, AIDecisionResult
from app.schemas.trend_models import TrendResult, TrendDirection
from app.schemas.market_structure_models import MarketStructureResult, StructureDirection
from app.schemas.indicator_models import IndicatorResponse
from app.schemas.confluence_models import MultiTimeframeConfluenceResult
from app.schemas.signal_score_models import SignalScoreResult, RiskRating
from app.schemas.signal_settings import SignalSettings


class AIDecisionEngine:
    """
    AI Decision Engine - Falcon's "brain".
    
    Evaluates all analytical engines and produces intelligent trading decisions.
    Behaves like a professional institutional trader - never guesses,
    only recommends trades when enough independent evidence agrees.
    """
    
    def __init__(self, settings: Optional[SignalSettings] = None):
        """Initialize the AI decision engine."""
        # Use provided settings or default
        self.settings = settings if settings else SignalSettings()
        
        # Cache (symbol + timeframe -> result)
        self._cache: dict = {}
        self._cache_ttl = 60  # 60 seconds cache TTL
        
        # Statistics
        self._total_decisions = 0
        self._buy_count = 0
        self._sell_count = 0
        self._wait_count = 0
        self._total_confidence = 0.0
        self._total_execution_time = 0.0
        self._cache_hits = 0
        self._cache_misses = 0
        self._highest_confidence = 0.0
        self._lowest_confidence = 100.0
    
    def make_decision(
        self,
        symbol: str,
        timeframe: str,
        trend_result: Optional[TrendResult] = None,
        structure_result: Optional[MarketStructureResult] = None,
        indicator_result: Optional[IndicatorResponse] = None,
        mt_confluence_result: Optional[MultiTimeframeConfluenceResult] = None,
        signal_score_result: Optional[SignalScoreResult] = None
    ) -> AIDecisionResult:
        """
        Make AI trading decision based on all analytical engines.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe analyzed
            trend_result: Trend analysis result
            structure_result: Market structure result
            indicator_result: Indicator analysis result
            mt_confluence_result: Multi-timeframe confluence result
            signal_score_result: Signal score result
            
        Returns:
            AIDecisionResult with decision, confidence, reasoning, and warnings
        """
        start_time = time.time()
        
        # Create cache key
        cache_key = f"{symbol}_{timeframe}"
        
        # Check cache
        if cache_key in self._cache:
            cached_result, cache_time = self._cache[cache_key]
            if (datetime.now(timezone.utc) - cache_time).total_seconds() < self._cache_ttl:
                self._cache_hits += 1
                return cached_result
        
        self._cache_misses += 1
        
        # Extract data from results
        trend_direction = trend_result.direction.value if trend_result else None
        trend_strength = trend_result.strength.value if trend_result else None
        structure_bias = structure_result.direction.value if structure_result else None
        liquidity_bias = self._determine_liquidity_bias(structure_result)
        confluence_score = mt_confluence_result.overallConfluenceScore if mt_confluence_result else None
        signal_score = signal_score_result.overallScore if signal_score_result else None
        risk_rating = signal_score_result.riskRating.value if signal_score_result else None
        
        # Generate warnings
        warnings = self._generate_warnings(
            trend_result, structure_result, indicator_result,
            mt_confluence_result, signal_score_result
        )
        
        # Determine decision
        decision, confidence, reasoning = self._determine_decision(
            trend_direction, trend_strength, structure_bias, liquidity_bias,
            confluence_score, signal_score, risk_rating, warnings
        )
        
        # Update statistics
        execution_time = (time.time() - start_time) * 1000
        self._total_decisions += 1
        self._total_confidence += confidence
        self._total_execution_time += execution_time
        self._highest_confidence = max(self._highest_confidence, confidence)
        self._lowest_confidence = min(self._lowest_confidence, confidence)
        
        if decision == DecisionType.BUY or decision == DecisionType.STRONG_BUY:
            self._buy_count += 1
        elif decision == DecisionType.SELL or decision == DecisionType.STRONG_SELL:
            self._sell_count += 1
        else:
            self._wait_count += 1
        
        # Create result
        result = AIDecisionResult(
            symbol=symbol,
            timeframe=timeframe,
            decision=decision,
            confidence=confidence,
            signalScore=signal_score,
            trendDirection=trend_direction,
            trendStrength=trend_strength,
            structureBias=structure_bias,
            liquidityBias=liquidity_bias,
            confluenceScore=confluence_score,
            riskRating=risk_rating,
            reasoning=reasoning,
            warnings=warnings
        )
        
        # Update cache
        self._cache[cache_key] = (result, datetime.now(timezone.utc))
        
        return result
    
    def _determine_liquidity_bias(self, structure_result: Optional[MarketStructureResult]) -> Optional[str]:
        """Determine liquidity bias from structure result."""
        if not structure_result:
            return None
        
        if structure_result.liquidityZones:
            return "BULLISH" if structure_result.direction.value == "BULLISH" else "BEARISH"
        return None
    
    def _determine_decision(
        self,
        trend_direction: Optional[str],
        trend_strength: Optional[str],
        structure_bias: Optional[str],
        liquidity_bias: Optional[str],
        confluence_score: Optional[float],
        signal_score: Optional[float],
        risk_rating: Optional[str],
        warnings: List[str]
    ) -> tuple[DecisionType, float, List[str]]:
        """Determine AI decision based on all factors."""
        reasoning = []
        
        # Check for NO_TRADE conditions
        if not trend_direction or trend_direction == "UNKNOWN":
            reasoning.append("Unknown trend direction")
            return DecisionType.NO_TRADE, 0.0, reasoning
        
        if not structure_bias or structure_bias == "NEUTRAL":
            reasoning.append("Unknown market structure")
            return DecisionType.NO_TRADE, 0.0, reasoning
        
        if signal_score is None:
            reasoning.append("Missing signal quality score")
            return DecisionType.NO_TRADE, 0.0, reasoning
        
        # Check for STRONG_BUY
        if (signal_score >= 95 and
            trend_direction == "BULLISH" and
            structure_bias == "BULLISH" and
            liquidity_bias == "BULLISH" and
            confluence_score and confluence_score >= self.settings.minimum_confluence and
            risk_rating == "LOW"):
            reasoning.extend([
                "Bullish trend confirmed",
                "Bullish market structure",
                "Liquidity sweep completed",
                "Strong confluence across timeframes",
                "Signal quality exceeds threshold",
                "Risk acceptable"
            ])
            return DecisionType.STRONG_BUY, 97.0, reasoning
        
        # Check for STRONG_SELL
        if (signal_score >= 95 and
            trend_direction == "BEARISH" and
            structure_bias == "BEARISH" and
            liquidity_bias == "BEARISH" and
            confluence_score and confluence_score >= self.settings.minimum_confluence and
            risk_rating == "LOW"):
            reasoning.extend([
                "Bearish trend confirmed",
                "Bearish market structure",
                "Liquidity sweep completed",
                "Strong confluence across timeframes",
                "Signal quality exceeds threshold",
                "Risk acceptable"
            ])
            return DecisionType.STRONG_SELL, 97.0, reasoning
        
        # Check for BUY
        if (signal_score >= self.settings.minimum_signal_score and
            trend_direction == "BULLISH" and
            structure_bias == "BULLISH" and
            confluence_score and confluence_score >= self.settings.minimum_confluence and
            risk_rating in ["LOW", "MEDIUM"]):
            reasoning.extend([
                "Bullish trend confirmed",
                "Bullish market structure",
                "Adequate confluence",
                "Signal quality above threshold",
                "Risk acceptable"
            ])
            return DecisionType.BUY, 92.0, reasoning
        
        # Check for SELL
        if (signal_score >= self.settings.minimum_signal_score and
            trend_direction == "BEARISH" and
            structure_bias == "BEARISH" and
            confluence_score and confluence_score >= self.settings.minimum_confluence and
            risk_rating in ["LOW", "MEDIUM"]):
            reasoning.extend([
                "Bearish trend confirmed",
                "Bearish market structure",
                "Adequate confluence",
                "Signal quality above threshold",
                "Risk acceptable"
            ])
            return DecisionType.SELL, 92.0, reasoning
        
        # Check for WAIT conditions
        wait_reasons = []
        
        if trend_direction != structure_bias:
            wait_reasons.append(f"Trend ({trend_direction}) conflicts with structure ({structure_bias})")
        
        if confluence_score and confluence_score < self.settings.minimum_confluence:
            wait_reasons.append(f"Confluence below threshold ({confluence_score:.0f})")
        
        if signal_score and signal_score < self.settings.minimum_signal_score:
            wait_reasons.append(f"Signal quality below threshold ({signal_score:.0f})")
        
        if not liquidity_bias:
            wait_reasons.append("Liquidity not confirmed")
        
        if trend_strength in ["WEAK", "VERY_WEAK"]:
            wait_reasons.append(f"Weak momentum ({trend_strength})")
        
        if wait_reasons:
            reasoning.extend(wait_reasons)
            return DecisionType.WAIT, 43.0, reasoning
        
        # Default to WAIT if conditions are unclear
        reasoning.append("Insufficient evidence for trade recommendation")
        return DecisionType.WAIT, 50.0, reasoning
    
    def _generate_warnings(
        self,
        trend_result: Optional[TrendResult],
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse],
        mt_confluence_result: Optional[MultiTimeframeConfluenceResult],
        signal_score_result: Optional[SignalScoreResult]
    ) -> List[str]:
        """Generate warnings about the decision."""
        warnings = []
        
        # High volatility warning
        if indicator_result and indicator_result.atr_14:
            atr_ratio = indicator_result.atr_14 / indicator_result.bb_middle if indicator_result.bb_middle else 0
            if atr_ratio > 0.02:
                warnings.append("High volatility detected")
        
        # Weak confluence warning
        if mt_confluence_result and mt_confluence_result.overallConfluenceScore < self.settings.minimum_confluence:
            warnings.append("Weak multi-timeframe confluence")
        
        # Low confidence warning
        if trend_result and trend_result.confidence < self.settings.minimum_confidence:
            warnings.append("Low trend confidence")
        
        # Missing liquidity warning
        if structure_result and not structure_result.liquidityZones:
            warnings.append("Missing liquidity confirmation")
        
        # Indicator disagreement warning
        if indicator_result and indicator_result.rsi_14:
            if indicator_result.rsi_14 > 70 and indicator_result.macd_line < indicator_result.macd_signal:
                warnings.append("Indicator disagreement (RSI overbought, MACD bearish)")
            elif indicator_result.rsi_14 < 30 and indicator_result.macd_line > indicator_result.macd_signal:
                warnings.append("Indicator disagreement (RSI oversold, MACD bullish)")
        
        # Sideways market warning
        if trend_result and trend_result.direction.value == "SIDEWAYS":
            warnings.append("Sideways market detected")
        
        # High risk warning
        if signal_score_result and signal_score_result.riskRating.value == "HIGH":
            warnings.append("High risk rating")
        
        return warnings
    
    def get_statistics(self) -> dict:
        """Get engine statistics."""
        avg_confidence = (
            self._total_confidence / self._total_decisions
            if self._total_decisions > 0
            else 0.0
        )
        
        avg_execution_time = (
            self._total_execution_time / self._total_decisions
            if self._total_decisions > 0
            else 0.0
        )
        
        return {
            'totalDecisions': self._total_decisions,
            'buyCount': self._buy_count,
            'sellCount': self._sell_count,
            'waitCount': self._wait_count,
            'averageConfidence': round(avg_confidence, 2),
            'averageExecutionTime': round(avg_execution_time, 2),
            'cacheHits': self._cache_hits,
            'cacheMisses': self._cache_misses,
            'highestConfidence': round(self._highest_confidence, 2) if self._total_decisions > 0 else None,
            'lowestConfidence': round(self._lowest_confidence, 2) if self._total_decisions > 0 else None
        }
    
    def reset_statistics(self) -> None:
        """Reset engine statistics."""
        self._total_decisions = 0
        self._buy_count = 0
        self._sell_count = 0
        self._wait_count = 0
        self._total_confidence = 0.0
        self._total_execution_time = 0.0
        self._cache_hits = 0
        self._cache_misses = 0
        self._highest_confidence = 0.0
        self._lowest_confidence = 100.0
        self._cache.clear()
