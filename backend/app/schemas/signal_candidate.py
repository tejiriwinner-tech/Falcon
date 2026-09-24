from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from app.schemas.research_promotion import ResearchSignalContext

class CandidateStatus(str, Enum):
    GENERATED = "GENERATED"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    VALIDATED = "VALIDATED"
    RISK_CHECKED = "RISK_CHECKED"
    EXECUTION_READY = "EXECUTION_READY"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class CandidateDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"

class CandidateReason(BaseModel):
    title: str
    description: str
    passed: bool

class CandidateCondition(BaseModel):
    title: str
    description: str
    passed: bool

class ConfidenceBreakdown(BaseModel):
    trendScore: int
    strategyScore: int
    sessionScore: int
    sentimentScore: int
    newsScore: int

class CandidateMarketSnapshot(BaseModel):
    trend: str
    volatility: str
    session: str
    spread: float
    newsImpact: str
    marketSentiment: str
    marketConfidence: int
    atr: Optional[float] = None
    rsi: Optional[float] = None

class SignalCandidate(BaseModel):
    id: str
    symbol: str
    strategyId: str
    strategyName: str
    strategyVersion: str
    strategyGrade: str
    strategyScore: int
    direction: CandidateDirection
    confidence: int  # integer between 0 and 100
    readinessScore: int  # integer between 0 and 100
    entryPrice: float
    stopLoss: float
    takeProfit: float
    riskReward: float
    status: CandidateStatus
    generatedAt: datetime
    reasons: List[CandidateReason]
    conditions: List[CandidateCondition]
    marketSnapshot: CandidateMarketSnapshot
    confidenceBreakdown: ConfidenceBreakdown
    evaluationDurationMs: int
    marketDataAgeSeconds: int
    evaluationStartedAt: datetime
    evaluationCompletedAt: datetime
    # Adaptive tuning metadata (immutable snapshot from candidate generation)
    adaptiveRuleVersion: Optional[str] = None
    adaptiveStopMultiplier: Optional[float] = None
    # Informational Research Promotion Context (Phase 4B)
    researchContext: Optional[ResearchSignalContext] = None
    # Pipeline metadata — consistent with all immutable Falcon artifacts
    pipelineStage: str = "SIGNAL_GENERATION"
    pipelineVersion: str = "1.0"
    engineVersion: str = "1.1.0"
    generatedBy: str = "Signal Generation Engine"
    timelineOrder: int = 1

class SignalCandidateListResponse(BaseModel):
    candidates: List[SignalCandidate]
    lastUpdated: datetime
