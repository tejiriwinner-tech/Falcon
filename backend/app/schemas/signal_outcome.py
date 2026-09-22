from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class SignalOutcomeItem(BaseModel):
    signalId: int
    symbol: str
    direction: str
    strategyId: str
    strategyName: str
    entryPrice: float
    exitPrice: float
    stopLoss: float
    takeProfit: float
    result: str  # WIN, LOSS, OPEN
    profitLoss: float
    riskReward: float
    reasonForExit: Optional[str] = None
    lessonLearned: Optional[str] = None
    resolvedAt: datetime


class SignalResolutionSummary(BaseModel):
    totalChecked: int
    resolvedCount: int
    winsCount: int
    lossesCount: int
    breakevensCount: int = 0
    openCount: int
    outcomes: List[SignalOutcomeItem]
    timestamp: datetime
