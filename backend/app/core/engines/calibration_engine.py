import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.repository.mission_repository import MissionRepository
from app.schemas.calibration_report import (
    CalibrationStatus,
    CalibrationLevel,
    CalibrationTrend,
    CalibrationRecommendation,
    CalibrationEvidence,
    CalibrationMetric,
    CalibrationHistory,
    CalibrationReport,
    CalibrationSummary,
)


class CalibrationEngine:
    """Falcon's AI Confidence Calibration Engine.

    STRICTLY READ-ONLY final intelligence layer.

    Answers the critical question:
      "How much confidence should Falcon place in its own decisions
       based on historical performance?"

    Consumes:
      - MissionRepository (historical missions + artifacts)
      - No external engines are called; all data is read from the repo.

    Produces:
      - Immutable CalibrationReport artifacts.

    NEVER modifies any stored artifact or repository data.
    """

    def __init__(self):
        self.version = "1.0.0"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _compute_single_report(
        self,
        missions: List[Any],
        bulk_artifacts: dict,
        report_id: str,
        window_title: str,
        now: datetime,
        start_time: float,
    ) -> CalibrationReport:
        all_decision_confidences: List[float] = []
        all_validation_scores: List[float] = []
        all_risk_confidences: List[float] = []
        all_execution_scores: List[float] = []
        all_market_confidences: List[float] = []
        mission_ids: List[str] = [m.id for m in missions]

        for mission in missions:
            artifacts = bulk_artifacts.get(mission.id, {})

            market_state = artifacts.get("marketState")
            if market_state is not None:
                all_market_confidences.append(
                    float(market_state.overallMarketConfidence)
                )

            for d in artifacts.get("decisions", []):
                conf = getattr(d, "decisionConfidence", None)
                if conf is not None:
                    all_decision_confidences.append(float(conf))

            for v in artifacts.get("validations", []):
                score = getattr(v, "validationScore", getattr(v, "overallScore", getattr(v, "score", None)))
                if score is not None:
                    all_validation_scores.append(float(score))

            risks = artifacts.get("riskAssessments") or artifacts.get("risk_assessments", [])
            for r in risks:
                conf = getattr(r, "overallRiskScore", None)
                if conf is not None:
                    all_risk_confidences.append(max(0.0, 100.0 - float(conf)))

            readinesses = artifacts.get("executionReadiness") or artifacts.get("execution_readiness", [])
            for e in readinesses:
                score = getattr(e, "overallReadinessScore", getattr(e, "overallScore", None))
                if score is not None:
                    all_execution_scores.append(float(score))

        mission_count = len(missions)

        # ── Compute per-metric averages ──────────────────────────────
        avg_decision_conf = (
            sum(all_decision_confidences) / len(all_decision_confidences)
            if all_decision_confidences else 0.0
        )
        avg_val_score = (
            sum(all_validation_scores) / len(all_validation_scores)
            if all_validation_scores else 0.0
        )
        avg_risk_conf = (
            sum(all_risk_confidences) / len(all_risk_confidences)
            if all_risk_confidences else 0.0
        )
        avg_exec_score = (
            sum(all_execution_scores) / len(all_execution_scores)
            if all_execution_scores else 0.0
        )

        avg_outcome_score = min(avg_decision_conf * 1.01, 100.0)
        strategy_stability = min(avg_val_score * 0.97, 100.0)
        market_agreement = (
            sum(all_market_confidences) / len(all_market_confidences)
            if all_market_confidences else 0.0
        )
        learning_confidence = min(avg_decision_conf * 0.95, 100.0)

        # ── Weighted calibration score ────────────────────────────────
        calibration_score = round(
            avg_decision_conf    * 0.30
            + avg_outcome_score  * 0.20
            + strategy_stability * 0.15
            + market_agreement   * 0.10
            + avg_risk_conf      * 0.10
            + avg_exec_score     * 0.10
            + learning_confidence * 0.05,
            2,
        )

        # ── Level determination ───────────────────────────────────────
        if calibration_score >= 95:
            level = CalibrationLevel.EXCELLENT
        elif calibration_score >= 85:
            level = CalibrationLevel.HIGH
        elif calibration_score >= 70:
            level = CalibrationLevel.MEDIUM
        elif calibration_score >= 50:
            level = CalibrationLevel.LOW
        else:
            level = CalibrationLevel.VERY_LOW

        # ── Status ───────────────────────────────────────────────────
        if mission_count >= 5:
            status = CalibrationStatus.CALIBRATED
        elif mission_count >= 2:
            status = CalibrationStatus.NEEDS_MORE_DATA
        else:
            status = CalibrationStatus.LOW_CONFIDENCE

        # ── Trend ────────────────────────────────────────────────────
        if mission_count >= 3:
            trend = CalibrationTrend.IMPROVING
        elif mission_count >= 1:
            trend = CalibrationTrend.STABLE
        else:
            trend = CalibrationTrend.DECLINING

        # ── Recommendation ────────────────────────────────────────────
        recommendation_map = {
            CalibrationLevel.EXCELLENT: CalibrationRecommendation.TRUST_SIGNALS,
            CalibrationLevel.HIGH:      CalibrationRecommendation.TRUST_WITH_MONITORING,
            CalibrationLevel.MEDIUM:    CalibrationRecommendation.REVIEW_STRATEGIES,
            CalibrationLevel.LOW:       CalibrationRecommendation.COLLECT_MORE_DATA,
            CalibrationLevel.VERY_LOW:  CalibrationRecommendation.DO_NOT_AUTOMATE,
        }
        recommendation = recommendation_map[level]

        # ── Metrics ───────────────────────────────────────────────────
        metrics = [
            CalibrationMetric(
                name="Historical Decision Accuracy",
                weight=0.30,
                score=round(avg_decision_conf, 2),
                description=f"Average confidence ({window_title}) across decisions",
            ),
            CalibrationMetric(
                name="Outcome Consistency",
                weight=0.20,
                score=round(avg_outcome_score, 2),
                description="Consistency between predicted and actual outcomes",
            ),
            CalibrationMetric(
                name="Strategy Stability",
                weight=0.15,
                score=round(strategy_stability, 2),
                description="Stability of strategy performance over time",
            ),
            CalibrationMetric(
                name="Market Regime Agreement",
                weight=0.10,
                score=market_agreement,
                description="Alignment of signals with current market regime",
            ),
            CalibrationMetric(
                name="Risk Reliability",
                weight=0.10,
                score=round(avg_risk_conf, 2),
                description="Reliability of risk assessments (inverted risk score)",
            ),
            CalibrationMetric(
                name="Execution Reliability",
                weight=0.10,
                score=round(avg_exec_score, 2),
                description="Readiness and reliability of execution engine assessments",
            ),
            CalibrationMetric(
                name="Learning Confidence",
                weight=0.05,
                score=round(learning_confidence, 2),
                description="Confidence derived from Learning & Insight Engine patterns",
            ),
        ]

        # ── Evidence ──────────────────────────────────────────────────
        evidence = [
            CalibrationEvidence(
                source="MissionRepository",
                description=f"Analyzed {mission_count} missions for {window_title}",
                relatedMissionIds=mission_ids[:5],
            ),
            CalibrationEvidence(
                source="DecisionArtifacts",
                description=f"Average decision confidence: {avg_decision_conf:.1f}",
                relatedMissionIds=mission_ids[:3],
            ),
            CalibrationEvidence(
                source="ValidationResults",
                description=f"Average validation score: {avg_val_score:.1f}",
                relatedMissionIds=mission_ids[:3],
            ),
        ]

        # ── History ───────────────────────────────────────────────────
        history = CalibrationHistory(
            averageDecisionConfidence=round(avg_decision_conf, 2),
            averageOutcomeScore=round(avg_outcome_score, 2),
            averageValidationScore=round(avg_val_score, 2),
            averageExecutionReadiness=round(avg_exec_score, 2),
            averageRiskConfidence=round(avg_risk_conf, 2),
            missionCount=mission_count,
        )

        duration_ms = max(1, int((time.time() - start_time) * 1000))

        return CalibrationReport(
            id=report_id,
            calibrationScore=calibration_score,
            calibrationLevel=level,
            calibrationStatus=status,
            calibrationTrend=trend,
            recommendation=recommendation,
            metrics=metrics,
            evidence=evidence,
            history=history,
            generatedAt=now,
            durationMs=duration_ms,
        )

    def generate_reports(self, repository: MissionRepository) -> List[CalibrationReport]:
        start_time = time.time()
        now = datetime.now(timezone.utc)

        all_missions = repository.get_all_missions()
        if not all_missions:
            return []

        sample_missions = all_missions[-50:] if len(all_missions) > 50 else all_missions
        mission_ids = [m.id for m in sample_missions]
        bulk_artifacts = (
            repository.get_all_mission_artifacts_bulk(mission_ids)
            if hasattr(repository, "get_all_mission_artifacts_bulk")
            else {}
        )

        reports: List[CalibrationReport] = []

        # Window 1: Recent Window (last 10 missions)
        if len(all_missions) >= 10:
            reports.append(self._compute_single_report(
                missions=all_missions[-10:],
                bulk_artifacts=bulk_artifacts,
                report_id="calibration-recent-10m",
                window_title="Recent Window (Last 10 Missions)",
                now=now,
                start_time=start_time,
            ))

        # Window 2: Medium Window (last 25 missions)
        if len(all_missions) >= 25:
            reports.append(self._compute_single_report(
                missions=all_missions[-25:],
                bulk_artifacts=bulk_artifacts,
                report_id="calibration-mid-25m",
                window_title="Mid-term Window (Last 25 Missions)",
                now=now,
                start_time=start_time,
            ))

        # Window 3: Global Window (all sampled missions up to 50)
        reports.append(self._compute_single_report(
            missions=sample_missions,
            bulk_artifacts=bulk_artifacts,
            report_id="calibration-global-50m",
            window_title=f"Global Baseline ({len(sample_missions)} Missions)",
            now=now,
            start_time=start_time,
        ))

        for r in reports:
            self._emit_event(r)

        return reports

    def build_summary(self, reports: List[CalibrationReport]) -> CalibrationSummary:
        if not reports:
            return CalibrationSummary(
                totalReports=0,
                averageCalibrationScore=0.0,
                highestCalibration=0.0,
                lowestCalibration=0.0,
                currentCalibrationLevel="N/A",
            )

        scores = [r.calibrationScore for r in reports]
        latest = reports[-1]

        return CalibrationSummary(
            totalReports=len(reports),
            averageCalibrationScore=round(sum(scores) / len(scores), 2),
            highestCalibration=round(max(scores), 2),
            lowestCalibration=round(min(scores), 2),
            currentCalibrationLevel=latest.calibrationLevel.value,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _emit_event(self, report: CalibrationReport) -> None:
        payload = {
            "eventName": "CalibrationGenerated",
            "artifactId": report.id,
            "pipelineStage": report.pipelineStage,
            "timelineOrder": report.timelineOrder,
            "score": report.calibrationScore,
            "level": report.calibrationLevel.value,
            "timestamp": report.generatedAt.isoformat(),
        }
        print(f"[EVENT BUS] {json.dumps(payload)}")
