"""
Falcon V10 — Research Promotion Gate Schemas (Phase 4B).

Defines read-only, non-ranking, non-trading contracts for evaluating whether
a historically discovered and independently forward-validated research candidate
is eligible to be exposed as informational research context to the signal-intelligence layer.

Strict separation:
Descriptive research evidence only; zero automated trading directives.
Zero ranking; zero DB mutations; zero broker connectivity.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.historical_behaviour import (
    DescriptiveStatistics,
    SampleAdequacy,
)
from app.schemas.historical_findings import (
    ForwardValidationDataQualityCensus,
    ForwardValidationStatus,
    GroupStabilityAnalysis,
    HypothesisStatus,
)


class PromotionStatus(str, Enum):
    """
    Categorical promotion eligibility status for candidate hypotheses.
    Strictly non-ranking and non-scoring. Never converted into a recommendation,
    weight, rank, or execution decision.
    """
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    LIMITED_DATA = "LIMITED_DATA"
    DATA_QUALITY_LIMITED = "DATA_QUALITY_LIMITED"
    TEMPORALLY_UNSTABLE = "TEMPORALLY_UNSTABLE"
    ELIGIBLE_INFORMATIONAL = "ELIGIBLE_INFORMATIONAL"


class ResearchPromotionResult(BaseModel):
    """
    Descriptive research promotion evaluation result for a frozen candidate hypothesis.
    Preserves complete provenance from Phase 3 (Discovery/Validation) and Phase 3C (Forward Validation).
    """
    # Candidate Identity & Boundaries (Strictly Immutable)
    candidate_id: str
    candidate_as_of: datetime
    validation_as_of: datetime
    instrument: str
    timeframe: str
    horizon: int
    behaviour_identity: str
    context_identity: str

    # Frozen Candidate Hypothesis Baseline (Phase 3)
    candidate_wording: str
    discovery_sample_size: int = 0
    discovery_metrics: Optional[DescriptiveStatistics] = None
    validation_sample_size: int = 0
    validation_metrics: Optional[DescriptiveStatistics] = None
    qualification_status: HypothesisStatus = HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS
    candidate_limitations: List[str] = Field(default_factory=list)
    candidate_stability: Optional[GroupStabilityAnalysis] = None

    # Independent Paper Forward Validation (Phase 3C)
    forward_validation_sample_size: int = 0
    forward_validation_sample_adequacy: SampleAdequacy = SampleAdequacy.UNKNOWN
    forward_validation_metrics: Optional[DescriptiveStatistics] = None
    forward_validation_stability: Optional[GroupStabilityAnalysis] = None
    forward_validation_status: ForwardValidationStatus = ForwardValidationStatus.NOT_EVALUATED
    data_quality_breakdown: ForwardValidationDataQualityCensus = Field(default_factory=ForwardValidationDataQualityCensus)

    # Promotion Gate Evaluation (Phase 4B)
    promotion_status: PromotionStatus = PromotionStatus.NOT_EVALUATED
    promotion_methodology_version: str = "1.0.0"
    promotion_reasons: List[str] = Field(default_factory=list)
    promotion_limitations: List[str] = Field(default_factory=list)


class ResearchPromotionResponse(BaseModel):
    """
    Response schema for GET /api/v1/analytics/candlestick-behaviour/promotion (Phase 4B).
    Stateless, read-only, non-ranking, and contains zero execution directives.
    """
    experiment_name: str = "RESEARCH_PROMOTION_GATE"
    experiment_version: str = "1.0.0"
    phase_1_version: str = "1.0.0"
    phase_2_version: str = "1.0.0"
    phase_3_version: str = "1.0.0"
    phase_3c_version: str = "1.0.0"
    promotion_methodology_version: str = "1.0.0"
    as_of: datetime
    candidate_as_of: datetime
    validation_as_of: datetime
    query_parameters: Dict[str, Any] = Field(default_factory=dict)

    # Aggregate Censuses
    total_candidates: int = 0
    eligible_informational_candidates: int = 0
    not_eligible_candidates: int = 0
    limited_data_candidates: int = 0
    data_quality_limited_candidates: int = 0
    temporally_unstable_candidates: int = 0

    promotion_results: List[ResearchPromotionResult] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class ResearchSignalContext(BaseModel):
    """
    Read-only informational research context object allowed to cross into signal schemas.
    Contains descriptive provenance only.
    Strictly prohibited from containing order parameters, lots, entry, SL, TP, or broker commands.
    """
    candidate_id: str
    instrument: str
    timeframe: str
    horizon: int
    behaviour_identity: str
    context_identity: str
    candidate_as_of: datetime
    validation_as_of: datetime
    promotion_status: PromotionStatus
    qualification_status: HypothesisStatus
    forward_validation_sample_size: int = 0
    forward_validation_status: ForwardValidationStatus
    methodology_version: str = "1.0.0"
    provenance_note: str
    limitations: List[str] = Field(default_factory=list)
