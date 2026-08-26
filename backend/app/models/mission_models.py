"""
Falcon Mission Persistence Models
SQLAlchemy models for persistent mission storage.
"""
from datetime import datetime, timezone
import uuid
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, JSON, Boolean,
    ForeignKey, Index, Enum as SQLEnum, Text
)
from sqlalchemy.orm import relationship
from app.core.config.database import Base
from app.schemas.signal_candidate import CandidateStatus, CandidateDirection
from app.schemas.validation_result import ValidationStatus
from app.schemas.risk_assessment import RiskLevel, RiskAssessmentStatus
from app.schemas.execution_readiness import ExecutionReadinessStatus
from app.schemas.decision_artifact import DecisionRecommendation, DecisionStatus


class MissionRecord(Base):
    """Persistent mission storage."""
    __tablename__ = "missions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mission_number = Column(Integer, nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, index=True)  # SUCCESS, PARTIAL_SUCCESS, FAILED
    
    # Timestamps
    started_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Performance metrics
    total_duration_ms = Column(Integer, nullable=False)
    market_duration_ms = Column(Integer, nullable=False)
    regime_duration_ms = Column(Integer, nullable=False)
    signal_duration_ms = Column(Integer, nullable=False)
    validation_duration_ms = Column(Integer, nullable=False)
    risk_duration_ms = Column(Integer, nullable=False)
    execution_duration_ms = Column(Integer, nullable=False)
    decision_duration_ms = Column(Integer, nullable=False)
    average_stage_duration_ms = Column(Float, nullable=False)
    
    # Health metrics
    pipeline_health_percentage = Column(Float, nullable=False)
    provider_health_percentage = Column(Float, nullable=False)
    engines_healthy = Column(Integer, nullable=False)
    providers_healthy = Column(Integer, nullable=False)
    warnings = Column(JSON, nullable=False, default=list)
    
    # Pipeline summary
    market_state_count = Column(Integer, nullable=False)
    regime_count = Column(Integer, nullable=False, default=0)
    candidate_count = Column(Integer, nullable=False)
    validation_count = Column(Integer, nullable=False)
    risk_assessment_count = Column(Integer, nullable=False)
    execution_readiness_count = Column(Integer, nullable=False)
    decision_count = Column(Integer, nullable=False)
    
    # Metadata
    pipeline_version = Column(String(20), nullable=False)
    engine_version = Column(String(20), nullable=False)
    generated_by = Column(String(50), nullable=False)
    
    __table_args__ = (
        Index('idx_mission_status_started', 'status', 'started_at'),
        Index('idx_mission_completed', 'completed_at'),
        Index('idx_mission_number', 'mission_number'),
    )
    
    # Relationships
    market_states = relationship("MarketStateRecord", back_populates="mission", cascade="all, delete-orphan")
    regime_reports = relationship("MarketRegimeRecord", back_populates="mission", cascade="all, delete-orphan")
    candidates = relationship("SignalCandidateRecord", back_populates="mission", cascade="all, delete-orphan")
    validations = relationship("ValidationResultRecord", back_populates="mission", cascade="all, delete-orphan")
    risk_assessments = relationship("RiskAssessmentRecord", back_populates="mission", cascade="all, delete-orphan")
    execution_readiness_items = relationship("ExecutionReadinessRecord", back_populates="mission", cascade="all, delete-orphan")
    decisions = relationship("DecisionArtifactRecord", back_populates="mission", cascade="all, delete-orphan")
    provider_health_snapshots = relationship("ProviderHealthRecord", back_populates="mission", cascade="all, delete-orphan")
    timeline_events = relationship("MissionTimelineRecord", back_populates="mission", cascade="all, delete-orphan")


