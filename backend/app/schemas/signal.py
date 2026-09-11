from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class SignalItem(BaseModel):
    id: int
    symbol: str
    action: str
    entry: float
    takeProfit: float
    stopLoss: float
    confidence: int
    timeframe: str
    status: str
    analysis: str
    timestamp: datetime
    strategyId: str
    strategyName: str
    strategyVersion: str
    dataAgeSeconds: int
    triggerCondition: Optional[str] = None
    validUntil: Optional[datetime] = None
    setupPattern: Optional[str] = None
    riskReward: Optional[float] = None

class SignalListResponse(BaseModel):
    signals: List[SignalItem]
    lastUpdated: datetime
    dataAgeSeconds: int
