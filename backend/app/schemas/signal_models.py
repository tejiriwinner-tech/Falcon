"""
Falcon Signal Generator Models
Schema models for intelligent signal generation.
"""
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SignalType(str, Enum):
    """Signal type."""
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"
    NONE = "NONE"


class SignalStatus(str, Enum):
    """Signal status."""
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class TradeManagement(BaseModel):
    """
    Trade management recommendations.
    
    Provides recommendations for managing the trade after entry.
    This does not execute anything - it simply recommends how to manage the trade.
    
    Attributes:
        moveStopToBreakevenAt: When to move stop loss to breakeven (e.g., "TP1")
        partialCloseAtTP1: Percentage to close at TP1 (e.g., 50)
        partialCloseAtTP2: Percentage to close at TP2 (e.g., 30)
        leaveRunner: Percentage to leave as runner (e.g., 20)
    """
    moveStopToBreakevenAt: Optional[str] = Field(None, description="When to move SL to breakeven")
    partialCloseAtTP1: Optional[int] = Field(None, ge=0, le=100, description="Percentage to close at TP1")
    partialCloseAtTP2: Optional[int] = Field(None, ge=0, le=100, description="Percentage to close at TP2")
    leaveRunner: Optional[int] = Field(None, ge=0, le=100, description="Percentage to leave as runner")
    
    class Config:
        json_schema_extra = {
            "example": {
                "moveStopToBreakevenAt": "TP1",
                "partialCloseAtTP1": 50,
                "partialCloseAtTP2": 30,
                "leaveRunner": 20
            }
        }


class TradeSetup(BaseModel):
    """
    Complete trade setup.
    
    Contains all details for a professional trading recommendation including
    entry, stop loss, take profits, risk/reward, and trade management.
    
    Attributes:
        signalId: Unique signal identifier
        symbol: Instrument symbol
        timeframe: Timeframe analyzed
        signalType: Signal type (BUY/SELL/WAIT/NONE)
        entryPrice: Recommended entry price
        stopLoss: Stop loss price
        takeProfit1: First take profit target
        takeProfit2: Second take profit target
        takeProfit3: Third take profit target
        riskRewardRatio: Risk/reward ratio
        confidence: Signal confidence (0-100)
        quality: Signal quality classification
        expectedHoldTime: Expected hold time
        status: Signal status
        decision: AI decision that led to this signal
        reasoning: List of reasoning statements
        warnings: List of warnings
        tradeManagement: Trade management recommendations
        generatedAt: Timestamp when signal was generated
        expiresAt: Timestamp when signal expires
    """
    signalId: str = Field(..., description="Unique signal identifier")
    symbol: str = Field(..., description="Instrument symbol")
    timeframe: str = Field(..., description="Timeframe analyzed")
    signalType: SignalType = Field(..., description="Signal type")
    entryPrice: float = Field(..., description="Recommended entry price")
    stopLoss: float = Field(..., description="Stop loss price")
    takeProfit1: Optional[float] = Field(None, description="First take profit target")
    takeProfit2: Optional[float] = Field(None, description="Second take profit target")
    takeProfit3: Optional[float] = Field(None, description="Third take profit target")
    riskRewardRatio: float = Field(..., ge=0.0, description="Risk/reward ratio")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Signal confidence (0-100)")
    quality: str = Field(..., description="Signal quality classification")
    expectedHoldTime: str = Field(..., description="Expected hold time")
    status: SignalStatus = Field(..., description="Signal status")
    decision: str = Field(..., description="AI decision")
    reasoning: List[str] = Field(default_factory=list, description="Signal reasoning")
    warnings: List[str] = Field(default_factory=list, description="Signal warnings")
    tradeManagement: Optional[TradeManagement] = Field(None, description="Trade management recommendations")
    generatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Signal timestamp")
    expiresAt: Optional[datetime] = Field(None, description="Signal expiration timestamp")
    aiSnapshot: Optional[Dict[str, Any]] = Field(None, description="Complete AI analysis snapshot")
    
    class Config:
        json_schema_extra = {
            "example": {
                "signalId": "SIG-20260802-000001",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "signalType": "BUY",
                "entryPrice": 3387.45,
                "stopLoss": 3379.20,
                "takeProfit1": 3397.10,
                "takeProfit2": 3406.50,
                "takeProfit3": 3418.00,
                "riskRewardRatio": 3.1,
                "confidence": 94.0,
                "quality": "EXCELLENT",
                "expectedHoldTime": "4 Hours",
                "status": "ACTIVE",
                "decision": "BUY",
                "reasoning": [
                    "Bullish trend",
                    "Bullish BOS",
                    "Liquidity sweep confirmed",
                    "Strong confluence",
                    "Excellent signal quality"
                ],
                "warnings": [],
                "tradeManagement": {
                    "moveStopToBreakevenAt": "TP1",
                    "partialCloseAtTP1": 50,
                    "partialCloseAtTP2": 30,
                    "leaveRunner": 20
                },
                "generatedAt": "2024-01-01T12:00:00Z",
                "expiresAt": "2024-01-01T20:00:00Z"
            }
        }


class SignalStatistics(BaseModel):
    """
    Signal generator runtime statistics.
    
    Provides performance metrics for the signal generator.
    
    Attributes:
        signalsGenerated: Total number of signals generated
        buySignals: Number of BUY signals
        sellSignals: Number of SELL signals
        waitSignals: Number of WAIT signals
        expiredSignals: Number of expired signals
        averageConfidence: Average confidence across all signals
        averageRR: Average risk/reward ratio
        averageGenerationTime: Average generation time in milliseconds
        cacheHits: Number of cache hits
        cacheMisses: Number of cache misses
    """
    signalsGenerated: int = Field(0, description="Total signals generated")
    buySignals: int = Field(0, description="Number of BUY signals")
    sellSignals: int = Field(0, description="Number of SELL signals")
    waitSignals: int = Field(0, description="Number of WAIT signals")
    expiredSignals: int = Field(0, description="Number of expired signals")
    averageConfidence: float = Field(0.0, description="Average confidence")
    averageRR: float = Field(0.0, description="Average risk/reward ratio")
    averageGenerationTime: float = Field(0.0, description="Average generation time (ms)")
    cacheHits: int = Field(0, description="Number of cache hits")
    cacheMisses: int = Field(0, description="Number of cache misses")
    
    class Config:
        json_schema_extra = {
            "example": {
                "signalsGenerated": 100,
                "buySignals": 45,
                "sellSignals": 40,
                "waitSignals": 15,
                "expiredSignals": 30,
                "averageConfidence": 82.5,
                "averageRR": 2.8,
                "averageGenerationTime": 2.5,
                "cacheHits": 75,
                "cacheMisses": 25
            }
        }
