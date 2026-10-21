from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class StrategyType(str, Enum):
    TREND_CONTINUATION = "TREND_CONTINUATION"
    BREAKOUT = "BREAKOUT"
    PULLBACK = "PULLBACK"
    SUPPORT_RESISTANCE = "SUPPORT_RESISTANCE"
    SESSION_BREAKOUT = "SESSION_BREAKOUT"
    VOLATILITY_EXHAUSTION = "VOLATILITY_EXHAUSTION"
    SCALPING = "SCALPING"
    SWING = "SWING"
    MOMENTUM = "MOMENTUM"
    PRICE_ACTION = "PRICE_ACTION"
    MEAN_REVERSION = "MEAN_REVERSION"
    SWING_STRUCTURE = "SWING_STRUCTURE"
    ALGORITHMIC = "ALGORITHMIC"
    EVENT_DRIVEN = "EVENT_DRIVEN"

class StrategyCategory(str, Enum):
    INTRADAY = "INTRADAY"
    SCALPING = "SCALPING"
    SWING = "SWING"
    POSITION = "POSITION"

class StrategyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    TESTING = "TESTING"
    PAUSED = "PAUSED"
    DEPRECATED = "DEPRECATED"
    INCUBATION = "INCUBATION"

class StrategyHealth(str, Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    WATCHLIST = "WATCHLIST"
    POOR = "POOR"

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class StrategyPerformance(BaseModel):
    totalTrades: int
    wins: int
    losses: int
    breakeven: int
    winRate: float
    averageRiskReward: float
    averageConfidence: float
    totalProfitLoss: float

class StrategyScore(BaseModel):
    historicalScore: int
    currentMarketScore: int
    overallScore: int
    historicalPerformance: int
    currentMarketFit: int
    currentNewsScore: int
    sessionMatch: int
    riskRating: RiskLevel

class MarketSnapshot(BaseModel):
    trend: str
    volatility: str
    liquidity: str
    news: str
    session: str
    spread: float
    atr: float
    rsi: float
    ema200: str
    adx: float

class StrategyValidationCheck(BaseModel):
    name: str
    passed: bool
    value: str

class StrategyValidation(BaseModel):
    score: int
    aiConfidence: int
    validationDurationSeconds: float
    failedChecks: List[str]
    checks: List[StrategyValidationCheck]
    marketSnapshot: MarketSnapshot

class StrategyItem(BaseModel):
    id: str
    name: str
    type: StrategyType
    category: StrategyCategory
    symbol: str
    description: str
    marketCondition: str
    bestSession: str
    bestTimeframe: str
    riskLevel: RiskLevel
    status: StrategyStatus
    health: StrategyHealth
    performance: StrategyPerformance
    strengths: List[str]
    weaknesses: List[str]
    entryChecklist: List[str]
    exitChecklist: List[str]
    idealVolatility: str
    avoidDuring: List[str]
    confirmationIndicators: List[str]
    successConditions: List[str]
    minimumConfidence: int
    minimumRiskReward: float
    preferredSessions: List[str]
    avoidConditions: List[str]
    requiredConfirmations: List[str]
    grade: str
    lastUsed: Optional[datetime] = None
    marketCompatibility: List[str]
    estimatedHoldingTime: str
    maxConsecutiveLosses: int
    createdAt: datetime
    updatedAt: datetime
    lastReviewedAt: datetime
    strategyVersion: str
    parentStrategyId: Optional[str] = None
    createdBy: str
    readyForExecution: bool
    reviewNotes: str
    dependencies: List[str]
    strategyScore: StrategyScore
    latestValidation: StrategyValidation

class StrategyListResponse(BaseModel):
    strategies: List[StrategyItem]
    lastUpdated: datetime
