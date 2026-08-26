"""
Falcon Multi-Timeframe Confluence Engine
Analyzes market conditions across multiple timeframes for confluence.
"""
import time
from typing import List, Optional
from datetime import datetime, timezone
from app.schemas.confluence_models import (
    TimeframeAnalysis, MultiTimeframeConfluenceResult, MultiTimeframeRecommendation
)
from app.schemas.trend_models import TrendResult
from app.schemas.market_structure_models import MarketStructureResult
from app.schemas.indicator_models import IndicatorResponse


class MultiTimeframeConfluenceEngine:
    """
    Multi-timeframe confluence analysis engine.
    
    Analyzes the same instrument across multiple timeframes (H4, H1, M15, M5)
    and determines whether market conditions align before producing a trading recommendation.
    
    Timeframe Weights:
    - H4: 40%
    - H1: 30%
    - M15: 20%
    - M5: 10%
    
    Higher timeframes have greater influence than lower ones.
    """
    
    def __init__(self, default_timeframes: Optional[List[str]] = None):
        """
        Initialize the multi-timeframe confluence engine.
        
        Args:
            default_timeframes: Default timeframes to analyze (default: H4, H1, M15, M5)
        """
        self.default_timeframes = default_timeframes or ["H4", "H1", "M15", "M5"]
        self.timeframe_weights = {
            "H4": 0.40,
            "H1": 0.30,
            "M15": 0.20,
            "M5": 0.10
        }
        
        # Cache (symbol + timeframe set -> result)
        self._cache: dict = {}
        self._cache_ttl = 60  # 1 minute cache TTL
        
        # Statistics
        self._calculations = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_execution_time = 0.0
        self._fastest_calculation = float('inf')
        self._slowest_calculation = 0.0
    
    def calculate_confluence(
        self,
        symbol: str,
        timeframe_data: dict[str, dict[str, any]],
        timeframes: Optional[List[str]] = None
    ) -> MultiTimeframeConfluenceResult:
        """
        Calculate multi-timeframe confluence.
        
        Args:
            symbol: Instrument symbol
            timeframe_data: Dictionary mapping timeframes to their analysis data
                          {timeframe: {"trend": TrendResult, "structure": MarketStructureResult, "indicator": IndicatorResponse}}
            timeframes: Timeframes to analyze (default: H4, H1, M15, M5)
            
        Returns:
            MultiTimeframeConfluenceResult with complete analysis
        """
        start_time = time.time()
        
        # Use provided timeframes or defaults
        timeframes = timeframes or self.default_timeframes
        
        # Create cache key
        cache_key = f"{symbol}_{'_'.join(sorted(timeframes))}"
        
        # Check cache
        if cache_key in self._cache:
            cached_result, cache_time = self._cache[cache_key]
            if (datetime.now(timezone.utc) - cache_time).total_seconds() < self._cache_ttl:
                self._cache_hits += 1
                return cached_result
        
        self._cache_misses += 1
        
        # Collect timeframe analyses
        analyses = []
        for tf in timeframes:
            if tf in timeframe_data:
                analysis = self._create_timeframe_analysis(tf, timeframe_data[tf])
                if analysis:
                    analyses.append(analysis)
        
        # Calculate confluence score
        confluence_score = self._calculate_confluence_score(analyses, timeframes)
        
        # Determine recommendation
        recommendation, reason, aligned, conflicting = self._determine_recommendation(
            analyses, confluence_score
        )
        
        # Update statistics
        execution_time = (time.time() - start_time) * 1000
        self._calculations += 1
        self._total_execution_time += execution_time
        self._fastest_calculation = min(self._fastest_calculation, execution_time)
        self._slowest_calculation = max(self._slowest_calculation, execution_time)
        
        # Create result
        result = MultiTimeframeConfluenceResult(
            symbol=symbol,
            analyses=analyses,
            alignedTimeframes=aligned,
            conflictingTimeframes=conflicting,
            overallConfluenceScore=confluence_score,
            recommendation=recommendation,
            recommendationReason=reason
        )
        
        # Update cache
        self._cache[cache_key] = (result, datetime.now(timezone.utc))
        
        return result
    
    def _create_timeframe_analysis(
        self,
        timeframe: str,
        data: dict[str, any]
    ) -> Optional[TimeframeAnalysis]:
        """
        Create timeframe analysis from trend, structure, and indicator data.
        
        Args:
            timeframe: Timeframe identifier
            data: Dictionary with trend, structure, and indicator results
            
        Returns:
            TimeframeAnalysis or None if data is insufficient
        """
        trend_result = data.get("trend")
        structure_result = data.get("structure")
        indicator_result = data.get("indicator")
        
        if not trend_result or not structure_result or not indicator_result:
            return None
        
        # Get current price from latest candle or indicator
        current_price = indicator_result.bb_middle
        
        # Calculate support/resistance distances
        support_level = None
        resistance_level = None
        distance_to_support = None
        distance_to_resistance = None
        
        if structure_result.support:
            support_level = min(structure_result.support, key=lambda x: abs(x - current_price))
            distance_to_support = abs(current_price - support_level)
        
        if structure_result.resistance:
            resistance_level = min(structure_result.resistance, key=lambda x: abs(x - current_price))
            distance_to_resistance = abs(resistance_level - current_price)
        
        # Determine EMA alignment
        ema_alignment = "Bullish"
        if indicator_result.ema_20 and indicator_result.ema_50 and indicator_result.ema_200:
            if indicator_result.ema_20 > indicator_result.ema_50 > indicator_result.ema_200:
                ema_alignment = "Bullish"
            elif indicator_result.ema_20 < indicator_result.ema_50 < indicator_result.ema_200:
                ema_alignment = "Bearish"
            else:
                ema_alignment = "Mixed"
        
        # Create analysis summary
        analysis_summary = f"{trend_result.direction.value} trend ({trend_result.strength.value}) with {structure_result.direction.value} structure"
        
        return TimeframeAnalysis(
            timeframe=timeframe,
            trendDirection=trend_result.direction.value,
            trendStrength=trend_result.strength.value,
            confidence=trend_result.confidence,
            marketStructure=f"{structure_result.direction.value} ({structure_result.currentEvent.value})",
            supportLevel=support_level,
            resistanceLevel=resistance_level,
            currentPrice=current_price,
            distanceToSupport=distance_to_support,
            distanceToResistance=distance_to_resistance,
            emaAlignment=ema_alignment,
            analysisSummary=analysis_summary
        )
    
    def _calculate_confluence_score(
        self,
        analyses: List[TimeframeAnalysis],
        timeframes: List[str]
    ) -> float:
        """
        Calculate overall confluence score using weighted scoring.
        
        Args:
            analyses: List of timeframe analyses
            timeframes: Timeframes being analyzed
            
        Returns:
            Confluence score (0-100)
        """
        if not analyses:
            return 0.0
        
        total_score = 0.0
        total_weight = 0.0
        
        # Count bullish and bearish signals
        bullish_count = 0
        bearish_count = 0
        
        for analysis in analyses:
            weight = self.timeframe_weights.get(analysis.timeframe, 0.25)
            
            # Base score from confidence
            score = analysis.confidence
            
            # Adjust based on trend direction
            if analysis.trendDirection == "BULLISH":
                bullish_count += 1
            elif analysis.trendDirection == "BEARISH":
                bearish_count += 1
            
            total_score += score * weight
            total_weight += weight
        
        # Normalize by total weight
        if total_weight > 0:
            total_score = total_score / total_weight
        
        # Apply confluence bonus for alignment
        if bullish_count == len(analyses) or bearish_count == len(analyses):
            # Full alignment bonus
            total_score = min(100.0, total_score * 1.1)
        elif bullish_count > 0 and bearish_count > 0:
            # Mixed signals penalty
            total_score = total_score * 0.8
        
        return min(100.0, max(0.0, total_score))
    
    def _determine_recommendation(
        self,
        analyses: List[TimeframeAnalysis],
        confluence_score: float
    ) -> tuple[MultiTimeframeRecommendation, str, List[str], List[str]]:
        """
        Determine trading recommendation based on confluence.
        
        Args:
            analyses: List of timeframe analyses
            confluence_score: Overall confluence score
            
        Returns:
            Tuple of (recommendation, reason, aligned_timeframes, conflicting_timeframes)
        """
        if not analyses:
            return MultiTimeframeRecommendation.NO_TRADE, "Insufficient data", [], []
        
        # Count bullish and bearish signals by timeframe weight
        bullish_weight = 0.0
        bearish_weight = 0.0
        bullish_timeframes = []
        bearish_timeframes = []
        sideways_timeframes = []
        
        for analysis in analyses:
            weight = self.timeframe_weights.get(analysis.timeframe, 0.25)
            
            if analysis.trendDirection == "BULLISH":
                bullish_weight += weight
                bullish_timeframes.append(analysis.timeframe)
            elif analysis.trendDirection == "BEARISH":
                bearish_weight += weight
                bearish_timeframes.append(analysis.timeframe)
            else:
                sideways_timeframes.append(analysis.timeframe)
        
        # Determine aligned and conflicting timeframes (as strings)
        if bullish_weight > bearish_weight:
            aligned = bullish_timeframes
            conflicting = bearish_timeframes + sideways_timeframes
        elif bearish_weight > bullish_weight:
            aligned = bearish_timeframes
            conflicting = bullish_timeframes + sideways_timeframes
        else:
            # Equal weight - all are conflicting
            aligned = []
            conflicting = [analysis.timeframe for analysis in analyses]
        
        # Make recommendation based on confluence score and alignment
        if confluence_score >= 90:
            if bullish_weight > bearish_weight:
                return MultiTimeframeRecommendation.BUY, "Strong bullish agreement across all monitored timeframes.", aligned, conflicting
            elif bearish_weight > bullish_weight:
                return MultiTimeframeRecommendation.SELL, "Strong bearish agreement across all monitored timeframes.", aligned, conflicting
            else:
                return MultiTimeframeRecommendation.NO_TRADE, "Mixed signals despite high confluence score.", aligned, conflicting
        elif confluence_score >= 75:
            if bullish_weight > bearish_weight:
                return MultiTimeframeRecommendation.BUY, "Strong bullish alignment with minor timeframe disagreement.", aligned, conflicting
            elif bearish_weight > bullish_weight:
                return MultiTimeframeRecommendation.SELL, "Strong bearish alignment with minor timeframe disagreement.", aligned, conflicting
            else:
                return MultiTimeframeRecommendation.WAIT, "Mixed timeframe alignment requires caution.", aligned, conflicting
        elif confluence_score >= 50:
            if bullish_weight > bearish_weight:
                return MultiTimeframeRecommendation.BUY, "Bullish bias with some disagreement.", aligned, conflicting
            elif bearish_weight > bullish_weight:
                return MultiTimeframeRecommendation.SELL, "Bearish bias with some disagreement.", aligned, conflicting
            else:
                return MultiTimeframeRecommendation.WAIT, "Conflicting market structure between timeframes.", aligned, conflicting
        else:
            return MultiTimeframeRecommendation.NO_TRADE, "Low confluence score - no trade recommended.", aligned, conflicting
    
    def get_statistics(self) -> dict:
        """
        Get engine statistics.
        
        Returns:
            Dictionary with performance metrics
        """
        avg_execution_time = (
            self._total_execution_time / self._calculations
            if self._calculations > 0
            else 0.0
        )
        
        return {
            'calculations': self._calculations,
            'cacheHits': self._cache_hits,
            'cacheMisses': self._cache_misses,
            'averageExecutionTime': round(avg_execution_time, 2),
            'fastestCalculation': round(self._fastest_calculation, 2) if self._fastest_calculation != float('inf') else None,
            'slowestCalculation': round(self._slowest_calculation, 2) if self._slowest_calculation > 0 else None
        }
    
    def reset_statistics(self) -> None:
        """Reset engine statistics."""
        self._calculations = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_execution_time = 0.0
        self._fastest_calculation = float('inf')
        self._slowest_calculation = 0.0
        self._cache.clear()
