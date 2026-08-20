from typing import Optional, List
from datetime import datetime
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

class TradeJournalItem(TradeJournalBase):
    id: int
    createdAt: datetime
    updatedAt: datetime

class TradeJournalListResponse(BaseModel):
    trades: List[TradeJournalItem]
    lastUpdated: datetime
