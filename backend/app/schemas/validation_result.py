from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List

class ValidationStatus(str, Enum):
    PASSED = "PASSED"
    PARTIALLY_PASSED = "PARTIALLY_PASSED"
    FAILED = "FAILED"

class ValidationCheck(BaseModel):
    title: str
    description: str
    passed: bool
    mandatory: bool
    weight: int
    scoreAwarded: int

class ValidationSummary(BaseModel):
    totalChecks: int
    passedChecks: int
    failedChecks: int
    mandatoryPassed: int
    mandatoryFailed: int
    validationPercentage: int

class ValidationResult(BaseModel):
    id: str
    candidateId: str
    strategyId: str
    strategyName: str
    strategyVersion: str
    status: ValidationStatus
    validationScore: int
    summary: ValidationSummary
    checks: List[ValidationCheck]
    validatedAt: datetime
    validationDurationMs: int
    pipelineStage: str = "VALIDATION"
    pipelineVersion: str = "1.0"
    validatedBy: str = "Validation Engine"
    engineVersion: str = "1.0.0"
    timelineOrder: int = 2

class ValidationResultListResponse(BaseModel):
    results: List[ValidationResult]
    lastUpdated: datetime
