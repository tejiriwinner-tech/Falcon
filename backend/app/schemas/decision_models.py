"""
Falcon AI Decision Models
Schema models for AI decision engine.
"""
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field


class DecisionType(str, Enum):
    """AI decision type."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    WAIT = "WAIT"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    NO_TRADE = "NO_TRADE"


class AIDecisionResult(BaseModel):
    """
    AI decision result.
    
    Contains the final AI trading decision with confidence, reasoning,
    and all supporting analytical data.
    
    Attributes:
        symbol: Instrument symbol
        timeframe: Timeframe analyzed
        decision: Final AI decision
        confidence: AI confidence (0-100)
        signalScore: Signal quality score from Phase 5.6
        trendDirection: Trend direction
        trendStrength: Trend strength
        structureBias: Market structure bias
        liquidityBias: Liquidity bias
        confluenceScore: Multi-timeframe confluence score
        riskRating: Risk rating
        reasoning: List of reasoning statements explaining the decision
        warnings: List of warnings about the decision
        generatedAt: Timestamp when decision was generated
    """
    symbol: str = Field(..., description="Instrument symbol")
    timeframe: str = Field(..., description="Timeframe analyzed")
    decision: DecisionType = Field(..., description="Final AI decision")
    confidence: float = Field(..., ge=0.0, le=100.0, description="AI confidence (0-100)")
    signalScore: Optional[float] = Field(None, ge=0.0, le=100.0, description="Signal quality score")
    trendDirection: Optional[str] = Field(None, description="Trend direction")
    trendStrength: Optional[str] = Field(None, description="Trend strength")
    structureBias: Optional[str] = Field(None, description="Market structure bias")
    liquidityBias: Optional[str] = Field(None, description="Liquidity bias")
    confluenceScore: Optional[float] = Field(None, ge=0.0, le=100.0, description="MT confluence score")
    riskRating: Optional[str] = Field(None, description="Risk rating")
    reasoning: List[str] = Field(default_factory=list, description="Decision reasoning")
    warnings: List[str] = Field(default_factory=list, description="Decision warnings")
    generatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Decision timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "decision": "BUY",
                "confidence": 94.0,
                "signalScore": 93.0,
                "trendDirection": "BULLISH",
                "trendStrength": "STRONG",
                "structureBias": "BULLISH",
                "liquidityBias": "BULLISH",
                "confluenceScore": 91.0,
                "riskRating": "LOW",
                "reasoning": [
                    "Bullish trend confirmed",
                    "Bullish BOS detected",
                    "Liquidity sweep completed",
                    "Momentum supports continuation",
                    "Higher timeframes aligned"
                ],
                "warnings": [],
                "generatedAt": "2024-01-01T12:00:00Z"
            }
        }


class AIDecisionStatistics(BaseModel):
    """
    AI decision engine runtime statistics.
    
    Provides performance metrics for the AI decision engine.
    
    Attributes:
        totalDecisions: Total number of decisions made
        buyCount: Number of BUY decisions
        sellCount: Number of SELL decisions
        waitCount: Number of WAIT decisions
        averageConfidence: Average confidence across all decisions
        averageExecutionTime: Average execution time in milliseconds
        cacheHits: Number of cache hits
        cacheMisses: Number of cache misses
        highestConfidence: Highest confidence recorded
        lowestConfidence: Lowest confidence recorded
    """
    totalDecisions: int = Field(0, description="Total decisions made")
    buyCount: int = Field(0, description="Number of BUY decisions")
    sellCount: int = Field(0, description="Number of SELL decisions")
    waitCount: int = Field(0, description="Number of WAIT decisions")
    averageConfidence: float = Field(0.0, description="Average confidence")
    averageExecutionTime: float = Field(0.0, description="Average execution time (ms)")
    cacheHits: int = Field(0, description="Number of cache hits")
    cacheMisses: int = Field(0, description="Number of cache misses")
    highestConfidence: Optional[float] = Field(None, description="Highest confidence recorded")
    lowestConfidence: Optional[float] = Field(None, description="Lowest confidence recorded")
    
    class Config:
        json_schema_extra = {
            "example": {
                "totalDecisions": 100,
                "buyCount": 35,
                "sellCount": 30,
                "waitCount": 35,
                "averageConfidence": 78.5,
                "averageExecutionTime": 1.5,
                "cacheHits": 75,
                "cacheMisses": 25,
                "highestConfidence": 97.0,
                "lowestConfidence": 43.0
            }
        }
