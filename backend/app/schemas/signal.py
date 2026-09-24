from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from app.schemas.research_promotion import ResearchSignalContext

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
    adaptiveRuleVersion: Optional[str] = None
    adaptiveStopMultiplier: Optional[float] = None
    researchContext: Optional[ResearchSignalContext] = None
    dataAgeSeconds: int
    triggerCondition: Optional[str] = None
    validUntil: Optional[datetime] = None
    setupPattern: Optional[str] = None
    riskReward: Optional[float] = None
    isPinned: bool = False
    breakevenTrigger: Optional[float] = None
    breakevenPrice: Optional[float] = None
    isBreakeven: bool = False

class SignalListResponse(BaseModel):
    signals: List[SignalItem]
    lastUpdated: datetime
    dataAgeSeconds: int
