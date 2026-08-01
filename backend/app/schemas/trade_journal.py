from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

class TradeJournalItem(BaseModel):
    id: int
    signalId: Optional[int] = None
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
    status: str
    result: str
    profitLoss: float
    riskReward: float
    confidence: int
    reasonForEntry: str
    reasonForExit: Optional[str] = None
    lessonLearned: Optional[str] = None
    notes: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime

class TradeJournalListResponse(BaseModel):
    trades: List[TradeJournalItem]
    lastUpdated: datetime
