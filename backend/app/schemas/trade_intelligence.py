from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class PairPerformance(BaseModel):
    symbol: str
    totalTrades: int
    winRate: float
    profitLoss: float

class SessionPerformance(BaseModel):
    session: str
    totalTrades: int
    winRate: float
    profitLoss: float

class TimeframePerformance(BaseModel):
    timeframe: str
    totalTrades: int
    winRate: float
    profitLoss: float

class TradeIntelligenceResponse(BaseModel):
    totalTrades: int
    winningTrades: int
    losingTrades: int
    breakEvenTrades: int
    openTrades: int
    winRate: float
    winningDays: int
    losingDays: int
    currentWinStreak: int
    currentLossStreak: int
    bestPair: str
    worstPair: str
    bestSession: str
    bestTimeframe: str
    averageRiskReward: float
    averageConfidence: float
    mostCommonLossReason: str
    lastUpdated: datetime
    pairPerformance: List[PairPerformance]
    sessionPerformance: List[SessionPerformance]
    timeframePerformance: List[TimeframePerformance]
