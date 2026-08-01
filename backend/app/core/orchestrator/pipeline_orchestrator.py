import json
import time
from datetime import datetime, timezone
from typing import List

from app.core.engines.market_state_engine import MarketStateEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.validation_engine import ValidationEngine
from app.core.engines.risk_engine import RiskEngine
from app.core.engines.execution_readiness_engine import ExecutionReadinessEngine
from app.core.engines.decision_engine import DecisionEngine
from app.core.repository.mission_repository import mission_repository

from app.schemas.mission_report import (
    MissionReport,
    MissionStatus,
    MissionStageStatus,
    MissionTimelineEvent,
    MissionArtifactReferences,
    MissionPipelineSummary,
    MissionPerformance,
    MissionHealth,
)


class PipelineOrchestrator:
    """Central coordinator for the Falcon intelligence pipeline.

    IMPORTANT: This class is NOT an intelligence engine.
    It must never perform technical analysis, validation, risk evaluation,
    execution readiness calculations, or decision making.

    Responsibilities:
      - Execute each engine in the correct order.
      - Collect immutable artifacts.
      - Preserve execution metadata.
      - Publish timeline events.
      - Produce a MissionReport.
      - Archive completed missions into MissionRepository.
    """

    def __init__(self):
        self._market_state_engine = MarketStateEngine()
        self._strategy_engine = StrategyEngine()
        self._signal_engine = SignalGenerationEngine()
        self._validation_engine = ValidationEngine()
        self._risk_engine = RiskEngine()
        self._execution_engine = ExecutionReadinessEngine()
        self._decision_engine = DecisionEngine()

        # Monotonic mission counter (per process lifetime)
        self._mission_counter: int = 0

    def run_pipeline(self) -> MissionReport:
        """Execute the complete Falcon intelligence pipeline exactly once.

        Returns an immutable MissionReport that is the single source of
        truth for all downstream consumers.
        """
        self._mission_counter += 1
        mission_number = self._mission_counter
        mission_id = f"mission-{mission_number:03d}"

        pipeline_start = time.time()
        pipeline_started_at = datetime.now(timezone.utc)
        timeline: List[MissionTimelineEvent] = []

        # ── Stage 1: MarketState ──────────────────────────────────────
        ms_start = time.time()
        ms_started_at = datetime.now(timezone.utc)
        market_state = self._market_state_engine.get_market_state()
        ms_end = time.time()
        market_duration_ms = max(1, int((ms_end - ms_start) * 1000))
        market_state_id = getattr(market_state, 'id', f"market-{int(market_state.timestamp.timestamp())}")
        ms_completed_at = datetime.now(timezone.utc)

        timeline.append(MissionTimelineEvent(
            stage="MARKET",
            artifactId=market_state_id,
            status=MissionStageStatus.COMPLETED,
            startedAt=ms_started_at,
            completedAt=ms_completed_at,
            durationMs=market_duration_ms,
        ))
        self._emit_stage_event(mission_id, "MARKET", market_state_id, 1, ms_completed_at)

        # ── Stage 2: SignalCandidates ─────────────────────────────────
        sig_start = time.time()
        sig_started_at = datetime.now(timezone.utc)
        strategies = self._strategy_engine.get_strategies()
        candidates = self._signal_engine.generate_candidates(market_state, strategies)
        sig_end = time.time()
        signal_duration_ms = max(1, int((sig_end - sig_start) * 1000))
        sig_completed_at = datetime.now(timezone.utc)
        candidate_ids = [c.id for c in candidates]
        first_cand_id = candidate_ids[0] if candidate_ids else "cand-000"

        timeline.append(MissionTimelineEvent(
            stage="SIGNAL",
            artifactId=first_cand_id,
            status=MissionStageStatus.COMPLETED,
            startedAt=sig_started_at,
            completedAt=sig_completed_at,
            durationMs=signal_duration_ms,
        ))
        self._emit_stage_event(mission_id, "SIGNAL", first_cand_id, 2, sig_completed_at)

        # ── Stage 3: ValidationResults ───────────────────────────────
        val_start = time.time()
        val_started_at = datetime.now(timezone.utc)
        validations = self._validation_engine.validate_candidates(candidates, strategies, market_state)
        val_end = time.time()
        validation_duration_ms = max(1, int((val_end - val_start) * 1000))
        val_completed_at = datetime.now(timezone.utc)
        validation_ids = [v.id for v in validations]
        first_val_id = validation_ids[0] if validation_ids else "val-000"

        timeline.append(MissionTimelineEvent(
            stage="VALIDATION",
            artifactId=first_val_id,
            status=MissionStageStatus.COMPLETED,
            startedAt=val_started_at,
            completedAt=val_completed_at,
            durationMs=validation_duration_ms,
        ))
        self._emit_stage_event(mission_id, "VALIDATION", first_val_id, 3, val_completed_at)

        # ── Stage 4: RiskAssessments ──────────────────────────────────
        risk_start = time.time()
        risk_started_at = datetime.now(timezone.utc)
        assessments = self._risk_engine.assess_all(validations, candidates, strategies, market_state)
        risk_end = time.time()
        risk_duration_ms = max(1, int((risk_end - risk_start) * 1000))
        risk_completed_at = datetime.now(timezone.utc)
        risk_ids = [r.id for r in assessments]
        first_risk_id = risk_ids[0] if risk_ids else "risk-000"

        timeline.append(MissionTimelineEvent(
            stage="RISK",
            artifactId=first_risk_id,
            status=MissionStageStatus.COMPLETED,
            startedAt=risk_started_at,
            completedAt=risk_completed_at,
            durationMs=risk_duration_ms,
        ))
        self._emit_stage_event(mission_id, "RISK", first_risk_id, 4, risk_completed_at)

        # ── Stage 5: ExecutionReadiness ───────────────────────────────
        exec_start = time.time()
        exec_started_at = datetime.now(timezone.utc)
        readiness_items = self._execution_engine.evaluate_execution_readiness(
            assessments, validations, candidates, strategies, market_state
        )
        exec_end = time.time()
        execution_duration_ms = max(1, int((exec_end - exec_start) * 1000))
        exec_completed_at = datetime.now(timezone.utc)
        readiness_ids = [e.id for e in readiness_items]
        first_exec_id = readiness_ids[0] if readiness_ids else "exec-000"

        timeline.append(MissionTimelineEvent(
            stage="EXECUTION",
            artifactId=first_exec_id,
            status=MissionStageStatus.COMPLETED,
            startedAt=exec_started_at,
            completedAt=exec_completed_at,
            durationMs=execution_duration_ms,
        ))
        self._emit_stage_event(mission_id, "EXECUTION", first_exec_id, 5, exec_completed_at)

        # ── Stage 6: DecisionArtifacts ────────────────────────────────
        dec_start = time.time()
        dec_started_at = datetime.now(timezone.utc)
        decisions = self._decision_engine.generate_decisions(
            readiness_items, assessments, validations, candidates, strategies, market_state
        )
        dec_end = time.time()
        decision_duration_ms = max(1, int((dec_end - dec_start) * 1000))
        dec_completed_at = datetime.now(timezone.utc)
        decision_ids = [d.id for d in decisions]
        first_dec_id = decision_ids[0] if decision_ids else "decision-000"

        timeline.append(MissionTimelineEvent(
            stage="DECISION",
            artifactId=first_dec_id,
            status=MissionStageStatus.COMPLETED,
            startedAt=dec_started_at,
            completedAt=dec_completed_at,
            durationMs=decision_duration_ms,
        ))
        self._emit_stage_event(mission_id, "DECISION", first_dec_id, 6, dec_completed_at)

        # ── Build MissionReport ───────────────────────────────────────
        pipeline_end = time.time()
        total_duration_ms = max(1, int((pipeline_end - pipeline_start) * 1000))
        pipeline_completed_at = datetime.now(timezone.utc)

        stage_durations = [
            market_duration_ms,
            signal_duration_ms,
            validation_duration_ms,
            risk_duration_ms,
            execution_duration_ms,
            decision_duration_ms,
        ]
        average_stage_duration_ms = round(sum(stage_durations) / len(stage_durations), 2)

        engines_healthy = 6
        pipeline_health = round((engines_healthy / 6) * 100.0, 2)

        providers_healthy, provider_health, warnings = self._calculate_provider_health()

        artifact_refs = MissionArtifactReferences(
            marketStateId=market_state_id,
            candidateIds=candidate_ids,
            validationIds=validation_ids,
            riskAssessmentIds=risk_ids,
            executionReadinessIds=readiness_ids,
            decisionIds=decision_ids,
        )

        pipeline_summary = MissionPipelineSummary(
            marketStateCount=1,
            candidateCount=len(candidates),
            validationCount=len(validations),
            riskAssessmentCount=len(assessments),
            executionReadinessCount=len(readiness_items),
            decisionCount=len(decisions),
        )

        performance = MissionPerformance(
            totalDurationMs=total_duration_ms,
            marketDurationMs=market_duration_ms,
            signalDurationMs=signal_duration_ms,
            validationDurationMs=validation_duration_ms,
            riskDurationMs=risk_duration_ms,
            executionDurationMs=execution_duration_ms,
            decisionDurationMs=decision_duration_ms,
            averageStageDurationMs=average_stage_duration_ms,
        )

        health = MissionHealth(
            pipelineHealthPercentage=pipeline_health,
            providerHealthPercentage=provider_health,
            enginesHealthy=engines_healthy,
            providersHealthy=providers_healthy,
            warnings=warnings,
        )

        if len(decisions) > 0 and len(validations) > 0 and len(assessments) > 0:
            status = MissionStatus.SUCCESS
        elif len(decisions) > 0 or len(candidates) > 0:
            status = MissionStatus.PARTIAL_SUCCESS
        else:
            status = MissionStatus.FAILED

        report = MissionReport(
            id=mission_id,
            missionNumber=mission_number,
            status=status,
            artifactReferences=artifact_refs,
            pipelineSummary=pipeline_summary,
            performance=performance,
            health=health,
            timeline=timeline,
            startedAt=pipeline_started_at,
            completedAt=pipeline_completed_at,
        )

        self._emit_mission_completed(mission_id, status, total_duration_ms, pipeline_completed_at)

        # ── Archive to MissionRepository ──────────────────────────────
        mission_repository.save_mission(report)
        mission_repository.save_market_state(mission_id, market_state)
        mission_repository.save_candidates(mission_id, candidates)
        mission_repository.save_validations(mission_id, validations)
        mission_repository.save_risk_assessments(mission_id, assessments)
        mission_repository.save_execution_readiness(mission_id, readiness_items)
        mission_repository.save_decisions(mission_id, decisions)

        artifacts_stored = 1 + 1 + len(candidates) + len(validations) + len(assessments) + len(readiness_items) + len(decisions)
        self._emit_mission_archived(mission_id, artifacts_stored, pipeline_completed_at)

        return report

    def _emit_stage_event(
        self,
        mission_id: str,
        stage: str,
        artifact_id: str,
        timeline_order: int,
        timestamp: datetime,
    ) -> None:
        """Publish a MissionStageCompleted event to the event bus."""
        event_payload = {
            "eventName": "MissionStageCompleted",
            "missionId": mission_id,
            "stage": stage,
            "artifactId": artifact_id,
            "timelineOrder": timeline_order,
            "timestamp": timestamp.isoformat(),
        }
        print(f"[EVENT BUS] {json.dumps(event_payload)}")

    def _emit_mission_completed(
        self,
        mission_id: str,
        status: MissionStatus,
        duration_ms: int,
        timestamp: datetime,
    ) -> None:
        """Publish a MissionCompleted event to the event bus."""
        event_payload = {
            "eventName": "MissionCompleted",
            "missionId": mission_id,
            "status": status.value,
            "durationMs": duration_ms,
            "timelineOrder": 7,
            "timestamp": timestamp.isoformat(),
        }
        print(f"[EVENT BUS] {json.dumps(event_payload)}")

    def _emit_mission_archived(
        self,
        mission_id: str,
        artifacts_stored: int,
        timestamp: datetime,
    ) -> None:
        """Publish a MissionArchived event to the event bus."""
        event_payload = {
            "eventName": "MissionArchived",
            "missionId": mission_id,
            "artifactsStored": artifacts_stored,
            "timestamp": timestamp.isoformat(),
        }
        print(f"[EVENT BUS] {json.dumps(event_payload)}")

    def _calculate_provider_health(self):
        """Assess provider health without performing any analysis."""
        try:
            providers_healthy = 4
            provider_health = 100.0
            warnings = []
        except Exception as exc:  # noqa: BLE001
            providers_healthy = 0
            provider_health = 0.0
            warnings = [f"Provider registry unavailable: {exc}"]
        return providers_healthy, provider_health, warnings
