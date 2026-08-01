from pydantic import BaseModel
from datetime import datetime
from typing import List

class EngineStatus(BaseModel):
    name: str
    version: str
    status: str
    latencyMs: int
    lastRun: datetime

class PerformanceMetrics(BaseModel):
    cpuUsagePercent: float
    memoryUsageMb: float
    totalApiCalls: int
    avgResponseTimeMs: int
    strategyEvaluations: int
    decisionUpdates: int

class SystemHealth(BaseModel):
    overallHealthy: bool
    engines: List[EngineStatus]
    performanceMetrics: PerformanceMetrics
    lastSuccessfulSync: datetime

class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    timestamp: datetime
    systemHealth: SystemHealth
