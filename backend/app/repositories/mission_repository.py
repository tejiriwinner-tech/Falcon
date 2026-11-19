"""
Falcon Mission Repository
Persistent SQLAlchemy-backed repository for mission storage.

Replaces the in-memory MissionRepository with database-backed persistence.
"""
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from app.models.mission_models import (
    MissionRecord,
    MarketStateRecord,
    MarketRegimeRecord,
    SignalCandidateRecord,
    ValidationResultRecord,
    RiskAssessmentRecord,
    ExecutionReadinessRecord,
    DecisionArtifactRecord,
    ProviderHealthRecord,
    MissionTimelineRecord,
    AuditMetadataRecord,
)
from app.schemas.mission_report import MissionReport, MissionStatus

logger = logging.getLogger(__name__)

def serialize_datetime(obj):
    """Recursively convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        return serialize_datetime(obj.__dict__)
    elif hasattr(obj, '_value_'):  # Handle enum-like objects
        return str(obj._value_)
    elif hasattr(obj, '_name_'):  # Handle enum names
        return str(obj._name_)
    else:
        try:
            # Try to convert to string, but keep None as None
            return str(obj) if obj is not None else None
        except:
            return None


class MissionRepository:
    """Persistent mission repository using SQLAlchemy.
    
    Provides CRUD operations for missions and all pipeline artifacts.
    Ensures mission history survives application restart.
    """

    def __init__(self, db: Session):
        """
        Initialize mission repository.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def save_mission(self, mission: MissionReport) -> str:
        """
        Save a complete mission with all artifacts.

        Uses merge (upsert) on the primary key so re-saves on repeated
        validation runs are idempotent. Also purges any existing row that
        holds the same mission_number (unique secondary key) to prevent
        IntegrityError when the orchestrator counter resets.

        Args:
            mission: MissionReport to persist

        Returns:
            mission_id if successful
        """
        try:
            mission_id = mission.id

            # Remove any existing mission with the same mission_number
            # (unique secondary key) that has a different primary key.
            # This handles the case where a prior run already wrote a row
            # with the same sequential number.
            try:
                existing = (
                    self.db.query(MissionRecord)
                    .filter(
                        MissionRecord.mission_number == mission.missionNumber,
                        MissionRecord.id != mission_id,
                    )
                    .first()
                )
                if existing:
                    self.db.delete(existing)
                    self.db.flush()
            except Exception:
                pass  # Non-fatal; the merge below will surface any real error

            # Handle UNIQUE constraint on mission_number by finding the next available number
            # if the current one is already taken
            try:
                existing_with_same_number = (
                    self.db.query(MissionRecord)
                    .filter(MissionRecord.mission_number == mission.missionNumber)
                    .first()
                )
                if existing_with_same_number and existing_with_same_number.id != mission_id:
                    # Find the next available mission number
                    from sqlalchemy import func
                    max_num = self.db.query(func.max(MissionRecord.mission_number)).scalar()
                    mission_number = (max_num + 1) if max_num is not None else mission.missionNumber
                else:
                    mission_number = mission.missionNumber
            except Exception:
                mission_number = mission.missionNumber

            # Create mission record
            mission_record = MissionRecord(
                id=mission_id,
                mission_number=mission_number,
                status=mission.status.value,
                started_at=mission.startedAt,
                completed_at=mission.completedAt,
                total_duration_ms=mission.performance.totalDurationMs,
                market_duration_ms=mission.performance.marketDurationMs,
                regime_duration_ms=mission.performance.regimeDurationMs,
                signal_duration_ms=mission.performance.signalDurationMs,
                validation_duration_ms=mission.performance.validationDurationMs,
                risk_duration_ms=mission.performance.riskDurationMs,
                execution_duration_ms=mission.performance.executionDurationMs,
                decision_duration_ms=mission.performance.decisionDurationMs,
                average_stage_duration_ms=mission.performance.averageStageDurationMs,
                pipeline_health_percentage=mission.health.pipelineHealthPercentage,
                provider_health_percentage=mission.health.providerHealthPercentage,
                engines_healthy=mission.health.enginesHealthy,
                providers_healthy=mission.health.providersHealthy,
                warnings=mission.health.warnings,
                market_state_count=mission.pipelineSummary.marketStateCount,
                regime_count=mission.pipelineSummary.regimeCount,
                candidate_count=mission.pipelineSummary.candidateCount,
                validation_count=mission.pipelineSummary.validationCount,
                risk_assessment_count=mission.pipelineSummary.riskAssessmentCount,
                execution_readiness_count=mission.pipelineSummary.executionReadinessCount,
                decision_count=mission.pipelineSummary.decisionCount,
                pipeline_version=mission.pipelineVersion,
                engine_version=mission.engineVersion,
                generated_by=mission.generatedBy,
            )
            
            self.db.merge(mission_record)

            # Save timeline events
            for event in mission.timeline:
                timeline_record = MissionTimelineRecord(
                    mission_id=mission_id,
                    stage=event.stage,
                    artifact_id=event.artifactId,
                    status=event.status.value,
                    timeline_order=event.timelineOrder,
                    started_at=event.startedAt,
                    completed_at=event.completedAt,
                    duration_ms=event.durationMs,
                )
                self.db.add(timeline_record)
            
            # Save provider health snapshots (placeholder - would be populated by orchestrator)
            provider_health_record = ProviderHealthRecord(
                mission_id=mission_id,
                provider_id="system",
                provider_name="System",
                provider_type="SYSTEM",
                status="ONLINE",
                health="HEALTHY",
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                success_rate=100.0,
                circuit_breaker_state="CLOSED",
                circuit_open_count=0,
                circuit_close_count=0,
                recovery_count=0,
                avg_success_latency_ms=0.0,
                avg_failure_latency_ms=0.0,
                uptime_percent=100.0,
                consecutive_successes=0,
                consecutive_failures=0,
                http_429_count=0,
                timeout_count=0,
                snapshot_at=datetime.now(timezone.utc),
            )
            self.db.add(provider_health_record)
            
            # Save audit metadata
            audit_record = AuditMetadataRecord(
                mission_id=mission_id,
                event_type="MISSION_COMPLETED",
                event_description=f"Mission {mission_id} completed with status {mission.status.value}",
                actor="system",
                event_data={
                    "status": mission.status.value,
                    "duration_ms": mission.performance.totalDurationMs,
                    "decisions": mission.pipelineSummary.decisionCount,
                },
            )
            self.db.add(audit_record)
            
            self.db.commit()
            logger.info(f"Mission {mission_id} saved successfully")
            return mission_id
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save mission: {str(e)}", exc_info=True)
            raise

    def save_market_state(self, mission_id: str, market_state) -> str:
        """
        Save market state for a mission.
        
        Args:
            mission_id: Mission identifier
            market_state: MarketState object
            
        Returns:
            market_state_id if successful
        """
        try:
            market_state_id = getattr(market_state, 'id', f"market-{int(market_state.timestamp.timestamp())}")
            
            # Use first symbol as primary symbol for this record
            primary_symbol = list(market_state.prices.keys())[0] if market_state.prices else "UNKNOWN"
            primary_price = market_state.prices.get(primary_symbol)
            
            record = MarketStateRecord(
                id=market_state_id,
                mission_id=mission_id,
                symbol=primary_symbol,
                current_price=primary_price.currentPrice if primary_price else 0.0,
                bid=primary_price.bid if primary_price else 0.0,
                ask=primary_price.ask if primary_price else 0.0,
                spread=primary_price.spread if primary_price else 0.0,
                timestamp=market_state.timestamp,
                provider=primary_price.provider if primary_price else "Unknown",
                trend=market_state.trend,
                volatility=market_state.volatility,
                liquidity=market_state.liquidity,
                session=market_state.session,
                market_open=market_state.marketOpen,
                market_sentiment_label=market_state.marketSentimentLabel,
                fear_greed_index=market_state.fearGreedIndex,
                current_news_impact=market_state.currentNewsImpact,
                upcoming_high_impact_news=market_state.upcomingHighImpactNews,
                data_age_seconds=market_state.dataAgeSeconds,
                overall_market_confidence=market_state.overallMarketConfidence,
                quote_status=market_state.quoteStatus,
                freshness_seconds=market_state.freshnessSeconds,
                primary_provider_id=market_state.primaryProviderId,
                primary_provider_name=market_state.primaryProviderName,
                watchlist_symbols=market_state.watchlistSymbols,
                data_source=market_state.dataSource,
            )
            
            self.db.add(record)
            self.db.commit()
            return market_state_id
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save market state: {str(e)}", exc_info=True)
            raise

    def save_regime_reports(self, mission_id: str, regime_reports: List) -> None:
        """
        Save market regime reports for a mission.
        
        Args:
            mission_id: Mission identifier
            regime_reports: List of MarketRegimeReport objects
        """
        try:
            for report in regime_reports:
                # Convert regime enum to string safely
                regime_str = report.regime.value if hasattr(report.regime, 'value') else str(report.regime)
                
                # Convert confidence enum or string to float safely for DB column
                raw_conf = report.confidence.value if hasattr(report.confidence, 'value') else report.confidence
                try:
                    conf_float = float(raw_conf)
                except (ValueError, TypeError):
                    conf_map = {"LOW": 0.25, "MEDIUM": 0.5, "HIGH": 0.75, "VERY_HIGH": 1.0}
                    conf_float = conf_map.get(str(raw_conf).upper(), 0.5)

                record = MarketRegimeRecord(
                    mission_id=mission_id,
                    regime=regime_str,
                    confidence=conf_float,
                    description=report.recommendation.description,
                    supporting_factors=[sf.dict() for sf in getattr(report, 'supportingFactors', getattr(report, 'factors', []))],
                    risk_factors=[rf.dict() for rf in getattr(report, 'riskFactors', [])],
                    trend_alignment=getattr(report, 'trendAlignment', getattr(getattr(report, 'snapshot', None), 'trend', 'UNKNOWN')),
                    volatility_assessment=getattr(report, 'volatilityAssessment', getattr(getattr(report, 'snapshot', None), 'volatility', 'UNKNOWN')),
                    liquidity_status=getattr(report, 'liquidityStatus', 'UNKNOWN'),
                    generated_at=report.generatedAt,
                )
                self.db.add(record)
            
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save regime reports: {str(e)}", exc_info=True)
            raise

    def save_candidates(self, mission_id: str, candidates: List) -> None:
        """
        Save signal candidates for a mission.
        
        Args:
            mission_id: Mission identifier
            candidates: List of SignalCandidate objects
        """
        try:
            for candidate in candidates:
                # Check if candidate ID already exists and handle collision
                existing = self.db.query(SignalCandidateRecord).filter(SignalCandidateRecord.id == candidate.id).first()
                if existing:
                    # Generate a new unique ID by appending mission_id and timestamp
                    import time
                    candidate.id = f"{candidate.id}-{mission_id[:8]}-{int(time.time() * 1000) % 10000:04d}"
                
                record = SignalCandidateRecord(
                    id=candidate.id,
                    mission_id=mission_id,
                    symbol=candidate.symbol,
                    strategy_id=candidate.strategyId,
                    strategy_name=candidate.strategyName,
                    strategy_version=candidate.strategyVersion,
                    strategy_grade=candidate.strategyGrade,
                    strategy_score=candidate.strategyScore,
                    direction=candidate.direction.value if hasattr(candidate.direction, 'value') else str(candidate.direction),
                    confidence=candidate.confidence,
                    readiness_score=candidate.readinessScore,
                    status=candidate.status.value if hasattr(candidate.status, 'value') else str(candidate.status),
                    entry_price=candidate.entryPrice,
                    stop_loss=candidate.stopLoss,
                    take_profit=candidate.takeProfit,
                    risk_reward=candidate.riskReward,
                    trend=candidate.marketSnapshot.trend,
                    volatility=candidate.marketSnapshot.volatility,
                    session=candidate.marketSnapshot.session,
                    spread=candidate.marketSnapshot.spread,
                    news_impact=candidate.marketSnapshot.newsImpact,
                    market_sentiment=candidate.marketSnapshot.marketSentiment,
                    market_confidence=candidate.marketSnapshot.marketConfidence,
                    reasons=serialize_datetime([r.dict() for r in candidate.reasons]),
                    conditions=serialize_datetime([c.dict() for c in candidate.conditions]),
                    confidence_breakdown=serialize_datetime(candidate.confidenceBreakdown.dict()),
                    evaluation_duration_ms=candidate.evaluationDurationMs,
                    market_data_age_seconds=candidate.marketDataAgeSeconds,
                    generated_at=candidate.generatedAt,
                    evaluation_started_at=candidate.evaluationStartedAt,
                    evaluation_completed_at=candidate.evaluationCompletedAt,
                    engine_version=candidate.engineVersion,
                )
                self.db.add(record)
            
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save candidates: {str(e)}", exc_info=True)
            raise

    def save_validations(self, mission_id: str, validations: List) -> None:
        """
        Save validation results for a mission.
        
        Args:
            mission_id: Mission identifier
            validations: List of ValidationResult objects
        """
        try:
            for validation in validations:
                # Check if validation ID already exists and handle collision
                existing = self.db.query(ValidationResultRecord).filter(ValidationResultRecord.id == validation.id).first()
                if existing:
                    # Generate a new unique ID by appending mission_id and timestamp
                    import time
                    validation.id = f"{validation.id}-{mission_id[:8]}-{int(time.time() * 1000) % 10000:04d}"
                
                record = ValidationResultRecord(
                    id=validation.id,
                    mission_id=mission_id,
                    candidate_id=validation.candidateId,
                    strategy_id=validation.strategyId,
                    strategy_name=validation.strategyName,
                    strategy_version=validation.strategyVersion,
                    status=validation.status.value if hasattr(validation.status, 'value') else str(validation.status),
                    validation_score=validation.validationScore,
                    total_checks=validation.summary.totalChecks,
                    passed_checks=validation.summary.passedChecks,
                    failed_checks=validation.summary.failedChecks,
                    mandatory_passed=validation.summary.mandatoryPassed,
                    mandatory_failed=validation.summary.mandatoryFailed,
                    validation_percentage=validation.summary.validationPercentage,
                    checks=serialize_datetime([c.dict() for c in validation.checks]),
                    validated_at=validation.validatedAt,
                    validation_duration_ms=validation.validationDurationMs,
                )
                self.db.add(record)
            
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save validations: {str(e)}", exc_info=True)
            raise

    def save_risk_assessments(self, mission_id: str, assessments: List) -> None:
        """
        Save risk assessments for a mission.
        
        Args:
            mission_id: Mission identifier
            assessments: List of RiskAssessment objects
        """
        try:
            for assessment in assessments:
                # Check if risk assessment ID already exists and handle collision
                existing = self.db.query(RiskAssessmentRecord).filter(RiskAssessmentRecord.id == assessment.id).first()
                if existing:
                    # Generate a new unique ID by appending mission_id and timestamp
                    import time
                    assessment.id = f"{assessment.id}-{mission_id[:8]}-{int(time.time() * 1000) % 10000:04d}"
                
                record = RiskAssessmentRecord(
                    id=assessment.id,
                    mission_id=mission_id,
                    candidate_id=assessment.candidateId,
                    validation_id=assessment.validationId,
                    strategy_id=assessment.strategyId,
                    status=assessment.status.value if hasattr(assessment.status, 'value') else str(assessment.status),
                    overall_risk_score=assessment.overallRiskScore,
                    risk_level=assessment.riskLevel.value if hasattr(assessment.riskLevel, 'value') else str(assessment.riskLevel),
                    low_max=assessment.thresholds.lowMax,
                    medium_max=assessment.thresholds.mediumMax,
                    high_max=assessment.thresholds.highMax,
                    extreme_max=assessment.thresholds.extremeMax,
                    category_scores=serialize_datetime([cs.dict() for cs in assessment.categoryScores]),
                    reasons=serialize_datetime([r.dict() for r in assessment.reasons]),
                    recommendation_action=assessment.recommendation.action.value if hasattr(assessment.recommendation.action, 'value') else str(assessment.recommendation.action),
                    recommendation_title=assessment.recommendation.title,
                    recommendation_description=assessment.recommendation.description,
                    trend=assessment.marketSnapshot.trend,
                    volatility=assessment.marketSnapshot.volatility,
                    session=assessment.marketSnapshot.session,
                    spread=assessment.marketSnapshot.spread,
                    news_impact=assessment.marketSnapshot.newsImpact,
                    market_sentiment=assessment.marketSnapshot.marketSentiment,
                    assessed_at=assessment.assessedAt,
                    assessment_duration_ms=assessment.assessmentDurationMs,
                )
                self.db.add(record)
            
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save risk assessments: {str(e)}", exc_info=True)
            raise

    def save_execution_readiness(self, mission_id: str, readiness_items: List) -> None:
        """
        Save execution readiness items for a mission.
        
        Args:
            mission_id: Mission identifier
            readiness_items: List of ExecutionReadiness objects
        """
        try:
            for readiness in readiness_items:
                # Check if execution readiness ID already exists and handle collision
                existing = self.db.query(ExecutionReadinessRecord).filter(ExecutionReadinessRecord.id == readiness.id).first()
                if existing:
                    # Generate a new unique ID by appending mission_id and timestamp
                    import time
                    readiness.id = f"{readiness.id}-{mission_id[:8]}-{int(time.time() * 1000) % 10000:04d}"
                
                record = ExecutionReadinessRecord(
                    id=readiness.id,
                    mission_id=mission_id,
                    candidate_id=readiness.candidateId,
                    validation_id=readiness.validationId,
                    risk_assessment_id=readiness.riskAssessmentId,
                    strategy_id=readiness.strategyId,
                    status=readiness.status.value if hasattr(readiness.status, 'value') else str(readiness.status),
                    overall_readiness_score=readiness.overallReadinessScore,
                    ready_min=readiness.thresholds.readyMin,
                    wait_min=readiness.thresholds.waitMin,
                    blocked_min=readiness.thresholds.blockedMin,
                    category_scores=serialize_datetime([cs.dict() for cs in readiness.categoryScores]),
                    reasons=serialize_datetime([r.dict() for r in readiness.reasons]),
                    action=readiness.recommendation.action.value if hasattr(readiness.recommendation.action, 'value') else str(readiness.recommendation.action),
                    title=readiness.recommendation.title,
                    description=readiness.recommendation.description,
                    next_review_in=readiness.recommendation.nextReviewIn,
                    session=readiness.marketSnapshot.session,
                    spread=readiness.marketSnapshot.spread,
                    volatility=readiness.marketSnapshot.volatility,
                    news_impact=readiness.marketSnapshot.newsImpact,
                    market_sentiment=readiness.marketSnapshot.marketSentiment,
                    market_confidence=readiness.marketSnapshot.marketConfidence,
                    market_open=readiness.marketSnapshot.marketOpen,
                    data_age_seconds=readiness.marketSnapshot.dataAgeSeconds,
                    candidate_status=readiness.candidateStatus.value if hasattr(readiness.candidateStatus, 'value') else str(readiness.candidateStatus),
                    validation_status=readiness.validationStatus.value if hasattr(readiness.validationStatus, 'value') else str(readiness.validationStatus),
                    risk_level=readiness.riskLevel.value if hasattr(readiness.riskLevel, 'value') else str(readiness.riskLevel),
                    risk_status=readiness.riskStatus.value if hasattr(readiness.riskStatus, 'value') else str(readiness.riskStatus),
                    evaluated_at=readiness.evaluatedAt,
                    evaluation_duration_ms=readiness.evaluationDurationMs,
                )
                self.db.add(record)
            
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save execution readiness: {str(e)}", exc_info=True)
            raise

    def save_decisions(self, mission_id: str, decisions: List) -> None:
        """
        Save decision artifacts for a mission.
        
        Args:
            mission_id: Mission identifier
            decisions: List of DecisionArtifact objects
        """
        try:
            for decision in decisions:
                # Check if decision ID already exists and handle collision
                existing = self.db.query(DecisionArtifactRecord).filter(DecisionArtifactRecord.id == decision.id).first()
                if existing:
                    # Generate a new unique ID by appending mission_id and timestamp
                    import time
                    decision.id = f"{decision.id}-{mission_id[:8]}-{int(time.time() * 1000) % 10000:04d}"
                
                record = DecisionArtifactRecord(
                    id=decision.id,
                    mission_id=mission_id,
                    candidate_id=decision.candidateId,
                    validation_id=decision.validationId,
                    risk_assessment_id=decision.riskAssessmentId,
                    execution_readiness_id=decision.executionReadinessId,
                    strategy_id=decision.strategyId,
                    recommendation=decision.recommendation.value if hasattr(decision.recommendation, 'value') else str(decision.recommendation),
                    status=decision.status.value if hasattr(decision.status, 'value') else str(decision.status),
                    decision_confidence=decision.decisionConfidence,
                    priority='MEDIUM',  # Default value since schema doesn't have priority field
                    title=decision.recommendationDetails.title,
                    description=decision.recommendationDetails.description,
                    expected_holding=decision.recommendationDetails.expectedHolding,
                    next_review_in=decision.recommendationDetails.nextReviewIn,
                    mission_status=decision.recommendationDetails.missionStatus,
                    decision_trace=serialize_datetime([dt.dict() if hasattr(dt, 'dict') else dt for dt in decision.decisionTrace]),
                    supporting_factors=serialize_datetime([sf.dict() if hasattr(sf, 'dict') else sf for sf in decision.supportingFactors]),
                    blocking_factors=serialize_datetime([bf.dict() if hasattr(bf, 'dict') else bf for bf in decision.blockingFactors]),
                    watch_items=serialize_datetime([wi.dict() if hasattr(wi, 'dict') else wi for wi in decision.watchItems]),
                    pipeline_summary=serialize_datetime(decision.pipelineSummary.dict() if hasattr(decision.pipelineSummary, 'dict') else decision.pipelineSummary),
                    market_snapshot=serialize_datetime(decision.marketSnapshot.dict() if hasattr(decision.marketSnapshot, 'dict') else decision.marketSnapshot),
                    generated_decision=serialize_datetime(decision.generatedDecision.dict()) if decision.generatedDecision and hasattr(decision.generatedDecision, 'dict') else None,
                    mission_verdict=serialize_datetime(decision.missionVerdict.dict() if hasattr(decision.missionVerdict, 'dict') else decision.missionVerdict),
                    strategy_name=decision.strategyName,
                    strategy_version=decision.strategyVersion,
                    artifact_type=decision.artifactType,
                    pipeline_stage=getattr(decision, 'pipelineStage', 'DECISION'),
                    pipeline_version=getattr(decision, 'pipelineVersion', '1.0'),
                    engine_version=getattr(decision, 'engineVersion', '1.0.0'),
                    decision_logic_version=getattr(decision, 'decisionLogicVersion', 'Captain Logic v1.0'),
                    decided_by=getattr(decision, 'decidedBy', 'Decision Engine'),
                    decided_at=getattr(decision, 'decidedAt', datetime.now(timezone.utc)) if isinstance(getattr(decision, 'decidedAt', None), datetime) else datetime.now(timezone.utc),
                    decision_duration_ms=getattr(decision, 'decisionDurationMs', 0),
                )
                self.db.add(record)
            
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save decisions: {str(e)}", exc_info=True)
            raise

    def get_mission(self, mission_id: str) -> Optional[MissionRecord]:
        """
        Get a mission by ID.
        
        Args:
            mission_id: Mission identifier
            
        Returns:
            MissionRecord if found, None otherwise
        """
        try:
            return self.db.query(MissionRecord)\
                .filter(MissionRecord.id == mission_id)\
                .first()
        except Exception as e:
            logger.error(f"Failed to get mission {mission_id}: {str(e)}", exc_info=True)
            return None

    def get_latest_missions(self, limit: int = 10) -> List[MissionRecord]:
        """
        Get the most recent missions.
        
        Args:
            limit: Maximum number of missions to return
            
        Returns:
            List of MissionRecord ordered by started_at descending
        """
        try:
            return self.db.query(MissionRecord)\
                .order_by(desc(MissionRecord.started_at))\
                .limit(limit)\
                .all()
        except Exception as e:
            logger.error(f"Failed to get latest missions: {str(e)}", exc_info=True)
            return []

    def get_missions_by_status(self, status: str, limit: int = 100) -> List[MissionRecord]:
        """
        Get missions by status.
        
        Args:
            status: Mission status (SUCCESS, PARTIAL_SUCCESS, FAILED)
            limit: Maximum number of missions to return
            
        Returns:
            List of MissionRecord with matching status
        """
        try:
            return self.db.query(MissionRecord)\
                .filter(MissionRecord.status == status)\
                .order_by(desc(MissionRecord.started_at))\
                .limit(limit)\
                .all()
        except Exception as e:
            logger.error(f"Failed to get missions by status {status}: {str(e)}", exc_info=True)
            return []

    def get_missions_by_timeframe(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[MissionRecord]:
        """
        Get missions within a time range.
        
        Args:
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            limit: Maximum number of missions to return
            
        Returns:
            List of MissionRecord within the time range
        """
        try:
            query = self.db.query(MissionRecord)\
                .filter(
                    and_(
                        MissionRecord.started_at >= start_time,
                        MissionRecord.started_at <= end_time
                    )
                )\
                .order_by(desc(MissionRecord.started_at))
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
        except Exception as e:
            logger.error(f"Failed to get missions by timeframe: {str(e)}", exc_info=True)
            return []

    def get_mission_artifacts(self, mission_id: str) -> Dict[str, Any]:
        """
        Get all artifacts for a mission.
        
        Args:
            mission_id: Mission identifier
            
        Returns:
            Dictionary with all mission artifacts
        """
        try:
            mission = self.get_mission(mission_id)
            if not mission:
                return {}
            
            market_states = self.db.query(MarketStateRecord)\
                .filter(MarketStateRecord.mission_id == mission_id)\
                .all()
            
            regime_reports = self.db.query(MarketRegimeRecord)\
                .filter(MarketRegimeRecord.mission_id == mission_id)\
                .all()
            
            candidates = self.db.query(SignalCandidateRecord)\
                .filter(SignalCandidateRecord.mission_id == mission_id)\
                .all()
            
            validations = self.db.query(ValidationResultRecord)\
                .filter(ValidationResultRecord.mission_id == mission_id)\
                .all()
            
            risk_assessments = self.db.query(RiskAssessmentRecord)\
                .filter(RiskAssessmentRecord.mission_id == mission_id)\
                .all()
            
            execution_readiness = self.db.query(ExecutionReadinessRecord)\
                .filter(ExecutionReadinessRecord.mission_id == mission_id)\
                .all()
            
            decisions = self.db.query(DecisionArtifactRecord)\
                .filter(DecisionArtifactRecord.mission_id == mission_id)\
                .all()
            
            return {
                "missionId": mission_id,
                "mission": mission,
                "marketStates": market_states,
                "regimeReports": regime_reports,
                "candidates": candidates,
                "validations": validations,
                "riskAssessments": risk_assessments,
                "executionReadiness": execution_readiness,
                "decisions": decisions,
            }
            
        except Exception as e:
            logger.error(f"Failed to get mission artifacts: {str(e)}", exc_info=True)
            return {}

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get repository statistics.
        
        Returns:
            Dictionary with mission statistics
        """
        try:
            total_missions = self.db.query(MissionRecord).count()
            
            if total_missions == 0:
                return {
                    'totalMissions': 0,
                    'successful': 0,
                    'partialSuccess': 0,
                    'failed': 0,
                    'averageDurationMs': 0.0,
                    'averagePipelineHealth': 0.0,
                }
            
            # Count by status
            successful = self.db.query(MissionRecord)\
                .filter(MissionRecord.status == MissionStatus.SUCCESS.value)\
                .count()
            partial_success = self.db.query(MissionRecord)\
                .filter(MissionRecord.status == MissionStatus.PARTIAL_SUCCESS.value)\
                .count()
            failed = self.db.query(MissionRecord)\
                .filter(MissionRecord.status == MissionStatus.FAILED.value)\
                .count()
            
            # Average duration
            avg_duration = self.db.query(func.avg(MissionRecord.total_duration_ms))\
                .scalar() or 0.0
            
            # Average pipeline health
            avg_health = self.db.query(func.avg(MissionRecord.pipeline_health_percentage))\
                .scalar() or 0.0
            
            return {
                'totalMissions': total_missions,
                'successful': successful,
                'partialSuccess': partial_success,
                'failed': failed,
                'averageDurationMs': round(avg_duration, 2),
                'averagePipelineHealth': round(avg_health, 2),
            }
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {str(e)}", exc_info=True)
            return {
                'totalMissions': 0,
                'successful': 0,
                'partialSuccess': 0,
                'failed': 0,
                'averageDurationMs': 0.0,
                'averagePipelineHealth': 0.0,
            }

    def delete_old_missions(self, older_than: datetime) -> int:
        """
        Delete missions older than a specified timestamp.
        
        Args:
            older_than: Delete missions with started_at older than this
            
        Returns:
            Number of missions deleted
        """
        from app.core.config import settings
        if not getattr(settings, "ENABLE_MISSION_AUTO_PRUNE", False):
            return 0
        try:
            deleted = self.db.query(MissionRecord)\
                .filter(MissionRecord.started_at < older_than)\
                .delete(synchronize_session=False)
            
            self.db.commit()
            logger.info(f"Deleted {deleted} old missions older than {older_than}")
            return deleted
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete old missions: {str(e)}", exc_info=True)
            return 0

    def get_mission_history(self, symbol: str, limit: int = 50) -> List[Dict]:
        """
        Get mission history for a specific symbol.
        
        Args:
            symbol: Trading symbol
            limit: Maximum number of records to return
            
        Returns:
            List of mission history dictionaries
        """
        try:
            # Query missions that have decisions for this symbol
            results = self.db.query(
                MissionRecord,
                DecisionArtifactRecord
            )\
            .join(DecisionArtifactRecord, MissionRecord.id == DecisionArtifactRecord.mission_id)\
            .filter(DecisionArtifactRecord.candidate_id.in_(
                self.db.query(SignalCandidateRecord.id)\
                    .filter(SignalCandidateRecord.symbol == symbol)
            ))\
            .order_by(desc(MissionRecord.started_at))\
            .limit(limit)\
            .all()
            
            history = []
            for mission, decision in results:
                history.append({
                    'missionId': mission.id,
                    'missionNumber': mission.mission_number,
                    'status': mission.status,
                    'startedAt': mission.started_at,
                    'completedAt': mission.completed_at,
                    'decisionId': decision.id,
                    'recommendation': decision.recommendation,
                    'confidence': decision.decision_confidence,
                    'symbol': symbol,
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get mission history for {symbol}: {str(e)}", exc_info=True)
            return []

    def exists(self, mission_id: str) -> bool:
        """
        Check if a mission exists.
        
        Args:
            mission_id: Mission identifier
            
        Returns:
            True if mission exists, False otherwise
        """
        try:
            return self.db.query(MissionRecord)\
                .filter(MissionRecord.id == mission_id)\
                .first() is not None
        except Exception as e:
            logger.error(f"Failed to check mission existence: {str(e)}", exc_info=True)
            return False

    def count(self) -> int:
        """
        Get total count of missions.
        
        Returns:
            Total number of missions
        """
        try:
            return self.db.query(MissionRecord).count()
        except Exception as e:
            logger.error(f"Failed to count missions: {str(e)}", exc_info=True)
            return 0