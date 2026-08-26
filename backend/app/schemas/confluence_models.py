"""
Falcon Confluence Models
Schema models for signal confluence and trading decisions.
"""
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class MultiTimeframeRecommendation(str, Enum):
    """Multi-timeframe confluence recommendation."""
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"
    NO_TRADE = "NO_TRADE"


class TimeframeAnalysis(BaseModel):
    """
    Analysis result for a single timeframe.
    
    Contains trend, structure, support/resistance, and indicator data
    for a specific timeframe.
    
    Attributes:
        timeframe: Timeframe identifier (e.g., H4, H1, M15, M5)
        trendDirection: Trend direction (BULLISH, BEARISH, SIDEWAYS, UNKNOWN)
        trendStrength: Trend strength (VERY_WEAK to VERY_STRONG)
        confidence: Analysis confidence score (0-100)
        marketStructure: Market structure summary
        supportLevel: Nearest support level
        resistanceLevel: Nearest resistance level
        currentPrice: Current price
        distanceToSupport: Distance to support in price units
        distanceToResistance: Distance to resistance in price units
        emaAlignment: EMA alignment status
        analysisSummary: Brief analysis summary
    """
    timeframe: str = Field(..., description="Timeframe identifier")
    trendDirection: str = Field(..., description="Trend direction")
    trendStrength: str = Field(..., description="Trend strength")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Confidence score (0-100)")
    marketStructure: str = Field(..., description="Market structure summary")
    supportLevel: Optional[float] = Field(None, description="Nearest support level")
    resistanceLevel: Optional[float] = Field(None, description="Nearest resistance level")
    currentPrice: Optional[float] = Field(None, description="Current price")
    distanceToSupport: Optional[float] = Field(None, description="Distance to support")
    distanceToResistance: Optional[float] = Field(None, description="Distance to resistance")
    emaAlignment: str = Field(..., description="EMA alignment status")
    analysisSummary: str = Field(..., description="Analysis summary")
    
    class Config:
        json_schema_extra = {
            "example": {
                "timeframe": "H4",
                "trendDirection": "BULLISH",
                "trendStrength": "STRONG",
                "confidence": 92.0,
                "marketStructure": "Bullish BOS",
                "supportLevel": 2030.0,
                "resistanceLevel": 2060.0,
                "currentPrice": 2045.0,
                "distanceToSupport": 15.0,
                "distanceToResistance": 15.0,
                "emaAlignment": "Bullish",
                "analysisSummary": "Strong bullish trend with bullish structure"
            }
        }


class SignalDirection(str, Enum):
    """Trading signal direction."""
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


class SignalQuality(str, Enum):
    """Signal quality classification."""
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class ConfirmationStatus(str, Enum):
    """Confirmation status for factors."""
    CONFIRMED = "CONFIRMED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"


class ConfluenceFactor(BaseModel):
    """
    Individual confluence factor.
    
    Represents a single factor in the confluence analysis.
    
    Attributes:
        name: Factor name (e.g., "Trend", "Market Structure", "Indicators")
        status: Confirmation status
        score: Factor score (0-100)
        weight: Factor weight in overall confidence (0-1)
        reason: Explanation for the factor's status
    """
    name: str = Field(..., description="Factor name")
    status: ConfirmationStatus = Field(..., description="Confirmation status")
    score: float = Field(..., ge=0.0, le=100.0, description="Factor score (0-100)")
    weight: float = Field(..., ge=0.0, le=1.0, description="Factor weight (0-1)")
    reason: str = Field(..., description="Explanation for status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Trend",
                "status": "CONFIRMED",
                "score": 85.0,
                "weight": 0.25,
                "reason": "Strong bullish trend with EMA alignment"
            }
        }


