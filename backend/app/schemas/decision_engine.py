from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.schemas.strategy import RiskLevel
from app.schemas.health import SystemHealth

class Recommendation(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"

class DecisionStatus(str, Enum):
    READY = "READY"
    MONITOR = "MONITOR"
    WAIT = "WAIT"
    BLOCKED = "BLOCKED"

class TradeQuality(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B_PLUS = "B+"
    B = "B"
    C = "C"
    D = "D"

class DecisionReason(BaseModel):
    title: str
    description: str
    passed: bool

class MissingCondition(BaseModel):
    title: str
    description: str

class ConfidenceExplanation(BaseModel):
    technicalSignalsContribution: int
    marketSentimentContribution: int
    newsImpactContribution: int
    historicalPerformanceContribution: int
    consistencyBonus: int

class RiskAssessment(BaseModel):
    accountRiskPercent: float
    maxDrawdown: float
    positionSizeRecommendation: float
    riskFactors: List[str]

class ExecutionReadiness(BaseModel):
    isReady: bool
    overallReadinessScore: int
    blockingConditions: List[str]
    passedChecks: List[str]
    estimatedTimeUntilReady: Optional[str]

class MarketClock(BaseModel):
    sessionName: str
    isOpen: bool
    timeUntilOpenOrClose: str

class TimelineEvent(BaseModel):
    timestamp: datetime
    formattedTime: str
    title: str
    description: str
    icon: str

class DecisionEngineResponse(BaseModel):
    recommendation: Recommendation
    decisionStatus: DecisionStatus
    riskLevel: RiskLevel
    tradeQuality: TradeQuality
    
    confidenceScore: int
    minimumConfidence: int
    confidenceGap: int
    
    greetingMessage: str
    captainsAction: str
    engineVersion: str
    
    reasons: List[DecisionReason]
    missingConditions: List[MissingCondition]
    explanation: ConfidenceExplanation
    lastUpdated: datetime

    # Strategy & readiness extensions for Mission Control
    strategyId: str
    strategyName: str
    strategyVersion: str
    strategyScore: int
    strategyValidationScore: int
    primaryWaitReason: Optional[str] = None
    confidenceHistory: List[int]
    executionReadiness: ExecutionReadiness
    systemHealth: SystemHealth
    marketClocks: List[MarketClock]
    timeline: List[TimelineEvent]