class MarketStateRecord(Base):
    """Persistent market state storage."""
    __tablename__ = "market_states"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mission_id = Column(String(36), ForeignKey("missions.id"), nullable=False, index=True)
    
    # Market state data
    symbol = Column(String(20), nullable=False, index=True)
    current_price = Column(Float, nullable=False)
    bid = Column(Float, nullable=False)
    ask = Column(Float, nullable=False)
    spread = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    
    # Market metadata
    trend = Column(String(20), nullable=False)
    volatility = Column(String(20), nullable=False)
    liquidity = Column(String(20), nullable=False)
    session = Column(String(50), nullable=False, index=True)
    market_open = Column(Boolean, nullable=False, index=True)
    
    # Sentiment and news
    market_sentiment_label = Column(String(20), nullable=False)
    fear_greed_index = Column(Integer, nullable=True)
    current_news_impact = Column(String(20), nullable=False)
    upcoming_high_impact_news = Column(Boolean, nullable=False)
    
    # Freshness and confidence
    data_age_seconds = Column(Integer, nullable=False)
    overall_market_confidence = Column(Integer, nullable=False)
    quote_status = Column(String(20), nullable=False, index=True)
    freshness_seconds = Column(Float, nullable=False)
    
    # Provider info
    primary_provider_id = Column(String(50), nullable=True)
    primary_provider_name = Column(String(50), nullable=True)
    
    # Metadata
    watchlist_symbols = Column(JSON, nullable=False)
    data_source = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        Index('idx_market_state_mission_symbol', 'mission_id', 'symbol'),
        Index('idx_market_state_timestamp', 'timestamp'),
        Index('idx_market_state_symbol_timestamp', 'symbol', 'timestamp'),
    )
    
    # Relationships
    mission = relationship("MissionRecord", back_populates="market_states")


class MarketRegimeRecord(Base):
    """Persistent market regime report storage."""
    __tablename__ = "market_regimes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mission_id = Column(String(36), ForeignKey("missions.id"), nullable=False, index=True)
    
    # Regime classification
    regime = Column(String(50), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    
    # Supporting data
    supporting_factors = Column(JSON, nullable=False, default=list)
    risk_factors = Column(JSON, nullable=False, default=list)
    
    # Market context
    trend_alignment = Column(String(20), nullable=False)
    volatility_assessment = Column(String(20), nullable=False)
    liquidity_status = Column(String(20), nullable=False)
    
    # Metadata
    generated_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        Index('idx_regime_mission', 'mission_id'),
        Index('idx_regime_generated', 'generated_at'),
        Index('idx_regime_type', 'regime'),
    )
    
    # Relationships
    mission = relationship("MissionRecord", back_populates="regime_reports")


class SignalCandidateRecord(Base):
    """Persistent signal candidate storage."""
    __tablename__ = "signal_candidates"
    
    id = Column(String(36), primary_key=True)
    mission_id = Column(String(36), ForeignKey("missions.id"), nullable=False, index=True)
    
    # Candidate identification
    symbol = Column(String(20), nullable=False, index=True)
    strategy_id = Column(String(50), nullable=False, index=True)
    strategy_name = Column(String(100), nullable=False)
    strategy_version = Column(String(20), nullable=False)
    strategy_grade = Column(String(10), nullable=False)
    strategy_score = Column(Float, nullable=False)
    
    # Direction and confidence
    direction = Column(String(10), nullable=False, index=True)  # BUY, SELL, WAIT
    confidence = Column(Float, nullable=False, index=True)
    readiness_score = Column(Float, nullable=False)
    status = Column(String(30), nullable=False, index=True)  # GENERATED, WAITING_CONFIRMATION, REJECTED
    
    # Trade management
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)
    risk_reward = Column(Float, nullable=False)
    
    # Market snapshot
    trend = Column(String(20), nullable=False)
    volatility = Column(String(20), nullable=False)
    session = Column(String(50), nullable=False)
    spread = Column(Float, nullable=False)
    news_impact = Column(String(20), nullable=False)
    market_sentiment = Column(String(20), nullable=False)
    market_confidence = Column(Float, nullable=False)
    
    # Reasons and conditions
    reasons = Column(JSON, nullable=False, default=list)
    conditions = Column(JSON, nullable=False, default=list)
    confidence_breakdown = Column(JSON, nullable=False)
    
    # Timing
    evaluation_duration_ms = Column(Integer, nullable=False)
    market_data_age_seconds = Column(Integer, nullable=False)
    generated_at = Column(DateTime, nullable=False, index=True)
    evaluation_started_at = Column(DateTime, nullable=False)
    evaluation_completed_at = Column(DateTime, nullable=False)
    
    # Metadata
    engine_version = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        Index('idx_candidate_mission_symbol', 'mission_id', 'symbol'),
        Index('idx_candidate_status_confidence', 'status', 'confidence'),
        Index('idx_candidate_strategy', 'strategy_id'),
        Index('idx_candidate_generated', 'generated_at'),
    )
    
    # Relationships
    mission = relationship("MissionRecord", back_populates="candidates")
    validations = relationship("ValidationResultRecord", back_populates="candidate", cascade="all, delete-orphan")
    risk_assessments = relationship("RiskAssessmentRecord", back_populates="candidate", cascade="all, delete-orphan")
    execution_readiness_items = relationship("ExecutionReadinessRecord", back_populates="candidate", cascade="all, delete-orphan")
    decisions = relationship("DecisionArtifactRecord", back_populates="candidate", cascade="all, delete-orphan")


