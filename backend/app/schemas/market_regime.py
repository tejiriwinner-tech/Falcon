from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class MarketRegime(str, Enum):
    TRENDING_BULLISH = "TRENDING_BULLISH"
    TRENDING_BEARISH = "TRENDING_BEARISH"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    BREAKOUT = "BREAKOUT"
    REVERSAL = "REVERSAL"
    UNCERTAIN = "UNCERTAIN"


class RegimeStrength(str, Enum):
    VERY_WEAK = "VERY_WEAK"
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"


class RegimeConfidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class RecommendationBias(str, Enum):
    BUY_BIAS = "BUY_BIAS"
    SELL_BIAS = "SELL_BIAS"
    NEUTRAL = "NEUTRAL"
    WAIT = "WAIT"


class RegimeEvidence(BaseModel):
    source: str
    description: str
    confidence: float


class RegimeFactor(BaseModel):
    name: str
    weight: float
    score: float
    description: str


class MarketRegimeSnapshot(BaseModel):
    trend: str
    session: str
    spread: float
    volatility: str
    marketSentiment: str
    fearGreed: str
    newsImpact: str


class MarketRegimeRecommendation(BaseModel):
    bias: RecommendationBias
    title: str
    description: str
    bestStrategies: List[str]
    avoidStrategies: List[str]


class MarketRegimeReport(BaseModel):
    id: str
    marketStateId: str
    regime: MarketRegime
    strength: RegimeStrength
    confidence: RegimeConfidence
    overallScore: float
    factors: List[RegimeFactor]
    recommendation: MarketRegimeRecommendation
    snapshot: MarketRegimeSnapshot

    # Metadata
    pipelineStage: str = "MARKET_REGIME"
    timelineOrder: int = 8
    engineVersion: str = "1.0.0"
    generatedBy: str = "Market Regime Intelligence Engine"
    generatedAt: datetime
    durationMs: int


class MarketRegimeSummary(BaseModel):
    totalReports: int
    bullishCount: int
    bearishCount: int
    rangingCount: int
    highVolatilityCount: int
    breakoutCount: int
    reversalCount: int
    uncertainCount: int


class MarketRegimeListResponse(BaseModel):
    reports: List[MarketRegimeReport]
    summary: MarketRegimeSummary
    lastUpdated: datetime
