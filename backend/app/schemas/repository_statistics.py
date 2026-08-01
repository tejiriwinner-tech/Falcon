from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class RepositoryStatistics(BaseModel):
    totalMissions: int
    totalMarketStates: int
    totalCandidates: int
    totalValidations: int
    totalRiskAssessments: int
    totalExecutionReadiness: int
    totalDecisions: int
    repositoryHealth: float
    startedAt: datetime
    lastMissionAt: Optional[datetime] = None