class ValidationResultRecord(Base):
    """Persistent validation result storage."""
    __tablename__ = "validation_results"
    
    id = Column(String(36), primary_key=True)
    mission_id = Column(String(36), ForeignKey("missions.id"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("signal_candidates.id"), nullable=False, index=True)
    
    # Validation identification
    strategy_id = Column(String(50), nullable=False, index=True)
    strategy_name = Column(String(100), nullable=False)
    strategy_version = Column(String(20), nullable=False)
    
    # Validation outcome
    status = Column(String(20), nullable=False, index=True)  # PASSED, PARTIALLY_PASSED, FAILED
    validation_score = Column(Integer, nullable=False, index=True)
    
    # Summary
    total_checks = Column(Integer, nullable=False)
    passed_checks = Column(Integer, nullable=False)
    failed_checks = Column(Integer, nullable=False)
    mandatory_passed = Column(Integer, nullable=False)
    mandatory_failed = Column(Integer, nullable=False)
    validation_percentage = Column(Integer, nullable=False)
    
    # Detailed checks
    checks = Column(JSON, nullable=False, default=list)
    
    # Timing
    validated_at = Column(DateTime, nullable=False, index=True)
    validation_duration_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        Index('idx_validation_mission_candidate', 'mission_id', 'candidate_id'),
        Index('idx_validation_status_score', 'status', 'validation_score'),
        Index('idx_validation_strategy', 'strategy_id'),
    )
    
    # Relationships
    mission = relationship("MissionRecord", back_populates="validations")
    candidate = relationship("SignalCandidateRecord", back_populates="validations")


class RiskAssessmentRecord(Base):
    """Persistent risk assessment storage."""
    __tablename__ = "risk_assessments"
    
    id = Column(String(36), primary_key=True)
    mission_id = Column(String(36), ForeignKey("missions.id"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("signal_candidates.id"), nullable=False, index=True)
    validation_id = Column(String(36), ForeignKey("validation_results.id"), nullable=False, index=True)
    strategy_id = Column(String(50), nullable=False, index=True)
    
    # Risk outcome
    status = Column(String(20), nullable=False, index=True)  # PASSED, REVIEW_REQUIRED, BLOCKED
    overall_risk_score = Column(Integer, nullable=False, index=True)
    risk_level = Column(String(20), nullable=False, index=True)  # LOW, MEDIUM, HIGH, EXTREME
    
    # Thresholds
    low_max = Column(Integer, nullable=False)
    medium_max = Column(Integer, nullable=False)
    high_max = Column(Integer, nullable=False)
    extreme_max = Column(Integer, nullable=False)
    
    # Category scores
    category_scores = Column(JSON, nullable=False, default=list)
    
    # Reasons
    reasons = Column(JSON, nullable=False, default=list)
    
    # Recommendation
    recommendation_action = Column(String(20), nullable=False)
    recommendation_title = Column(String(100), nullable=False)
    recommendation_description = Column(Text, nullable=False)
    
    # Market snapshot
    trend = Column(String(20), nullable=False)
    volatility = Column(String(20), nullable=False)
    session = Column(String(50), nullable=False)
    spread = Column(Float, nullable=False)
    news_impact = Column(String(20), nullable=False)
    market_sentiment = Column(String(20), nullable=False)
    
    # Timing
    assessed_at = Column(DateTime, nullable=False, index=True)
    assessment_duration_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        Index('idx_risk_mission_candidate', 'mission_id', 'candidate_id'),
        Index('idx_risk_level_score', 'risk_level', 'overall_risk_score'),
        Index('idx_risk_status', 'status'),
    )
    
    # Relationships
    mission = relationship("MissionRecord", back_populates="risk_assessments")
    candidate = relationship("SignalCandidateRecord", back_populates="risk_assessments")


