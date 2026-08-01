from pydantic import BaseModel
from datetime import datetime
from typing import List

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

class SignalListResponse(BaseModel):
    signals: List[SignalItem]
    lastUpdated: datetime
    dataAgeSeconds: int
