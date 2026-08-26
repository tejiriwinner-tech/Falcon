"""
Falcon Confidence Engine
Calculates AI confidence in trading recommendations
"""
from typing import Optional, Dict, Any
from enum import Enum

from app.schemas.trend_models import TrendResult
from app.schemas.market_structure_models import MarketStructureResult
from app.schemas.indicator_models import IndicatorResponse
from app.schemas.confluence_models import MultiTimeframeConfluenceResult
from app.schemas.signal_score_models import SignalScoreResult


class ConfidenceLevel(str, Enum):
    """Confidence level classifications."""
    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    AVOID = "AVOID"


class ConfidenceAssessment:
    """Confidence assessment result."""
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        confidence_level: ConfidenceLevel,
        confidence_percentage: float,
        reasoning: str
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.confidence_level = confidence_level
        self.confidence_percentage = confidence_percentage
        self.reasoning = reasoning
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'confidenceLevel': self.confidence_level.value,
            'confidencePercentage': self.confidence_percentage,
            'reasoning': self.reasoning
        }


class ConfidenceEngine:
    """
    Confidence Engine - AI confidence calculation.
    
    Calculates confidence based on:
    - Trend confidence
    - Structure confidence
    - Signal score
    - Multi-timeframe confluence
    - Indicator alignment
    
    Output:
    - Confidence Level (VERY_HIGH/HIGH/MEDIUM/LOW/AVOID)
    - Confidence Percentage (0-100%)
    """
    
    def __init__(self):
        """Initialize the confidence engine."""
        self._calculation_count = 0
    
    def calculate_confidence(
        self,
        symbol: str,
        timeframe: str,
        trend_result: Optional[TrendResult],
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse],
        mt_confluence_result: Optional[MultiTimeframeConfluenceResult],
        signal_score_result: Optional[SignalScoreResult]
    ) -> ConfidenceAssessment:
        """
        Calculate AI confidence.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe
            trend_result: Trend analysis
            structure_result: Market structure analysis
            indicator_result: Indicator analysis
            mt_confluence_result: Multi-timeframe confluence
            signal_score_result: Signal score
            
        Returns:
            ConfidenceAssessment with confidence level and percentage
        """
        self._calculation_count += 1
        
        confidence_factors = []
        
        if trend_result:
            confidence_factors.append(trend_result.confidence)
        
        if structure_result:
            confidence_factors.append(structure_result.confidence)
        
        if mt_confluence_result:
            confidence_factors.append(mt_confluence_result.overallConfluenceScore)
        
        if signal_score_result:
            confidence_factors.append(signal_score_result.overallScore)
        
        if indicator_result:
            confidence_factors.append(self._calculate_indicator_confidence(indicator_result))
        
        if not confidence_factors:
            return ConfidenceAssessment(
                symbol=symbol,
                timeframe=timeframe,
                confidence_level=ConfidenceLevel.AVOID,
                confidence_percentage=0.0,
                reasoning="Insufficient data for confidence calculation"
            )
        
        confidence_percentage = sum(confidence_factors) / len(confidence_factors)
        
        confidence_level = self._determine_confidence_level(confidence_percentage)
        
        reasoning = self._generate_reasoning(
            confidence_level, confidence_percentage, confidence_factors
        )
        
        return ConfidenceAssessment(
            symbol=symbol,
            timeframe=timeframe,
            confidence_level=confidence_level,
            confidence_percentage=confidence_percentage,
            reasoning=reasoning
        )
    
    def _calculate_indicator_confidence(
        self,
        indicator_result: IndicatorResponse
    ) -> float:
        """Calculate confidence from indicators."""
        confidence = 70.0
        
        if 40 <= indicator_result.rsi_14 <= 60:
            confidence += 10.0
        
        if indicator_result.macd_line and indicator_result.macd_signal:
            confidence += 10.0
        
        if indicator_result.ema_20 and indicator_result.ema_50:
            confidence += 10.0
        
        return min(100.0, confidence)
    
    def _determine_confidence_level(self, confidence_percentage: float) -> ConfidenceLevel:
        """Determine confidence level from percentage."""
        if confidence_percentage >= 90:
            return ConfidenceLevel.VERY_HIGH
        elif confidence_percentage >= 75:
            return ConfidenceLevel.HIGH
        elif confidence_percentage >= 60:
            return ConfidenceLevel.MEDIUM
        elif confidence_percentage >= 40:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.AVOID
    
    def _generate_reasoning(
        self,
        confidence_level: ConfidenceLevel,
        confidence_percentage: float,
        confidence_factors: list
    ) -> str:
        """Generate reasoning for confidence assessment."""
        num_factors = len(confidence_factors)
        
        if confidence_level == ConfidenceLevel.VERY_HIGH:
            return f"Very high confidence ({confidence_percentage:.0f}%) based on {num_factors} aligned factors"
        elif confidence_level == ConfidenceLevel.HIGH:
            return f"High confidence ({confidence_percentage:.0f}%) with strong analytical agreement"
        elif confidence_level == ConfidenceLevel.MEDIUM:
            return f"Medium confidence ({confidence_percentage:.0f}%) with acceptable alignment"
        elif confidence_level == ConfidenceLevel.LOW:
            return f"Low confidence ({confidence_percentage:.0f}%) with weak analytical support"
        else:
            return f"Avoid trading ({confidence_percentage:.0f}%) due to insufficient confidence"
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            'calculationCount': self._calculation_count
        }