class ExecutionReadinessRecord(Base):
    """Persistent execution readiness storage."""
    __tablename__ = "execution_readiness"
    
    id = Column(String(36), primary_key=True)
    mission_id = Column(String(36), ForeignKey("missions.id"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("signal_candidates.id"), nullable=False, index=True)
    validation_id = Column(String(36), nullable=False, index=True)
    risk_assessment_id = Column(String(36), nullable=False, index=True)
    strategy_id = Column(String(50), nullable=False, index=True)
    
    # Readiness outcome
    status = Column(String(20), nullable=False, index=True)  # READY, WAIT, BLOCKED
    overall_readiness_score = Column(Integer, nullable=False, index=True)
    
    # Thresholds
    ready_min = Column(Integer, nullable=False)
    wait_min = Column(Integer, nullable=False)
    blocked_min = Column(Integer, nullable=False)
    
    # Category scores
    category_scores = Column(JSON, nullable=False, default=list)
    
    # Reasons
    reasons = Column(JSON, nullable=False, default=list)
    
    # Recommendation
    action = Column(String(20), nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    next_review_in = Column(String(100), nullable=False)
    
    # Market snapshot
    session = Column(String(50), nullable=False)
    spread = Column(Float, nullable=False)
    volatility = Column(String(20), nullable=False)
    news_impact = Column(String(20), nullable=False)
    market_sentiment = Column(String(20), nullable=False)
    market_confidence = Column(Float, nullable=False)
    market_open = Column(Boolean, nullable=False)
    data_age_seconds = Column(Integer, nullable=False)
    
    # Candidate status context
    candidate_status = Column(String(30), nullable=False)
    validation_status = Column(String(20), nullable=False)
    risk_level = Column(String(20), nullable=False)
    risk_status = Column(String(20), nullable=False)
    
    # Timing
    evaluated_at = Column(DateTime, nullable=False, index=True)
    evaluation_duration_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        Index('idx_execution_mission_candidate', 'mission_id', 'candidate_id'),
        Index('idx_execution_status_score', 'status', 'overall_readiness_score'),
    )
    
    # Relationships
    mission = relationship("MissionRecord", back_populates="execution_readiness_items")
    candidate = relationship("SignalCandidateRecord", back_populates="execution_readiness_items")


class DecisionArtifactRecord(Base):
    """Persistent decision artifact storage."""
    __tablename__ = "decision_artifacts"
    
    id = Column(String(36), primary_key=True)
    mission_id = Column(String(36), ForeignKey("missions.id"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("signal_candidates.id"), nullable=False, index=True)
    validation_id = Column(String(36), nullable=False)
    risk_assessment_id = Column(String(36), nullable=False)
    execution_readiness_id = Column(String(36), nullable=False)
    strategy_id = Column(String(50), nullable=False, index=True)
    
    # Decision outcome
    recommendation = Column(String(10), nullable=False, index=True)  # BUY, SELL, WAIT, NO_TRADE, MONITOR
    status = Column(String(20), nullable=False, index=True)  # APPROVED, REJECTED, PENDING, MONITORING
    decision_confidence = Column(Float, nullable=False, index=True)
    priority = Column(String(10), nullable=False)  # CRITICAL, HIGH, MEDIUM, LOW
    
    # Decision details
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    expected_holding = Column(String(50), nullable=False)
    next_review_in = Column(String(50), nullable=False)
    mission_status = Column(String(20), nullable=False)
    
    # Decision trace
    decision_trace = Column(JSON, nullable=False, default=list)
    supporting_factors = Column(JSON, nullable=False, default=list)
    blocking_factors = Column(JSON, nullable=False, default=list)
    watch_items = Column(JSON, nullable=False, default=list)
    
    # Pipeline summary
    pipeline_summary = Column(JSON, nullable=False)
    
    # Market snapshot
    market_snapshot = Column(JSON, nullable=False)
    
    # Generated decision (from DecisionGenerator)
    generated_decision = Column(JSON, nullable=True)
    
    # Mission verdict
    mission_verdict = Column(JSON, nullable=False)
    
    # Metadata
    strategy_name = Column(String(100), nullable=False)
    strategy_version = Column(String(20), nullable=False)
    artifact_type = Column(String(20), nullable=False)
    pipeline_stage = Column(String(20), nullable=False)
    pipeline_version = Column(String(20), nullable=False)
    engine_version = Column(String(20), nullable=False)
    decision_logic_version = Column(String(50), nullable=False)
    decided_by = Column(String(50), nullable=False)
    decided_at = Column(DateTime, nullable=False, index=True)
    decision_duration_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        Index('idx_decision_mission_candidate', 'mission_id', 'candidate_id'),
        Index('idx_decision_recommendation_confidence', 'recommendation', 'decision_confidence'),
        Index('idx_decision_status', 'status'),
        Index('idx_decision_decided', 'decided_at'),
    )
    
    # Relationships
    mission = relationship("MissionRecord", back_populates="decisions")
    candidate = relationship("SignalCandidateRecord", back_populates="decisions")


class ProviderHealthRecord(Base):
    """Persistent provider health snapshot storage."""
    __tablename__ = "provider_health_snapshots"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mission_id = Column(String(36), ForeignKey("missions.id"), nullable=False, index=True)
    
    # Provider identification
    provider_id = Column(String(50), nullable=False, index=True)
    provider_name = Column(String(100), nullable=False)
    provider_type = Column(String(20), nullable=False)
    
    # Health status
    status = Column(String(20), nullable=False, index=True)  # ONLINE, OFFLINE, DEGRADED, RATE_LIMITED
    health = Column(String(20), nullable=False, index=True)  # HEALTHY, WARNING, CRITICAL
    
    # Statistics
    total_requests = Column(Integer, nullable=False, default=0)
    successful_requests = Column(Integer, nullable=False, default=0)
    failed_requests = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=100.0)
    
    # Circuit breaker state
    circuit_breaker_state = Column(String(20), nullable=False)
    circuit_open_count = Column(Integer, nullable=False, default=0)
    circuit_close_count = Column(Integer, nullable=False, default=0)
    recovery_count = Column(Integer, nullable=False, default=0)
    circuit_retry_in_seconds = Column(Float, nullable=True)
    
    # Performance
    avg_success_latency_ms = Column(Float, nullable=False, default=0.0)
    avg_failure_latency_ms = Column(Float, nullable=False, default=0.0)
    uptime_percent = Column(Float, nullable=False, default=100.0)
    consecutive_successes = Column(Integer, nullable=False, default=0)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    http_429_count = Column(Integer, nullable=False, default=0)
    timeout_count = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    last_success_at = Column(DateTime, nullable=True)
    last_failure_at = Column(DateTime, nullable=True)
    last_successful_quote_at = Column(DateTime, nullable=True)
    last_failed_request_at = Column(DateTime, nullable=True)
    snapshot_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        Index('idx_provider_health_mission', 'mission_id'),
        Index('idx_provider_health_status', 'provider_id', 'status'),
        Index('idx_provider_health_snapshot', 'snapshot_at'),
    )
    
    # Relationships
    mission = relationship("MissionRecord", back_populates="provider_health_snapshots")


