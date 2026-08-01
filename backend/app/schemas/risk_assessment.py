from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class RiskCategory(str, Enum):
    CAPITAL = "CAPITAL"
    EXPOSURE = "EXPOSURE"
    MARKET = "MARKET"
    VOLATILITY = "VOLATILITY"
    NEWS = "NEWS"
    SESSION = "SESSION"
    STRATEGY = "STRATEGY"

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"

class RiskSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class RiskAssessmentStatus(str, Enum):
    PASSED = "PASSED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"

class RecommendationAction(str, Enum):
    PROCEED = "PROCEED"
    MONITOR = "MONITOR"
    REDUCE_RISK = "REDUCE_RISK"
    WAIT = "WAIT"
    BLOCK = "BLOCK"

class RiskThresholds(BaseModel):
    lowMax: int
    mediumMax: int
    highMax: int
    extremeMax: int

class RiskRecommendation(BaseModel):
    action: RecommendationAction
    title: str
    description: str

class RiskReason(BaseModel):
    title: str
    description: str
    severity: RiskSeverity
    isBlocking: bool

class RiskCategoryScore(BaseModel):
    category: RiskCategory
    score: int
    maxScore: int
    percentage: int
    description: str

class RiskMarketSnapshot(BaseModel):
    trend: str
    volatility: str
    session: str
    spread: float
    newsImpact: str
    marketSentiment: str

class RiskAssessment(BaseModel):
    id: str
    candidateId: str
    validationId: str
    strategyId: str
    previousAssessmentId: Optional[str] = None
    status: RiskAssessmentStatus
    overallRiskScore: int
    riskLevel: RiskLevel
    thresholds: RiskThresholds
    recommendation: RiskRecommendation
    categoryScores: List[RiskCategoryScore]
    reasons: List[RiskReason]
    marketSnapshot: RiskMarketSnapshot
    pipelineStage: str = "RISK"
    pipelineVersion: str = "1.0"
    engineVersion: str = "1.0.2"
    assessedBy: str = "Risk Engine"
    timelineOrder: int = 3
    assessedAt: datetime
    assessmentDurationMs: int

class RiskSummary(BaseModel):
    totalAssessments: int
    lowRisk: int
    mediumRisk: int
    highRisk: int
    extremeRisk: int
    averageRiskScore: int

class RiskAssessmentListResponse(BaseModel):
    assessments: List[RiskAssessment]
    summary: RiskSummary
    lastUpdated: datetime
