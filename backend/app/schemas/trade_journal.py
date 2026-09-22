from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel

class TradeJournalBase(BaseModel):
    signalId: Optional[int] = None
    strategyId: Optional[str] = None
    symbol: str
    direction: str
    entryPrice: float
    exitPrice: Optional[float] = None
    stopLoss: float
    takeProfit: float
    timeframe: str
    marketSession: str
    tradeDate: datetime
    closeDate: Optional[datetime] = None
    status: str = "OPEN"
    result: str = "OPEN"
    profitLoss: float = 0.0
    riskReward: float = 0.0
    confidence: int = 0
    reasonForEntry: str
    reasonForExit: Optional[str] = None
    lessonLearned: Optional[str] = None
    notes: Optional[str] = None
    # V10 Performance & Validation Fields
    fillTime: Optional[datetime] = None
    fillPrice: Optional[float] = None
    realizedRMultiple: Optional[float] = None
    peakPrice: Optional[float] = None
    troughPrice: Optional[float] = None
    mfeR: Optional[float] = None
    maeR: Optional[float] = None
    strategyVersion: Optional[str] = None
    adaptiveRuleVersion: Optional[str] = None
    adaptiveStopMultiplier: Optional[float] = None
    spreadAtEntry: Optional[float] = None
    atrAtEntry: Optional[float] = None
    initialMonetaryRisk: Optional[Decimal] = None
    executionMode: Optional[str] = None

class TradeJournalCreate(TradeJournalBase):
    """Payload for a new entry. ``id`` and timestamps are assigned by the server."""

class TradeJournalUpdate(BaseModel):
    """Partial update — typically used to close an open trade."""
    exitPrice: Optional[float] = None
    closeDate: Optional[datetime] = None
    status: Optional[str] = None
    result: Optional[str] = None
    profitLoss: Optional[float] = None
    riskReward: Optional[float] = None
    confidence: Optional[int] = None
    reasonForExit: Optional[str] = None
    lessonLearned: Optional[str] = None
    notes: Optional[str] = None
    # V10 Performance & Validation Fields
    fillTime: Optional[datetime] = None
    fillPrice: Optional[float] = None
    realizedRMultiple: Optional[float] = None
    peakPrice: Optional[float] = None
    troughPrice: Optional[float] = None
    mfeR: Optional[float] = None
    maeR: Optional[float] = None
    strategyVersion: Optional[str] = None
    adaptiveRuleVersion: Optional[str] = None
    adaptiveStopMultiplier: Optional[float] = None
    spreadAtEntry: Optional[float] = None
    atrAtEntry: Optional[float] = None
    initialMonetaryRisk: Optional[Decimal] = None
    executionMode: Optional[str] = None


class TradeJournalItem(TradeJournalBase):
    id: int
    createdAt: datetime
    updatedAt: datetime

class TradeJournalListResponse(BaseModel):
    trades: List[TradeJournalItem]
    lastUpdated: datetime
