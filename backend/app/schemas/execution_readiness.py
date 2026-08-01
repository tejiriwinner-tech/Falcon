from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

from app.schemas.signal_candidate import CandidateStatus
from app.schemas.validation_result import ValidationStatus
from app.schemas.risk_assessment import RiskLevel, RiskAssessmentStatus

class ExecutionReadinessStatus(str, Enum):
    READY = "READY"
    WAIT = "WAIT"
    BLOCKED = "BLOCKED"

class ReadinessCategory(str, Enum):
    MARKET = "MARKET"
    SESSION = "SESSION"
    SPREAD = "SPREAD"
    VOLATILITY = "VOLATILITY"
    NEWS = "NEWS"
    RISK = "RISK"
    VALIDATION = "VALIDATION"
    SYSTEM = "SYSTEM"

class ReadinessSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class ReadinessAction(str, Enum):
    PROCEED = "PROCEED"
    MONITOR = "MONITOR"
    WAIT = "WAIT"
    BLOCK = "BLOCK"

class ReadinessThresholds(BaseModel):
    readyMin: int
    waitMin: int
    blockedMin: int

class ReadinessRecommendation(BaseModel):
    action: ReadinessAction
    title: str
    description: str
    nextReviewIn: Optional[str] = None

class ReadinessReason(BaseModel):
    title: str
    description: str
    severity: ReadinessSeverity
    isBlocking: bool

class ReadinessCategoryScore(BaseModel):
    category: ReadinessCategory
    score: int
    maxScore: int
    percentage: int
    description: str

class ExecutionMarketSnapshot(BaseModel):
    session: str
    spread: float
    volatility: str
    newsImpact: str
    marketSentiment: str
    marketConfidence: int
    marketOpen: bool
    dataAgeSeconds: int

class ExecutionReadiness(BaseModel):
    id: str
    candidateId: str
    validationId: str
    riskAssessmentId: str
    strategyId: str
    status: ExecutionReadinessStatus
    overallReadinessScore: int
    thresholds: ReadinessThresholds
    recommendation: ReadinessRecommendation
    categoryScores: List[ReadinessCategoryScore]
    reasons: List[ReadinessReason]
    marketSnapshot: ExecutionMarketSnapshot
    
    # Frozen upstream verdicts
    candidateStatus: CandidateStatus
    validationStatus: ValidationStatus
    riskLevel: RiskLevel
    riskStatus: RiskAssessmentStatus
    
    # Pipeline metadata
    artifactType: str = "ExecutionReadiness"
    pipelineStage: str = "EXECUTION"
    pipelineVersion: str = "1.0"
    engineVersion: str = "1.0.0"
    evaluatedBy: str = "Execution Readiness Engine"
    timelineOrder: int = 4
    evaluatedAt: datetime
    evaluationDurationMs: int

class ExecutionSummary(BaseModel):
    totalAssessments: int
    ready: int
    waiting: int
    blocked: int
    averageReadinessScore: int

class ExecutionReadinessListResponse(BaseModel):
    assessments: List[ExecutionReadiness]
    summary: ExecutionSummary
    lastUpdated: datetime
