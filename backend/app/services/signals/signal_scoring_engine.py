"""
Falcon Signal Scoring Engine
Evaluates trading opportunities by combining outputs from all Falcon analysis engines.
"""
import time
from typing import Optional, Dict, List
from datetime import datetime, timezone
from app.schemas.signal_score_models import (
    SignalComponentScore, SignalQuality, SignalRecommendation, RiskRating, SignalScoreResult
)
from app.schemas.trend_models import TrendResult, TrendDirection
from app.schemas.market_structure_models import MarketStructureResult, StructureDirection
from app.schemas.indicator_models import IndicatorResponse
from app.schemas.confluence_models import MultiTimeframeConfluenceResult


class SignalScoringEngine:
    """
    Signal scoring engine that evaluates trading opportunities.
    
    Combines outputs from all Falcon analysis engines into a single
    quantitative Signal Quality Score (0-100).
    
    Scoring Categories:
    - Trend: 25 points max
    - Market Structure: 20 points max
    - Support/Resistance: 15 points max
    - Momentum: 15 points max
    - Liquidity: 10 points max
    - Multi-Timeframe Confluence: 15 points max
    - Total: 100 points
    """
    
    def __init__(self):
        """Initialize the signal scoring engine."""
        # Component weights
        self.weights = {
            "Trend": 25.0,
            "Structure": 20.0,
            "SupportResistance": 15.0,
            "Momentum": 15.0,
            "Liquidity": 10.0,
            "MultiTimeframeConfluence": 15.0
        }
        
        # Cache (symbol + timeframe -> result)
        self._cache: dict = {}
        self._cache_ttl = 60  # 60 seconds cache TTL
        
        # Statistics
        self._calculations = 0
        self._total_execution_time = 0.0
        self._cache_hits = 0
        self._cache_misses = 0
        self._highest_score = 0.0
        self._lowest_score = 100.0
    
    def calculate_signal_score(
        self,
        symbol: str,
        timeframe: str,
        trend_result: Optional[TrendResult] = None,
        structure_result: Optional[MarketStructureResult] = None,
        indicator_result: Optional[IndicatorResponse] = None,
        mt_confluence_result: Optional[MultiTimeframeConfluenceResult] = None,
        current_price: Optional[float] = None
    ) -> SignalScoreResult:
        """
        Calculate signal quality score.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe analyzed
            trend_result: Trend analysis result
            structure_result: Market structure result
            indicator_result: Indicator analysis result
            mt_confluence_result: Multi-timeframe confluence result
            current_price: Current market price
            
        Returns:
            SignalScoreResult with complete scoring analysis
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
        
        # Calculate component scores
        component_scores = []
        
        # Trend Score (25 points)
        trend_score = self._score_trend(trend_result)
        component_scores.append(trend_score)
        
        # Structure Score (20 points)
        structure_score = self._score_structure(structure_result)
        component_scores.append(structure_score)
        
        # Support/Resistance Score (15 points)
        sr_score = self._score_support_resistance(structure_result, current_price)
        component_scores.append(sr_score)
        
        # Momentum Score (15 points)
        momentum_score = self._score_momentum(indicator_result)
        component_scores.append(momentum_score)
        
        # Liquidity Score (10 points)
        liquidity_score = self._score_liquidity(structure_result)
        component_scores.append(liquidity_score)
        
        # Multi-Timeframe Confluence Score (15 points)
        mt_confluence_score = self._score_mt_confluence(mt_confluence_result)
        component_scores.append(mt_confluence_score)
        
        # Calculate overall score
        overall_score = sum(cs.rawScore for cs in component_scores)
        
        # Classify quality
        quality = self._classify_quality(overall_score)
        
        # Determine recommendation
        recommendation, confidence = self._determine_recommendation(
            overall_score, trend_result, mt_confluence_result
        )
        
        # Determine risk rating
        risk_rating = self._determine_risk_rating(
            indicator_result, structure_result, mt_confluence_result
        )
        
        # Generate analysis summary
        analysis_summary = self._generate_analysis_summary(
            overall_score, quality, recommendation, component_scores
        )
        
        # Update statistics
        execution_time = (time.time() - start_time) * 1000
        self._calculations += 1
        self._total_execution_time += execution_time
        self._highest_score = max(self._highest_score, overall_score)
        self._lowest_score = min(self._lowest_score, overall_score)
        
        # Create result
        result = SignalScoreResult(
            symbol=symbol,
            timeframe=timeframe,
            overallScore=overall_score,
            quality=quality,
            recommendation=recommendation,
            confidence=confidence,
            componentScores=component_scores,
            riskRating=risk_rating,
            analysisSummary=analysis_summary
        )
        
        # Update cache
        self._cache[cache_key] = (result, datetime.now(timezone.utc))
        
        return result
    
    def _score_trend(self, trend_result: Optional[TrendResult]) -> SignalComponentScore:
        """Score trend component (25 points max)."""
        weight = self.weights["Trend"]
        
        if not trend_result:
            return SignalComponentScore(
                componentName="Trend",
                weight=weight,
                rawScore=0.0,
                weightedScore=0.0,
                explanation="No trend data available."
            )
        
        score = 0.0
        explanations = []
        
        # Trend direction (10 points)
        if trend_result.direction == TrendDirection.BULLISH or trend_result.direction == TrendDirection.BEARISH:
            score += 10.0
            explanations.append(f"{trend_result.direction.value} trend direction.")
        else:
            explanations.append(f"{trend_result.direction.value} trend direction.")
        
        # Trend strength (8 points)
        strength_scores = {
            "VERY_STRONG": 8.0,
            "STRONG": 7.0,
            "MODERATE": 5.0,
            "WEAK": 3.0,
            "VERY_WEAK": 1.0
        }
        score += strength_scores.get(trend_result.strength.value, 0.0)
        explanations.append(f"{trend_result.strength.value} strength.")
        
        # Confidence (7 points)
        confidence_score = (trend_result.confidence / 100.0) * 7.0
        score += confidence_score
        explanations.append(f"{trend_result.confidence:.0f}% confidence.")
        
        # EMA alignment bonus
        if trend_result.ema_alignment >= 80:
            score += 2.0
            explanations.append("Strong EMA alignment.")
        
        # Clamp to max weight
        score = min(score, weight)
        
        return SignalComponentScore(
            componentName="Trend",
            weight=weight,
            rawScore=score,
            weightedScore=(score / weight) * 100,
            explanation=" ".join(explanations)
        )
    
    def _score_structure(self, structure_result: Optional[MarketStructureResult]) -> SignalComponentScore:
        """Score market structure component (20 points max)."""
        weight = self.weights["Structure"]
        
        if not structure_result:
            return SignalComponentScore(
                componentName="Structure",
                weight=weight,
                rawScore=0.0,
                weightedScore=0.0,
                explanation="No structure data available."
            )
        
        score = 0.0
        explanations = []
        
        # BOS/CHoCH (8 points)
        if structure_result.currentEvent.value in ["BOS", "CHoCH"]:
            score += 8.0
            explanations.append(f"{structure_result.currentEvent.value} confirmed.")
        else:
            explanations.append(f"{structure_result.currentEvent.value} detected.")
        
        # Higher Highs/Higher Lows (6 points)
        if structure_result.higherHigh and structure_result.higherLow:
            score += 6.0
            explanations.append("HH and HL pattern.")
        elif structure_result.higherHigh or structure_result.higherLow:
            score += 3.0
            explanations.append("Partial HH/HL pattern.")
        
        # Market phase (4 points)
        if structure_result.marketPhase == "TRENDING":
            score += 4.0
            explanations.append("Trending market phase.")
        elif structure_result.marketPhase == "RANGING":
            score += 2.0
            explanations.append("Ranging market phase.")
        
        # Structure confidence (2 points)
        if structure_result.confidence >= 70:
            score += 2.0
            explanations.append(f"{structure_result.confidence:.0f}% structure confidence.")
        
        # Clamp to max weight
        score = min(score, weight)
        
        return SignalComponentScore(
            componentName="Structure",
            weight=weight,
            rawScore=score,
            weightedScore=(score / weight) * 100,
            explanation=" ".join(explanations)
        )
    
    def _score_support_resistance(
        self,
        structure_result: Optional[MarketStructureResult],
        current_price: Optional[float]
    ) -> SignalComponentScore:
        """Score support/resistance component (15 points max)."""
        weight = self.weights["SupportResistance"]
        
        if not structure_result or not current_price:
            return SignalComponentScore(
                componentName="SupportResistance",
                weight=weight,
                rawScore=0.0,
                weightedScore=0.0,
                explanation="No S/R data available."
            )
        
        score = 0.0
        explanations = []
        
        # Distance to support/resistance (8 points)
        nearest_support = min(structure_result.support, key=lambda x: abs(x - current_price)) if structure_result.support else None
        nearest_resistance = min(structure_result.resistance, key=lambda x: abs(x - current_price)) if structure_result.resistance else None
        
        if nearest_support:
            dist_to_support = abs(current_price - nearest_support)
            if 0.5 <= dist_to_support <= 2.0:  # Optimal distance
                score += 4.0
                explanations.append(f"Near support ({dist_to_support:.2f}).")
        
        if nearest_resistance:
            dist_to_resistance = abs(nearest_resistance - current_price)
            if 0.5 <= dist_to_resistance <= 2.0:  # Optimal distance
                score += 4.0
                explanations.append(f"Near resistance ({dist_to_resistance:.2f}).")
        
        # S/R quality (4 points)
        if structure_result.activeDemandZones or structure_result.activeSupplyZones:
            score += 4.0
            explanations.append("Active S/R zones detected.")
        
        # Zone proximity (3 points)
        if structure_result.discountZone or structure_result.premiumZone:
            score += 3.0
            explanations.append("In premium/discount zone.")
        
        # Clamp to max weight
        score = min(score, weight)
        
        return SignalComponentScore(
            componentName="SupportResistance",
            weight=weight,
            rawScore=score,
            weightedScore=(score / weight) * 100,
            explanation=" ".join(explanations) if explanations else "No clear S/R levels."
        )
    
    def _score_momentum(self, indicator_result: Optional[IndicatorResponse]) -> SignalComponentScore:
        """Score momentum component (15 points max)."""
        weight = self.weights["Momentum"]
        
        if not indicator_result:
            return SignalComponentScore(
                componentName="Momentum",
                weight=weight,
                rawScore=0.0,
                weightedScore=0.0,
                explanation="No momentum data available."
            )
        
        score = 0.0
        explanations = []
        
        # RSI (5 points)
        if 40 <= indicator_result.rsi_14 <= 60:
            score += 5.0
            explanations.append(f"RSI healthy at {indicator_result.rsi_14:.0f}.")
        elif 30 <= indicator_result.rsi_14 <= 70:
            score += 3.0
            explanations.append(f"RSI at {indicator_result.rsi_14:.0f}.")
        else:
            explanations.append(f"RSI extreme at {indicator_result.rsi_14:.0f}.")
        
        # MACD (5 points)
        if indicator_result.macd_line > indicator_result.macd_signal:
            score += 5.0
            explanations.append("MACD bullish.")
        elif indicator_result.macd_line < indicator_result.macd_signal:
            score += 2.0
            explanations.append("MACD bearish.")
        
        # EMA alignment (5 points)
        if indicator_result.ema_20 > indicator_result.ema_50 > indicator_result.ema_200:
            score += 5.0
            explanations.append("Bullish EMA alignment.")
        elif indicator_result.ema_20 < indicator_result.ema_50 < indicator_result.ema_200:
            score += 5.0
            explanations.append("Bearish EMA alignment.")
        
        # Clamp to max weight
        score = min(score, weight)
        
        return SignalComponentScore(
            componentName="Momentum",
            weight=weight,
            rawScore=score,
            weightedScore=(score / weight) * 100,
            explanation=" ".join(explanations)
        )
    
    def _score_liquidity(self, structure_result: Optional[MarketStructureResult]) -> SignalComponentScore:
        """Score liquidity component (10 points max)."""
        weight = self.weights["Liquidity"]
        
        if not structure_result:
            return SignalComponentScore(
                componentName="Liquidity",
                weight=weight,
                rawScore=0.0,
                weightedScore=0.0,
                explanation="No liquidity data available."
            )
        
        score = 0.0
        explanations = []
        
        # Liquidity zones (5 points)
        if structure_result.liquidityZones:
            score += 5.0
            explanations.append(f"{len(structure_result.liquidityZones)} liquidity zones detected.")
        
        # Equal highs/lows (3 points)
        if structure_result.swingHighs or structure_result.swingLows:
            score += 3.0
            explanations.append("Swing points detected.")
        
        # Stop hunt zones (2 points)
        if structure_result.activeSupplyZones or structure_result.activeDemandZones:
            score += 2.0
            explanations.append("Potential stop hunt zones.")
        
        # Clamp to max weight
        score = min(score, weight)
        
        return SignalComponentScore(
            componentName="Liquidity",
            weight=weight,
            rawScore=score,
            weightedScore=(score / weight) * 100,
            explanation=" ".join(explanations) if explanations else "No clear liquidity signals."
        )
    
    def _score_mt_confluence(self, mt_confluence_result: Optional[MultiTimeframeConfluenceResult]) -> SignalComponentScore:
        """Score multi-timeframe confluence component (15 points max)."""
        weight = self.weights["MultiTimeframeConfluence"]
        
        if not mt_confluence_result:
            return SignalComponentScore(
                componentName="MultiTimeframeConfluence",
                weight=weight,
                rawScore=0.0,
                weightedScore=0.0,
                explanation="No MT confluence data available."
            )
        
        # Use the confluence score directly (0-100) and scale to 15 points
        raw_score = (mt_confluence_result.overallConfluenceScore / 100.0) * weight
        
        explanation = f"MT confluence score: {mt_confluence_result.overallConfluenceScore:.0f}. "
        explanation += f"Recommendation: {mt_confluence_result.recommendation.value}."
        
        return SignalComponentScore(
            componentName="MultiTimeframeConfluence",
            weight=weight,
            rawScore=raw_score,
            weightedScore=mt_confluence_result.overallConfluenceScore,
            explanation=explanation
        )
    
    def _classify_quality(self, score: float) -> SignalQuality:
        """Classify signal quality based on score."""
        if score >= 95:
            return SignalQuality.EXCELLENT
        elif score >= 85:
            return SignalQuality.VERY_GOOD
        elif score >= 70:
            return SignalQuality.GOOD
        elif score >= 55:
            return SignalQuality.FAIR
        elif score > 0:
            return SignalQuality.POOR
        else:
            return SignalQuality.INVALID
    
    def _determine_recommendation(
        self,
        score: float,
        trend_result: Optional[TrendResult],
        mt_confluence_result: Optional[MultiTimeframeConfluenceResult]
    ) -> tuple[SignalRecommendation, float]:
        """Determine trading recommendation."""
        confidence = score
        
        # Determine direction from trend or MT confluence
        direction = None
        if trend_result and trend_result.direction in [TrendDirection.BULLISH, TrendDirection.BEARISH]:
            direction = trend_result.direction.value
        elif mt_confluence_result and mt_confluence_result.recommendation in ["BUY", "SELL"]:
            direction = mt_confluence_result.recommendation.value
        
        if score >= 95:
            if direction == "BULLISH":
                return SignalRecommendation.STRONG_BUY, confidence
            elif direction == "BEARISH":
                return SignalRecommendation.STRONG_SELL, confidence
            else:
                return SignalRecommendation.NO_SIGNAL, confidence
        elif score >= 85:
            if direction == "BULLISH":
                return SignalRecommendation.BUY, confidence
            elif direction == "BEARISH":
                return SignalRecommendation.SELL, confidence
            else:
                return SignalRecommendation.WAIT, confidence
        elif score >= 70:
            if direction == "BULLISH":
                return SignalRecommendation.BUY, confidence
            elif direction == "BEARISH":
                return SignalRecommendation.SELL, confidence
            else:
                return SignalRecommendation.WAIT, confidence
        elif score >= 55:
            return SignalRecommendation.WAIT, confidence
        else:
            return SignalRecommendation.NO_SIGNAL, confidence
    
    def _determine_risk_rating(
        self,
        indicator_result: Optional[IndicatorResponse],
        structure_result: Optional[MarketStructureResult],
        mt_confluence_result: Optional[MultiTimeframeConfluenceResult]
    ) -> RiskRating:
        """Determine risk rating."""
        risk_factors = 0
        
        # High volatility (ATR)
        if indicator_result and indicator_result.atr_14:
            atr_ratio = indicator_result.atr_14 / indicator_result.bb_middle if indicator_result.bb_middle else 0
            if atr_ratio > 0.02:  # > 2% ATR
                risk_factors += 1
        
        # Low confluence
        if mt_confluence_result and mt_confluence_result.overallConfluenceScore < 70:
            risk_factors += 1
        
        # Poor structure
        if structure_result and structure_result.confidence < 60:
            risk_factors += 1
        
        if risk_factors >= 2:
            return RiskRating.HIGH
        elif risk_factors == 1:
            return RiskRating.MEDIUM
        else:
            return RiskRating.LOW
    
    def _generate_analysis_summary(
        self,
        score: float,
        quality: SignalQuality,
        recommendation: SignalRecommendation,
        component_scores: List[SignalComponentScore]
    ) -> str:
        """Generate analysis summary."""
        if quality == SignalQuality.EXCELLENT:
            return f"Excellent {recommendation.value} setup with {score:.0f} score. Strong confluence across all components."
        elif quality == SignalQuality.VERY_GOOD:
            return f"Very good {recommendation.value} setup with {score:.0f} score. Strong analytical alignment."
        elif quality == SignalQuality.GOOD:
            return f"Good {recommendation.value} setup with {score:.0f} score. Favorable conditions detected."
        elif quality == SignalQuality.FAIR:
            return f"Fair {recommendation.value} setup with {score:.0f} score. Moderate conditions, proceed with caution."
        elif quality == SignalQuality.POOR:
            return f"Poor setup with {score:.0f} score. Insufficient confluence for trading."
        else:
            return "Invalid setup. Insufficient data for analysis."
    
    def get_statistics(self) -> dict:
        """Get engine statistics."""
        avg_execution_time = (
            self._total_execution_time / self._calculations
            if self._calculations > 0
            else 0.0
        )
        
        return {
            'calculations': self._calculations,
            'averageExecutionTime': round(avg_execution_time, 2),
            'cacheHits': self._cache_hits,
            'cacheMisses': self._cache_misses,
            'highestScore': round(self._highest_score, 2) if self._calculations > 0 else None,
            'lowestScore': round(self._lowest_score, 2) if self._calculations > 0 else None
        }
    
    def reset_statistics(self) -> None:
        """Reset engine statistics."""
        self._calculations = 0
        self._total_execution_time = 0.0
        self._cache_hits = 0
        self._cache_misses = 0
        self._highest_score = 0.0
        self._lowest_score = 100.0
        self._cache.clear()