class MissionTimelineRecord(Base):
    """Persistent mission timeline event storage."""
    __tablename__ = "mission_timeline"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mission_id = Column(String(36), ForeignKey("missions.id"), nullable=False, index=True)
    
    # Event details
    stage = Column(String(30), nullable=False, index=True)
    artifact_id = Column(String(36), nullable=False, index=True)
    status = Column(String(20), nullable=False)  # COMPLETED, SKIPPED, FAILED
    timeline_order = Column(Integer, nullable=False)
    
    # Timing
    started_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=False, index=True)
    duration_ms = Column(Integer, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        Index('idx_timeline_mission_stage', 'mission_id', 'stage'),
        Index('idx_timeline_completed', 'completed_at'),
    )
    
    # Relationships
    mission = relationship("MissionRecord", back_populates="timeline_events")


class AuditMetadataRecord(Base):
    """Audit metadata for mission lifecycle events."""
    __tablename__ = "audit_metadata"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mission_id = Column(String(36), ForeignKey("missions.id"), nullable=False, index=True)
    
    # Audit event
    event_type = Column(String(50), nullable=False, index=True)  # MISSION_CREATED, MISSION_COMPLETED, MISSION_ARCHIVED
    event_description = Column(Text, nullable=False)
    
    # Actor (system or user)
    actor = Column(String(50), nullable=False, default="system")
    
    # Event data
    event_data = Column(JSON, nullable=False, default=dict)
    
    # Timestamp
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    __table_args__ = (
        Index('idx_audit_mission_event', 'mission_id', 'event_type'),
        Index('idx_audit_created', 'created_at'),
    )
    
    # Relationships
    mission = relationship("MissionRecord")