class TradeLevels(BaseModel):
    """
    Trade level calculations.
    
    Contains entry, stop loss, and take profit levels with risk/reward ratio.
    
    Attributes:
        entry: Entry price
        stopLoss: Stop loss price
        takeProfit1: First take profit target
        takeProfit2: Second take profit target
        takeProfit3: Third take profit target
        riskReward: Risk/reward ratio
    """
    entry: Optional[float] = Field(None, description="Entry price")
    stopLoss: Optional[float] = Field(None, description="Stop loss price")
    takeProfit1: Optional[float] = Field(None, description="First take profit")
    takeProfit2: Optional[float] = Field(None, description="Second take profit")
    takeProfit3: Optional[float] = Field(None, description="Third take profit")
    riskReward: Optional[float] = Field(None, ge=0.0, description="Risk/reward ratio")
    
    class Config:
        json_schema_extra = {
            "example": {
                "entry": 2045.0,
                "stopLoss": 2035.0,
                "takeProfit1": 2060.0,
                "takeProfit2": 2075.0,
                "takeProfit3": 2090.0,
                "riskReward": 2.0
            }
        }


class SignalDecision(BaseModel):
    """
    Complete signal decision from confluence analysis.
    
    Contains the final trading decision with all supporting factors,
    trade levels, and explanations.
    
    Attributes:
        symbol: Instrument symbol
        timeframe: Candle timeframe
        direction: Signal direction (BUY, SELL, WAIT)
        quality: Signal quality
        confidence: Overall confidence score (0-100)
        tradeLevels: Trade level calculations
        trend: Trend analysis summary
        marketStructure: Market structure summary
        indicatorSummary: Indicator summary
        factors: List of confluence factors
        reasons: List of positive reasons
        warnings: List of warnings/rejections
        timestamp: Decision timestamp
    """
    symbol: str = Field(..., description="Instrument symbol")
    timeframe: str = Field(..., description="Candle timeframe")
    direction: SignalDirection = Field(..., description="Signal direction")
    quality: SignalQuality = Field(..., description="Signal quality")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Overall confidence (0-100)")
    tradeLevels: TradeLevels = Field(..., description="Trade level calculations")
    trend: str = Field(..., description="Trend analysis summary")
    marketStructure: str = Field(..., description="Market structure summary")
    indicatorSummary: str = Field(..., description="Indicator summary")
    factors: List[ConfluenceFactor] = Field(default_factory=list, description="Confluence factors")
    reasons: List[str] = Field(default_factory=list, description="Positive reasons")
    warnings: List[str] = Field(default_factory=list, description="Warnings/rejections")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Decision timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "direction": "BUY",
                "quality": "VERY_HIGH",
                "confidence": 92.0,
                "tradeLevels": {
                    "entry": 2045.0,
                    "stopLoss": 2035.0,
                    "takeProfit1": 2060.0,
                    "takeProfit2": 2075.0,
                    "takeProfit3": 2090.0,
                    "riskReward": 2.0
                },
                "trend": "Strong bullish trend with EMA alignment",
                "marketStructure": "Bullish BOS in demand zone",
                "indicatorSummary": "Bullish indicators across the board",
                "factors": [],
                "reasons": [
                    "✓ Bullish Trend",
                    "✓ Bullish BOS",
                    "✓ Demand Zone",
                    "✓ EMA Alignment",
                    "✓ RSI Recovery",
                    "✓ MACD Bullish",
                    "✓ ATR Healthy",
                    "✓ No High Impact News",
                    "✓ RR 2.8"
                ],
                "warnings": [],
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }


