from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

from app.schemas.signal_candidate import CandidateStatus
from app.schemas.validation_result import ValidationStatus
from app.schemas.risk_assessment import RiskLevel, RiskAssessmentStatus
from app.schemas.execution_readiness import ExecutionReadinessStatus

class DecisionRecommendation(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"
    MONITOR = "MONITOR"
    NO_TRADE = "NO_TRADE"

class DecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    MONITORING = "MONITORING"
    PENDING = "PENDING"
    REJECTED = "REJECTED"

class DecisionSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class DecisionPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class DecisionFactor(BaseModel):
    title: str
    description: str
    severity: DecisionSeverity
    priority: DecisionPriority
    passed: bool

class DecisionRecommendationDetails(BaseModel):
    recommendation: DecisionRecommendation
    priority: DecisionPriority
    expectedHolding: str
    nextReviewIn: Optional[str] = None
    missionStatus: str
    title: str
    description: str

class DecisionStageTrace(BaseModel):
    stage: str
    artifactId: str
    status: str
    completedAt: datetime

class MissionVerdict(BaseModel):
    signalVerdict: CandidateStatus
    validationVerdict: ValidationStatus
    riskVerdict: RiskLevel
    executionVerdict: ExecutionReadinessStatus
    decisionVerdict: DecisionRecommendation

class DecisionMarketSnapshot(BaseModel):
    trend: str
    volatility: str
    session: str
    spread: float
    newsImpact: str
    marketSentiment: str
    marketConfidence: float
    dataAgeSeconds: int

class DecisionPipelineSummary(BaseModel):
    candidateStatus: CandidateStatus
    validationStatus: ValidationStatus
    riskStatus: RiskAssessmentStatus
    executionStatus: ExecutionReadinessStatus
    signalConfidence: float
    validationScore: float
    overallRiskScore: float
    executionReadinessScore: float

class DecisionArtifact(BaseModel):
    id: str
    marketStateId: str
    candidateId: str
    validationId: str
    riskAssessmentId: str
    executionReadinessId: str
    strategyId: str
    strategyName: str
    strategyVersion: str
    recommendation: DecisionRecommendation
    status: DecisionStatus
    decisionConfidence: float
    recommendationDetails: DecisionRecommendationDetails
    missionVerdict: MissionVerdict
    decisionTrace: List[DecisionStageTrace]
    supportingFactors: List[DecisionFactor]
    blockingFactors: List[DecisionFactor]
    watchItems: List[DecisionFactor]
    pipelineSummary: DecisionPipelineSummary
    marketSnapshot: DecisionMarketSnapshot
    
    # Metadata
    artifactType: str = "DecisionArtifact"
    pipelineStage: str = "DECISION"
    pipelineVersion: str = "1.0"
    engineVersion: str = "1.0.0"
    decisionLogicVersion: str = "Captain Logic v1.0"
    decidedBy: str = "Decision Engine"
    timelineOrder: int = 6
    decidedAt: datetime
    decisionDurationMs: int

class DecisionSummary(BaseModel):
    totalDecisions: int
    buyCount: int
    sellCount: int
    waitCount: int
    monitorCount: int
    noTradeCount: int
    highestConfidence: float
    lowestConfidence: float
    averageConfidence: float

class DecisionArtifactListResponse(BaseModel):
    decisions: List[DecisionArtifact]
    summary: DecisionSummary
    lastUpdated: datetime
