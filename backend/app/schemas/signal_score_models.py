"""
Falcon Signal Scoring Models
Schema models for signal quality scoring and evaluation.
"""
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field


class SignalQuality(str, Enum):
    """Signal quality classification."""
    EXCELLENT = "EXCELLENT"
    VERY_GOOD = "VERY_GOOD"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    INVALID = "INVALID"


class SignalRecommendation(str, Enum):
    """Signal recommendation."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    WAIT = "WAIT"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    NO_SIGNAL = "NO_SIGNAL"


class RiskRating(str, Enum):
    """Risk rating."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SignalComponentScore(BaseModel):
    """
    Individual signal component score.
    
    Contains the score for a single analytical component (trend, structure, etc.)
    with its weight, raw score, weighted score, and explanation.
    
    Attributes:
        componentName: Name of the component (e.g., Trend, Structure, Momentum)
        weight: Maximum possible points for this component
        rawScore: Actual score achieved (0 to weight)
        weightedScore: Normalized score (0 to 100)
        explanation: Human-readable explanation of the score
    """
    componentName: str = Field(..., description="Component name")
    weight: float = Field(..., ge=0.0, description="Maximum points for this component")
    rawScore: float = Field(..., ge=0.0, description="Actual score achieved")
    weightedScore: float = Field(..., ge=0.0, le=100.0, description="Normalized score (0-100)")
    explanation: str = Field(..., description="Score explanation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "componentName": "Trend",
                "weight": 25.0,
                "rawScore": 24.0,
                "weightedScore": 96.0,
                "explanation": "Strong bullish trend with 90% confidence."
            }
        }


class SignalScoreResult(BaseModel):
    """
    Complete signal score result.
    
    Contains the overall signal quality score with all component scores,
    recommendation, risk rating, and analysis summary.
    
    Attributes:
        symbol: Instrument symbol
        timeframe: Timeframe analyzed
        overallScore: Overall signal quality score (0-100)
        quality: Signal quality classification
        recommendation: Trading recommendation
        confidence: Confidence in the recommendation (0-100)
        componentScores: List of individual component scores
        riskRating: Risk rating (LOW, MEDIUM, HIGH)
        analysisSummary: Brief analysis summary
        generatedAt: Timestamp when analysis was generated
    """
    symbol: str = Field(..., description="Instrument symbol")
    timeframe: str = Field(..., description="Timeframe analyzed")
    overallScore: float = Field(..., ge=0.0, le=100.0, description="Overall signal quality score (0-100)")
    quality: SignalQuality = Field(..., description="Signal quality classification")
    recommendation: SignalRecommendation = Field(..., description="Trading recommendation")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Confidence in recommendation (0-100)")
    componentScores: List[SignalComponentScore] = Field(default_factory=list, description="Component scores")
    riskRating: RiskRating = Field(..., description="Risk rating")
    analysisSummary: str = Field(..., description="Analysis summary")
    generatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Analysis timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "overallScore": 92.0,
                "quality": "VERY_GOOD",
                "recommendation": "BUY",
                "confidence": 91.0,
                "componentScores": [
                    {
                        "componentName": "Trend",
                        "weight": 25.0,
                        "rawScore": 24.0,
                        "weightedScore": 96.0,
                        "explanation": "Strong bullish trend with 90% confidence."
                    }
                ],
                "riskRating": "LOW",
                "analysisSummary": "High-quality bullish setup confirmed across multiple analytical components.",
                "generatedAt": "2024-01-01T12:00:00Z"
            }
        }


class SignalScoreStatistics(BaseModel):
    """
    Signal scoring engine runtime statistics.
    
    Provides performance metrics for the signal scoring engine.
    
    Attributes:
        calculations: Total number of signal score calculations performed
        averageExecutionTime: Average execution time in milliseconds
        cacheHits: Number of cache hits
        cacheMisses: Number of cache misses
        highestScore: Highest score recorded
        lowestScore: Lowest score recorded
        lastCalculation: Timestamp of last calculation
    """
    calculations: int = Field(0, description="Total calculations performed")
    averageExecutionTime: float = Field(0.0, description="Average execution time (ms)")
    cacheHits: int = Field(0, description="Number of cache hits")
    cacheMisses: int = Field(0, description="Number of cache misses")
    highestScore: Optional[float] = Field(None, description="Highest score recorded")
    lowestScore: Optional[float] = Field(None, description="Lowest score recorded")
    lastCalculation: Optional[datetime] = Field(None, description="Last calculation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "calculations": 100,
                "averageExecutionTime": 3.5,
                "cacheHits": 75,
                "cacheMisses": 25,
                "highestScore": 98.0,
                "lowestScore": 45.0,
                "lastCalculation": "2024-01-01T12:00:00Z"
            }
        }