class MultiTimeframeConfluenceResult(BaseModel):
    """
    Multi-timeframe confluence analysis result.
    
    Contains analysis across multiple timeframes with overall confluence score
    and trading recommendation.
    
    Attributes:
        symbol: Instrument symbol
        analyses: List of timeframe analyses
        alignedTimeframes: List of timeframes aligned with recommendation
        conflictingTimeframes: List of timeframes conflicting with recommendation
        overallConfluenceScore: Overall confluence score (0-100)
        recommendation: Trading recommendation (BUY, SELL, WAIT, NO_TRADE)
        recommendationReason: Explanation for recommendation

        generatedAt: Timestamp when analysis was generated
    """
    symbol: str = Field(..., description="Instrument symbol")
    analyses: List[TimeframeAnalysis] = Field(default_factory=list, description="Timeframe analyses")
    alignedTimeframes: List[str] = Field(default_factory=list, description="Aligned timeframes")
    conflictingTimeframes: List[str] = Field(default_factory=list, description="Conflicting timeframes")
    overallConfluenceScore: float = Field(..., ge=0.0, le=100.0, description="Overall confluence score (0-100)")
    recommendation: MultiTimeframeRecommendation = Field(..., description="Trading recommendation")
    recommendationReason: str = Field(..., description="Recommendation explanation")
    generatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Analysis timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "XAUUSD",
                "analyses": [
                    {
                        "timeframe": "H4",
                        "trendDirection": "BULLISH",
                        "trendStrength": "STRONG",
                        "confidence": 92.0,
                        "marketStructure": "Bullish BOS",
                        "supportLevel": 2030.0,
                        "resistanceLevel": 2060.0,
                        "currentPrice": 2045.0,
                        "distanceToSupport": 15.0,
                        "distanceToResistance": 15.0,
                        "emaAlignment": "Bullish",
                        "analysisSummary": "Strong bullish trend with bullish structure"
                    }
                ],
                "alignedTimeframes": ["H4", "H1", "M15", "M5"],
                "conflictingTimeframes": [],
                "overallConfluenceScore": 89.0,
                "recommendation": "BUY",
                "recommendationReason": "Strong bullish alignment across all monitored timeframes.",
                "generatedAt": "2024-01-01T12:00:00Z"
            }
        }


class MultiTimeframeConfluenceStatistics(BaseModel):
    """
    Multi-timeframe confluence engine runtime statistics.
    
    Provides performance metrics for the multi-timeframe confluence engine.
    
    Attributes:
        calculations: Total number of confluence calculations performed
        cacheHits: Number of cache hits
        cacheMisses: Number of cache misses
        averageExecutionTime: Average execution time in milliseconds
        fastestCalculation: Fastest calculation time in milliseconds
        slowestCalculation: Slowest calculation time in milliseconds
        lastCalculation: Timestamp of last calculation
    """
    calculations: int = Field(0, description="Total calculations performed")
    cacheHits: int = Field(0, description="Number of cache hits")
    cacheMisses: int = Field(0, description="Number of cache misses")
    averageExecutionTime: float = Field(0.0, description="Average execution time (ms)")
    fastestCalculation: Optional[float] = Field(None, description="Fastest calculation time (ms)")
    slowestCalculation: Optional[float] = Field(None, description="Slowest calculation time (ms)")
    lastCalculation: Optional[datetime] = Field(None, description="Last calculation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "calculations": 100,
                "cacheHits": 75,
                "cacheMisses": 25,
                "averageExecutionTime": 3.2,
                "fastestCalculation": 2.5,
                "slowestCalculation": 4.8,
                "lastCalculation": "2024-01-01T12:00:00Z"
            }
        }


class ConfluenceStatistics(BaseModel):
    """
    Confluence engine runtime statistics.
    
    Provides performance metrics for the confluence engine.
    
    Attributes:
        calculations: Total number of confluence calculations performed
        average_execution_time: Average execution time in milliseconds
        buy_signals: Number of BUY signals generated
        sell_signals: Number of SELL signals generated
        wait_signals: Number of WAIT signals generated
        cache_hits: Number of cache hits
        cache_misses: Number of cache misses
        average_confidence: Average confidence score
        last_calculation: Timestamp of last calculation
    """
    calculations: int = Field(0, description="Total calculations performed")
    average_execution_time: float = Field(0.0, description="Average execution time (ms)")
    buy_signals: int = Field(0, description="Number of BUY signals")
    sell_signals: int = Field(0, description="Number of SELL signals")
    wait_signals: int = Field(0, description="Number of WAIT signals")
    cache_hits: int = Field(0, description="Number of cache hits")
    cache_misses: int = Field(0, description="Number of cache misses")
    average_confidence: float = Field(0.0, description="Average confidence score")
    last_calculation: Optional[datetime] = Field(None, description="Last calculation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "calculations": 200,
                "average_execution_time": 3.5,
                "buy_signals": 80,
                "sell_signals": 60,
                "wait_signals": 60,
                "cache_hits": 150,
                "cache_misses": 50,
                "average_confidence": 75.0,
                "last_calculation": "2024-01-01T12:00:00Z"
            }
        }
