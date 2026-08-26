"""
Falcon Trend Detector
Determines Primary, Secondary, Intraday, Swing Trends and Strength
"""
from typing import Optional, Dict, Any
from enum import Enum

from app.schemas.trend_models import TrendResult


class TrendType(str, Enum):
    """Trend type classifications."""
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    INTRADAY = "INTRADAY"
    SWING = "SWING"


class TrendStrengthLevel(str, Enum):
    """Trend strength classifications."""
    STRONG_BULLISH = "STRONG_BULLISH"
    WEAK_BULLISH = "WEAK_BULLISH"
    NEUTRAL = "NEUTRAL"
    WEAK_BEARISH = "WEAK_BEARISH"
    STRONG_BEARISH = "STRONG_BEARISH"


class TrendDetectorResult:
    """Trend detection result."""
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        primary_trend: TrendStrengthLevel,
        secondary_trend: TrendStrengthLevel,
        intraday_trend: TrendStrengthLevel,
        swing_trend: TrendStrengthLevel,
        trend_strength: float
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.primary_trend = primary_trend
        self.secondary_trend = secondary_trend
        self.intraday_trend = intraday_trend
        self.swing_trend = swing_trend
        self.trend_strength = trend_strength
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'primaryTrend': self.primary_trend.value,
            'secondaryTrend': self.secondary_trend.value,
            'intradayTrend': self.intraday_trend.value,
            'swingTrend': self.swing_trend.value,
            'trendStrength': self.trend_strength
        }


class TrendDetector:
    """
    Trend Detector - Multi-timeframe trend analysis.
    
    Determines:
    - Primary Trend (D1/H4)
    - Secondary Trend (H1/M30)
    - Intraday Trend (M15/M5)
    - Swing Trend (overall)
    - Trend Strength (0-100)
    """
    
    def __init__(self):
        """Initialize the trend detector."""
        self._detection_count = 0
    
    def detect_trends(
        self,
        symbol: str,
        timeframe: str,
        trend_result: Optional[TrendResult]
    ) -> TrendDetectorResult:
        """
        Detect multi-level trends.
        
        Args:
            symbol: Instrument symbol
            timeframe: Current timeframe
            trend_result: Trend analysis result
            
        Returns:
            TrendDetectorResult with all trend classifications
        """
        self._detection_count += 1
        
        if not trend_result:
            return TrendDetectorResult(
                symbol=symbol,
                timeframe=timeframe,
                primary_trend=TrendStrengthLevel.NEUTRAL,
                secondary_trend=TrendStrengthLevel.NEUTRAL,
                intraday_trend=TrendStrengthLevel.NEUTRAL,
                swing_trend=TrendStrengthLevel.NEUTRAL,
                trend_strength=0.0
            )
        
        primary_trend = self._classify_trend(trend_result, TrendType.PRIMARY)
        secondary_trend = self._classify_trend(trend_result, TrendType.SECONDARY)
        intraday_trend = self._classify_trend(trend_result, TrendType.INTRADAY)
        swing_trend = self._classify_trend(trend_result, TrendType.SWING)
        
        trend_strength = trend_result.confidence
        
        return TrendDetectorResult(
            symbol=symbol,
            timeframe=timeframe,
            primary_trend=primary_trend,
            secondary_trend=secondary_trend,
            intraday_trend=intraday_trend,
            swing_trend=swing_trend,
            trend_strength=trend_strength
        )
    
    def _classify_trend(
        self,
        trend_result: TrendResult,
        trend_type: TrendType
    ) -> TrendStrengthLevel:
        """Classify trend based on direction and strength."""
        direction = trend_result.direction.value
        strength = trend_result.strength.value
        
        if direction == "BULLISH":
            if strength in ["STRONG", "VERY_STRONG"]:
                return TrendStrengthLevel.STRONG_BULLISH
            else:
                return TrendStrengthLevel.WEAK_BULLISH
        elif direction == "BEARISH":
            if strength in ["STRONG", "VERY_STRONG"]:
                return TrendStrengthLevel.STRONG_BEARISH
            else:
                return TrendStrengthLevel.WEAK_BEARISH
        else:
            return TrendStrengthLevel.NEUTRAL
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return {
            'detectionCount': self._detection_count
        }
