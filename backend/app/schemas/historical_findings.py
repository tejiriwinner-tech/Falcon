"""
Falcon V10 — Historical Research Findings & Stability Analysis Schemas (Phase 3).

Defines research-only data contracts for:
1. Temporal Stability Analysis across chronological periods (Full, Early, Middle, Late).
2. Out-of-sample Discovery vs Validation isolation (Chronological 70/30 split).
3. Candidate Paper-Only Research Hypotheses with mandatory limitations.
4. Objective, non-ranking eligibility qualification.

Strict separation:
Descriptive research evidence only; zero production trading decisions.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.historical_behaviour import (
    DataQuality,
    DescriptiveStatistics,
    DirectionalBias,
    DistributionMetrics,
    ForwardWindowMetrics,
    HistoricalBehaviourObservation,
    SampleAdequacy,
    SubsequentDirection,
)


# -----------------------------------------------------------------------------
# Phase 3 Categorical Enums
# -----------------------------------------------------------------------------

class StabilityStatus(str, Enum):
    """
    Descriptive categorization of cross-period relationship stability.
    Strictly non-scoring; never converted to a numerical score.
    """
    STABLE_DESCRIPTIVE = "STABLE_DESCRIPTIVE"
    MIXED = "MIXED"
    INCONSISTENT = "INCONSISTENT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNKNOWN = "UNKNOWN"


class DirectionConsistency(str, Enum):
    """
    Descriptive categorization of directional consistency across evaluable periods.
    """
    CONSISTENT = "CONSISTENT"
    MIXED = "MIXED"
    INCONSISTENT = "INCONSISTENT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class TemporalPeriod(str, Enum):
    """
    Chronological partition identifiers for temporal stability evaluation.
    """
    FULL_PERIOD = "FULL_PERIOD"
    EARLY_PERIOD = "EARLY_PERIOD"
    MIDDLE_PERIOD = "MIDDLE_PERIOD"
    LATE_PERIOD = "LATE_PERIOD"


class ResearchPartitionPhase(str, Enum):
    """
    Chronological split for out-of-sample research isolation.
    """
    DISCOVERY = "DISCOVERY"
    VALIDATION = "VALIDATION"


class HypothesisStatus(str, Enum):
    """
    Status of an objective candidate research hypothesis.
    """
    CANDIDATE_PAPER_HYPOTHESIS = "CANDIDATE_PAPER_HYPOTHESIS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REJECTED_STABILITY = "REJECTED_STABILITY"
    EXPLORATORY = "EXPLORATORY"


# -----------------------------------------------------------------------------
# Stability Metrics Models
# -----------------------------------------------------------------------------

class PeriodStabilityMetrics(BaseModel):
    """
    Descriptive outcome metrics measured for a specific temporal partition period.
    """
    period: TemporalPeriod
    sample_size: int = 0
    sample_adequacy: SampleAdequacy = SampleAdequacy.UNKNOWN
    mean_raw_return: Optional[float] = None
    median_raw_return: Optional[float] = None
    mean_directional_return: Optional[float] = None
    median_directional_return: Optional[float] = None
    follow_through_rate: float = 0.0
    reversal_rate: float = 0.0
    neutral_rate: float = 0.0
    mean_mfe: Optional[float] = None
    median_mfe: Optional[float] = None
    mean_mae: Optional[float] = None
    median_mae: Optional[float] = None
    volatility_normalized_return: Optional[float] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class GroupStabilityAnalysis(BaseModel):
    """
    Comprehensive cross-period stability diagnostics for a candidate group.
    Contains zero numerical stability scores.
    """
    sample_size_by_period: Dict[str, int] = Field(default_factory=dict)
    median_return_by_period: Dict[str, Optional[float]] = Field(default_factory=dict)
    mean_return_by_period: Dict[str, Optional[float]] = Field(default_factory=dict)
    follow_through_rate_by_period: Dict[str, float] = Field(default_factory=dict)
    reversal_rate_by_period: Dict[str, float] = Field(default_factory=dict)
    mfe_by_period: Dict[str, Optional[float]] = Field(default_factory=dict)
    mae_by_period: Dict[str, Optional[float]] = Field(default_factory=dict)
    volatility_normalized_return_by_period: Dict[str, Optional[float]] = Field(default_factory=dict)
    periods_available: int = 0
    periods_with_evaluable_samples: int = 0  # Periods with SampleAdequacy in {ADEQUATE, LIMITED} (N >= 10)
    direction_consistency: DirectionConsistency = DirectionConsistency.INSUFFICIENT_DATA
    sign_consistency: Optional[bool] = None
    magnitude_variation: Optional[float] = None  # max(median) - min(median) across evaluable periods
    stability_status: StabilityStatus = StabilityStatus.INSUFFICIENT_DATA
    period_metrics: Dict[str, PeriodStabilityMetrics] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# Research Finding Model
# -----------------------------------------------------------------------------

class ResearchFinding(BaseModel):
    """
    Traceable historical research finding binding behaviour, context, horizon,
    descriptive distributions, and multi-period stability.
    """
    finding_id: str
    instrument: str
    timeframe: str
    horizon: int
    behaviour_identity: str
    context_identity: str
    sample_size: int = 0
    sample_adequacy: SampleAdequacy = SampleAdequacy.UNKNOWN
    full_period_statistics: DescriptiveStatistics = Field(default_factory=DescriptiveStatistics)
    full_period_distribution: DistributionMetrics = Field(default_factory=DistributionMetrics)
    stability_analysis: GroupStabilityAnalysis = Field(default_factory=GroupStabilityAnalysis)
    observation_ids_sample: List[str] = Field(default_factory=list)  # max 20 deterministic IDs
    phase1_methodology_version: str = "1.0.0"
    phase2_methodology_version: str = "1.0.0"
    phase3_methodology_version: str = "1.0.0"
    partition_methodology: str = "CHRONOLOGICAL_TERTILES_V1"
    as_of: datetime


# -----------------------------------------------------------------------------
# Candidate Hypothesis Model
# -----------------------------------------------------------------------------

class CandidateHypothesis(BaseModel):
    """
    Objective, descriptive candidate research hypothesis.
    Maintains strict structural separation between Discovery and Validation data.
    Contains mandatory limitations and zero recommendation language.
    """
    hypothesis_id: str
    behaviour: str
    context: str
    instrument: str
    timeframe: str
    horizon: int
    historical_period: str
    descriptive_observation: str
    limitations: List[str] = Field(default_factory=list)
    status: HypothesisStatus = HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS

    # Discovery Population (Sole determinant of qualification & wording)
    discovery_sample_size: int = 0
    discovery_sample_adequacy: SampleAdequacy = SampleAdequacy.UNKNOWN
    discovery_metrics: DescriptiveStatistics = Field(default_factory=DescriptiveStatistics)
    discovery_stability: GroupStabilityAnalysis = Field(default_factory=GroupStabilityAnalysis)

    # Validation Population (Independent descriptive evaluation only)
    validation_sample_size: int = 0
    validation_sample_adequacy: SampleAdequacy = SampleAdequacy.UNKNOWN
    validation_metrics: Optional[DescriptiveStatistics] = None
    validation_stability: Optional[GroupStabilityAnalysis] = None
    validation_data_quality: DataQuality = DataQuality.VALID

    # Traceability & Provenance
    discovery_spread_methodology: str = "CHRONOLOGICAL_DISCOVERY_TERTILES_V1"
    partition_methodology: str = "CHRONOLOGICAL_TERTILES_V1"
    discovery_validation_methodology: str = "CHRONOLOGICAL_70_30_V1"
    observation_ids_sample: List[str] = Field(default_factory=list)  # max 20 deterministic IDs


# -----------------------------------------------------------------------------
# Population Metrics & Response Models
# -----------------------------------------------------------------------------

class PopulationMetrics(BaseModel):
    """
    Census counts across all defined research populations.
    Prevents double-counting and mixing incomplete records with valid outcomes.
    """
    all_observations: int = 0
    valid_outcome_population: int = 0
    adequate_sample_population: int = 0
    limited_sample_population: int = 0
    insufficient_sample_population: int = 0
    stability_analysis_population: int = 0
    candidate_hypothesis_population: int = 0


class HistoricalFindingsResponse(BaseModel):
    """
    Response schema for GET /api/v1/analytics/candlestick-behaviour/findings.
    Stateless, read-only, deterministic.
    """
    experiment_name: str = "HISTORICAL_RESEARCH_FINDINGS_AND_STABILITY"
    experiment_version: str = "1.0.0"
    phase_1_version: str = "1.0.0"
    phase_2_version: str = "1.0.0"
    research_methodology_version: str = "1.0.0"
    partition_methodology: str = "CHRONOLOGICAL_TERTILES_V1"
    discovery_validation_methodology: str = "CHRONOLOGICAL_70_30_V1"
    discovery_spread_methodology: str = "CHRONOLOGICAL_DISCOVERY_TERTILES_V1"
    as_of: datetime
    query_parameters: Dict[str, Any] = Field(default_factory=dict)
    population_metrics: PopulationMetrics = Field(default_factory=PopulationMetrics)
    sample_adequacy: SampleAdequacy = SampleAdequacy.UNKNOWN
    findings: List[ResearchFinding] = Field(default_factory=list)
    breakdowns: Dict[str, Any] = Field(default_factory=dict)
    data_quality: DataQuality = DataQuality.VALID


class HistoricalStabilityResponse(BaseModel):
    """
    Response schema for GET /api/v1/analytics/candlestick-behaviour/stability.
    """
    experiment_name: str = "HISTORICAL_RESEARCH_FINDINGS_AND_STABILITY"
    experiment_version: str = "1.0.0"
    phase_1_version: str = "1.0.0"
    phase_2_version: str = "1.0.0"
    research_methodology_version: str = "1.0.0"
    partition_methodology: str = "CHRONOLOGICAL_TERTILES_V1"
    as_of: datetime
    query_parameters: Dict[str, Any] = Field(default_factory=dict)
    sample_size: int = 0
    stability_records: List[GroupStabilityAnalysis] = Field(default_factory=list)
    group_summaries: Dict[str, Any] = Field(default_factory=dict)


class HistoricalHypothesesResponse(BaseModel):
    """
    Response schema for GET /api/v1/analytics/candlestick-behaviour/hypotheses.
    """
    experiment_name: str = "HISTORICAL_RESEARCH_FINDINGS_AND_STABILITY"
    experiment_version: str = "1.0.0"
    phase_1_version: str = "1.0.0"
    phase_2_version: str = "1.0.0"
    research_methodology_version: str = "1.0.0"
    discovery_validation_methodology: str = "CHRONOLOGICAL_70_30_V1"
    discovery_spread_methodology: str = "CHRONOLOGICAL_DISCOVERY_TERTILES_V1"
    as_of: datetime
    query_parameters: Dict[str, Any] = Field(default_factory=dict)
    total_hypotheses: int = 0
    hypotheses: List[CandidateHypothesis] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Phase 3B Candidate Monitoring & Persistence Analysis Models
# -----------------------------------------------------------------------------

class CandidateMonitoring(BaseModel):
    """
    Descriptive historical candidate monitoring result (Phase 3B).
    Evaluates what descriptive behaviour is observed in chronological observations
    occurring strictly after the candidate's frozen boundary (candidate_as_of).
    Strictly read-only; non-ranking; zero trading directives.
    """
    candidate_id: str
    candidate_as_of: datetime
    instrument: str
    timeframe: str
    horizon: int
    behaviour_identity: str
    context_identity: str
    candidate_wording: str

    # Frozen Historical Candidate Baseline (Immutable)
    discovery_sample_size: int = 0
    discovery_metrics: Optional[DescriptiveStatistics] = None
    validation_sample_size: int = 0
    validation_metrics: Optional[DescriptiveStatistics] = None
    qualification_status: HypothesisStatus = HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS
    candidate_limitations: List[str] = Field(default_factory=list)

    # Monitoring Period & Census (Strictly observation_time > candidate_as_of)
    monitoring_start: Optional[datetime] = None
    monitoring_end: Optional[datetime] = None
    monitoring_total_observations: int = 0
    monitoring_sample_size: int = 0  # Count of VALID outcome observations
    monitoring_incomplete_observations: int = 0
    monitoring_invalid_observations: int = 0
    monitoring_sample_adequacy: SampleAdequacy = SampleAdequacy.UNKNOWN
    monitoring_data_quality: DataQuality = DataQuality.VALID

    # Descriptive Monitoring Metrics
    monitoring_metrics: Optional[DescriptiveStatistics] = None
    monitoring_stability: Optional[GroupStabilityAnalysis] = None
    observation_ids_sample: List[str] = Field(default_factory=list)  # max 20 deterministic IDs

    # Traceability & Provenance
    methodology_version: str = "1.0.0"
    monitoring_limitations: List[str] = Field(default_factory=list)


class CandidateMonitoringResponse(BaseModel):
    """
    Response schema for GET /api/v1/analytics/candlestick-behaviour/monitoring (Phase 3B).
    Stateless, read-only, deterministic.
    """
    experiment_name: str = "HISTORICAL_CANDIDATE_MONITORING"
    experiment_version: str = "1.0.0"
    phase_1_version: str = "1.0.0"
    phase_2_version: str = "1.0.0"
    phase_3_version: str = "1.0.0"
    as_of: datetime
    candidate_as_of: datetime
    query_parameters: Dict[str, Any] = Field(default_factory=dict)

    total_candidates: int = 0
    total_monitoring_observations: int = 0
    total_valid_monitoring_observations: int = 0
    total_incomplete_monitoring_observations: int = 0

    monitoring_records: List[CandidateMonitoring] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


# Type aliases for flexible contract compatibility
CandidateMonitoringMetrics = CandidateMonitoring
HistoricalMonitoringResponse = CandidateMonitoringResponse


# -----------------------------------------------------------------------------
# Phase 3C Independent Paper-Only Forward Validation Models
# -----------------------------------------------------------------------------

class ForwardValidationStatus(str, Enum):
    """
    Descriptive categorical status of independent paper forward validation (Phase 3C).
    Non-ranking, non-predictive; zero trading recommendations.
    """
    NOT_EVALUATED = "NOT_EVALUATED"
    NO_FORWARD_DATA = "NO_FORWARD_DATA"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    LIMITED_DATA = "LIMITED_DATA"
    ADEQUATE_DATA = "ADEQUATE_DATA"
    VALIDATED_DESCRIPTIVELY = "VALIDATED_DESCRIPTIVELY"
    DATA_QUALITY_LIMITED = "DATA_QUALITY_LIMITED"


class ForwardValidationDataQualityCensus(BaseModel):
    """
    Data-quality breakdown of forward observations.
    Excludes non-VALID observations from metrics while maintaining complete census fidelity.
    """
    total_observations: int = 0
    valid_count: int = 0
    incomplete_count: int = 0
    invalid_count: int = 0
    unknown_count: int = 0


class ForwardValidationResult(BaseModel):
    """
    Descriptive forward validation result for a frozen candidate hypothesis (Phase 3C).
    Evaluates genuinely unseen chronological observations (candidate_as_of < T0 <= validation_as_of).
    Candidate identity, wording, and Discovery metrics remain strictly immutable.
    """
    # Frozen Candidate Hypothesis Baseline (Strictly Immutable)
    candidate_id: str
    candidate_as_of: datetime
    validation_as_of: datetime
    instrument: str
    timeframe: str
    horizon: int
    behaviour_identity: str
    context_identity: str
    candidate_wording: str
    discovery_sample_size: int = 0
    discovery_metrics: Optional[DescriptiveStatistics] = None
    validation_sample_size: int = 0
    validation_metrics: Optional[DescriptiveStatistics] = None
    qualification_status: HypothesisStatus = HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS
    candidate_limitations: List[str] = Field(default_factory=list)
    candidate_stability: Optional[GroupStabilityAnalysis] = None

    # Forward Validation Period & Census (candidate_as_of < observation_time <= validation_as_of)
    forward_validation_start: Optional[datetime] = None
    forward_validation_end: Optional[datetime] = None
    forward_validation_sample_size: int = 0  # Count of VALID outcome observations
    forward_validation_sample_adequacy: SampleAdequacy = SampleAdequacy.UNKNOWN
    data_quality_breakdown: ForwardValidationDataQualityCensus = Field(default_factory=ForwardValidationDataQualityCensus)

    # Descriptive Forward Outcome Metrics (Computed on VALID observations only)
    forward_validation_metrics: Optional[DescriptiveStatistics] = None
    forward_validation_stability: Optional[GroupStabilityAnalysis] = None
    forward_validation_status: ForwardValidationStatus = ForwardValidationStatus.NOT_EVALUATED

    # Traceability & Provenance
    observation_ids_sample: List[str] = Field(default_factory=list)  # max 20 deterministic IDs
    methodology_version: str = "1.0.0"
    validation_limitations: List[str] = Field(default_factory=list)


class ForwardValidationResponse(BaseModel):
    """
    Response schema for GET /api/v1/analytics/candlestick-behaviour/forward-validation (Phase 3C).
    Stateless, read-only, non-persistent, deterministic.
    """
    experiment_name: str = "INDEPENDENT_PAPER_FORWARD_VALIDATION"
    experiment_version: str = "1.0.0"
    phase_1_version: str = "1.0.0"
    phase_2_version: str = "1.0.0"
    phase_3_version: str = "1.0.0"
    forward_validation_methodology_version: str = "1.0.0"
    as_of: datetime
    candidate_as_of: datetime
    validation_as_of: datetime
    query_parameters: Dict[str, Any] = Field(default_factory=dict)

    total_candidates: int = 0
    total_forward_observations: int = 0
    total_valid_forward_observations: int = 0
    total_incomplete_forward_observations: int = 0

    validation_results: List[ForwardValidationResult] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


# Type aliases for flexible contract compatibility
ForwardValidationMetrics = ForwardValidationResult
