import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.repository.mission_repository import MissionRepository
from app.schemas.learning_insight import (
    LearningCategory,
    InsightSeverity,
    InsightConfidence,
    InsightRecommendation,
    InsightEvidence,
    InsightPattern,
    LearningInsight,
    LearningSummary,
    LearningInsightListResponse,
)


class LearningInsightEngine:
    """Falcon's Learning & Insight Engine.

    STRICTLY READ-ONLY self-improvement intelligence layer.
    Analyzes historical repository artifacts to discover deterministic patterns.
    Produces immutable LearningInsight artifacts.
    Never modifies any stored artifact or strategy configuration.
    """

    def __init__(self):
        self.version = "1.0.0"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_learning_insights(
        self,
        repository: MissionRepository,
    ) -> List[LearningInsight]:
        """Analyze repository history and return deterministic LearningInsight artifacts."""
        start_time = time.time()
        now = datetime.now(timezone.utc)

        all_missions = repository.get_all_missions()
        if not all_missions:
            return []

        missions = all_missions[-50:] if len(all_missions) > 50 else all_missions
        mission_ids = [m.id for m in missions]
        bulk_artifacts = repository.get_all_mission_artifacts_bulk(mission_ids) if hasattr(repository, "get_all_mission_artifacts_bulk") else {}

        # ---- Collect all artifacts across all missions ----
        all_candidates: List[Any] = []
        all_validations: List[Any] = []
        all_risks: List[Any] = []
        all_executions: List[Any] = []
        all_decisions: List[Any] = []

        for m in missions:
            arts = bulk_artifacts.get(m.id) or repository.get_mission_artifacts(m.id)
            all_candidates.extend(arts.get("candidates", []))
            all_validations.extend(arts.get("validations", []))
            all_risks.extend(arts.get("riskAssessments", []))
            all_executions.extend(arts.get("executionReadiness", []))
            all_decisions.extend(arts.get("decisions", []))
        insights: List[LearningInsight] = []
        counter = 1

        # ---- Pattern 1: High-confidence BUY signal strategies ----
        buy_candidates = [c for c in all_candidates if "BUY" in str(c.direction).upper()]
        high_conf_buys = [c for c in buy_candidates if float(c.confidence) >= 80.0]
        if high_conf_buys:
            strat_ids = list({c.strategyId for c in high_conf_buys})
            strat_names = list({getattr(c, "strategyName", c.strategyId) for c in high_conf_buys})
            conf_avg = sum(float(c.confidence) for c in high_conf_buys) / len(high_conf_buys)
            confidence_level = self._score_to_confidence(conf_avg)
            evidence = [
                InsightEvidence(
                    title="High-Confidence BUY Signals Detected",
                    description=f"{len(high_conf_buys)} BUY signals with average confidence {conf_avg:.1f}% found across {len(strat_ids)} strategies.",
                    source="SignalCandidateArtifacts",
                    artifactId=high_conf_buys[0].id if hasattr(high_conf_buys[0], 'id') else "sig-candidate",
                    timestamp=now,
                ),
            ]
            insight = LearningInsight(
                id=f"learning-{counter:03d}",
                category=LearningCategory.STRATEGY,
                title="High-Confidence BUY Signal Cluster Detected",
                description=(
                    f"Falcon identified {len(high_conf_buys)} high-confidence BUY signals (≥80%) "
                    f"across {len(strat_ids)} strategies. These signals consistently pass validation and indicate "
                    "favorable market entry conditions during the observed mission window."
                ),
                severity=InsightSeverity.NOTICE,
                confidence=confidence_level,
                recommendation=InsightRecommendation.FOCUS,
                pattern=InsightPattern(
                    title="Recurring High-Confidence BUY Cluster",
                    description=f"Strategies producing BUY signals with confidence ≥80% across {len(missions)} missions.",
                    occurrences=len(high_conf_buys),
                    confidencePercentage=round(conf_avg, 1),
                ),
                evidence=evidence,
                affectedStrategies=strat_names[:5],
                relatedMissionIds=mission_ids[:5],
                generatedFrom="SignalCandidates",
                generatedAt=now,
                generationDurationMs=max(1, int((time.time() - start_time) * 1000)),
            )
            insights.append(insight)
            self._emit_event(insight)
            counter += 1

        # ---- Pattern 2: Repeated HIGH Risk Assessments ----
        high_risk_items = [r for r in all_risks if float(r.overallRiskScore) >= 60.0]
        if high_risk_items:
            strat_names_risk = list({getattr(r, "strategyId", "unknown") for r in high_risk_items})
            avg_risk = sum(float(r.overallRiskScore) for r in high_risk_items) / len(high_risk_items)
            severity = InsightSeverity.WARNING if avg_risk >= 70 else InsightSeverity.NOTICE
            evidence = [
                InsightEvidence(
                    title="Elevated Risk Score Pattern",
                    description=f"{len(high_risk_items)} risk assessments returned scores ≥60. Average risk: {avg_risk:.1f}.",
                    source="RiskAssessmentArtifacts",
                    artifactId=f"risk-{mission_ids[0]}",
                    timestamp=now,
                ),
            ]
            insight = LearningInsight(
                id=f"learning-{counter:03d}",
                category=LearningCategory.RISK,
                title="Repeated Elevated Risk Score Pattern",
                description=(
                    f"Falcon detected {len(high_risk_items)} risk assessments returning scores ≥60 "
                    f"across {len(missions)} missions. Average risk score: {avg_risk:.1f}. "
                    "This pattern may indicate market conditions are generating elevated risk exposure that "
                    "warrants risk parameter review."
                ),
                severity=severity,
                confidence=InsightConfidence.HIGH,
                recommendation=InsightRecommendation.INVESTIGATE,
                pattern=InsightPattern(
                    title="Elevated Risk Scoring Cluster",
                    description=f"Risk assessments scoring ≥60 across {len(missions)} pipeline missions.",
                    occurrences=len(high_risk_items),
                    confidencePercentage=round(min(99.0, avg_risk + 15.0), 1),
                ),
                evidence=evidence,
                affectedStrategies=strat_names_risk[:5],
                relatedMissionIds=mission_ids[:5],
                generatedFrom="RiskAssessments",
                generatedAt=now,
                generationDurationMs=max(1, int((time.time() - start_time) * 1000)),
            )
            insights.append(insight)
            self._emit_event(insight)
            counter += 1

        # ---- Pattern 3: Repeated WAIT decisions ----
        wait_decisions = [d for d in all_decisions if "WAIT" in str(d.status).upper() or "WAIT" in str(getattr(d, 'action', '')).upper()]
        if not wait_decisions:
            # Fallback: check direction
            wait_decisions = [d for d in all_decisions if "WAIT" in str(getattr(d, 'recommendedAction', '')).upper()]
        wait_count = len(wait_decisions)
        total_decisions = len(all_decisions)
        if total_decisions > 0:
            wait_ratio = wait_count / total_decisions
            severity = InsightSeverity.WARNING if wait_ratio >= 0.4 else InsightSeverity.INFO
            confidence_pct = round(min(99.0, 60.0 + wait_ratio * 40.0), 1)
            evidence = [
                InsightEvidence(
                    title="WAIT Decision Frequency Pattern",
                    description=f"{wait_count} of {total_decisions} decisions resulted in a WAIT outcome ({wait_ratio*100:.0f}%).",
                    source="DecisionArtifacts",
                    artifactId=f"decision-{mission_ids[0]}",
                    timestamp=now,
                ),
            ]
            insight = LearningInsight(
                id=f"learning-{counter:03d}",
                category=LearningCategory.DECISION,
                title="Frequent WAIT Decision Pattern Identified",
                description=(
                    f"Falcon observed {wait_count} WAIT decisions out of {total_decisions} total decisions "
                    f"({wait_ratio*100:.0f}%). A high WAIT ratio may indicate overly conservative risk or "
                    "validation thresholds, or consistent market conditions not meeting entry criteria."
                ),
                severity=severity,
                confidence=self._score_to_confidence(confidence_pct),
                recommendation=InsightRecommendation.MONITOR,
                pattern=InsightPattern(
                    title="Recurring WAIT Decision Outcome",
                    description=f"WAIT outcomes occurring at {wait_ratio*100:.0f}% rate across {len(missions)} missions.",
                    occurrences=wait_count,
                    confidencePercentage=confidence_pct,
                ),
                evidence=evidence,
                affectedStrategies=[],
                relatedMissionIds=mission_ids[:5],
                generatedFrom="DecisionArtifacts",
                generatedAt=now,
                generationDurationMs=max(1, int((time.time() - start_time) * 1000)),
            )
            insights.append(insight)
            self._emit_event(insight)
            counter += 1

        # ---- Pattern 4: Strategies consistently APPROVED ----
        approved_decisions = [d for d in all_decisions if "APPROVED" in str(d.status).upper()]
        if approved_decisions:
            strat_ids_approved = list({getattr(d, 'strategyId', 'unknown') for d in approved_decisions})
            strat_names_approved = list({getattr(d, 'strategyName', sid) for d, sid in
                                         zip(approved_decisions, [getattr(d, 'strategyId', 'unknown') for d in approved_decisions])})
            avg_conf_approved = (
                sum(float(d.decisionConfidence) for d in approved_decisions) / len(approved_decisions)
                if hasattr(approved_decisions[0], 'decisionConfidence') else 85.0
            )
            evidence = [
                InsightEvidence(
                    title="Consistently Approved Strategies",
                    description=f"{len(approved_decisions)} APPROVED decisions across {len(strat_ids_approved)} strategies with avg confidence {avg_conf_approved:.1f}%.",
                    source="DecisionArtifacts",
                    artifactId=f"decision-approved-{mission_ids[0]}",
                    timestamp=now,
                ),
            ]
            insight = LearningInsight(
                id=f"learning-{counter:03d}",
                category=LearningCategory.STRATEGY,
                title="Consistently Approved Strategies Identified",
                description=(
                    f"Falcon found {len(approved_decisions)} APPROVED trade decisions across "
                    f"{len(strat_ids_approved)} strategies. These strategies pass the full pipeline reliably "
                    f"with average decision confidence of {avg_conf_approved:.1f}%."
                ),
                severity=InsightSeverity.INFO,
                confidence=self._score_to_confidence(avg_conf_approved),
                recommendation=InsightRecommendation.FOCUS,
                pattern=InsightPattern(
                    title="Reliable APPROVED Decision Pattern",
                    description=f"APPROVED decisions from {len(strat_ids_approved)} strategies across {len(missions)} missions.",
                    occurrences=len(approved_decisions),
                    confidencePercentage=round(avg_conf_approved, 1),
                ),
                evidence=evidence,
                affectedStrategies=strat_names_approved[:5],
                relatedMissionIds=mission_ids[:5],
                generatedFrom="DecisionArtifacts",
                generatedAt=now,
                generationDurationMs=max(1, int((time.time() - start_time) * 1000)),
            )
            insights.append(insight)
            self._emit_event(insight)
            counter += 1

        # ---- Pattern 5: Execution blocking pattern ----
        blocked_executions = [e for e in all_executions if float(e.overallReadinessScore) < 70.0]
        if blocked_executions:
            avg_block_score = sum(float(e.overallReadinessScore) for e in blocked_executions) / len(blocked_executions)
            strat_names_blocked = list({getattr(e, "strategyId", "unknown") for e in blocked_executions})
            evidence = [
                InsightEvidence(
                    title="Low Execution Readiness Pattern",
                    description=f"{len(blocked_executions)} execution readiness items scored below 70. Avg score: {avg_block_score:.1f}.",
                    source="ExecutionReadinessArtifacts",
                    artifactId=f"exec-{mission_ids[0]}",
                    timestamp=now,
                ),
            ]
            insight = LearningInsight(
                id=f"learning-{counter:03d}",
                category=LearningCategory.EXECUTION,
                title="Execution Readiness Bottleneck Detected",
                description=(
                    f"Falcon identified {len(blocked_executions)} execution readiness items with scores below 70 "
                    f"(avg: {avg_block_score:.1f}). These represent potential pipeline bottlenecks where strategies "
                    "fail to reach trade execution despite passing earlier validation and risk checks."
                ),
                severity=InsightSeverity.WARNING,
                confidence=InsightConfidence.HIGH,
                recommendation=InsightRecommendation.ADJUST,
                pattern=InsightPattern(
                    title="Recurring Execution Readiness Bottleneck",
                    description=f"Execution scores below 70 across {len(blocked_executions)} items in {len(missions)} missions.",
                    occurrences=len(blocked_executions),
                    confidencePercentage=round(min(99.0, 100.0 - avg_block_score), 1),
                ),
                evidence=evidence,
                affectedStrategies=strat_names_blocked[:5],
                relatedMissionIds=mission_ids[:5],
                generatedFrom="ExecutionReadiness",
                generatedAt=now,
                generationDurationMs=max(1, int((time.time() - start_time) * 1000)),
            )
            insights.append(insight)
            self._emit_event(insight)
            counter += 1

        # ---- Pattern 6: Validation bottleneck ----
        low_val_items = [v for v in all_validations if float(v.validationScore) < 75.0]
        if low_val_items:
            avg_val = sum(float(v.validationScore) for v in low_val_items) / len(low_val_items)
            strat_val = list({getattr(v, "strategyId", "unknown") for v in low_val_items})
            evidence = [
                InsightEvidence(
                    title="Validation Score Below Threshold",
                    description=f"{len(low_val_items)} validation results scored below 75. Average score: {avg_val:.1f}.",
                    source="ValidationArtifacts",
                    artifactId=f"val-{mission_ids[0]}",
                    timestamp=now,
                ),
            ]
            insight = LearningInsight(
                id=f"learning-{counter:03d}",
                category=LearningCategory.VALIDATION,
                title="Recurring Validation Score Bottleneck",
                description=(
                    f"Falcon detected {len(low_val_items)} validation results scoring below 75 "
                    f"(avg: {avg_val:.1f}). This pattern may indicate that signal candidates are being "
                    "generated in conditions that do not meet full validation requirements."
                ),
                severity=InsightSeverity.NOTICE,
                confidence=InsightConfidence.MEDIUM,
                recommendation=InsightRecommendation.OBSERVE,
                pattern=InsightPattern(
                    title="Low Validation Score Cluster",
                    description=f"Validation results below 75 for {len(strat_val)} strategies across {len(missions)} missions.",
                    occurrences=len(low_val_items),
                    confidencePercentage=round(min(99.0, 85.0 - avg_val * 0.3), 1),
                ),
                evidence=evidence,
                affectedStrategies=strat_val[:5],
                relatedMissionIds=mission_ids[:5],
                generatedFrom="ValidationArtifacts",
                generatedAt=now,
                generationDurationMs=max(1, int((time.time() - start_time) * 1000)),
            )
            insights.append(insight)
            self._emit_event(insight)
            counter += 1

        # ---- Pattern 7: Pipeline stability / mission health ----
        successful_missions = [m for m in missions if "SUCCESS" in str(m.status).upper()]
        pipeline_stability = len(successful_missions) / len(missions) if missions else 1.0
        severity = InsightSeverity.INFO if pipeline_stability >= 0.8 else InsightSeverity.WARNING
        evidence = [
            InsightEvidence(
                title="Pipeline Mission Success Rate",
                description=f"{len(successful_missions)} of {len(missions)} missions completed with SUCCESS status ({pipeline_stability*100:.0f}%).",
                source="MissionRepository",
                artifactId=mission_ids[0] if mission_ids else "mission-001",
                timestamp=now,
            ),
        ]
        insight = LearningInsight(
            id=f"learning-{counter:03d}",
            category=LearningCategory.MISSION,
            title="Pipeline Stability Pattern Analysis",
            description=(
                f"Falcon's pipeline achieved a {pipeline_stability*100:.0f}% mission success rate "
                f"across {len(missions)} archived missions. "
                + ("The pipeline is operating at high stability." if pipeline_stability >= 0.8
                   else "Pipeline stability requires attention — review failed missions for common failure causes.")
            ),
            severity=severity,
            confidence=InsightConfidence.VERY_HIGH,
            recommendation=InsightRecommendation.OBSERVE if pipeline_stability >= 0.8 else InsightRecommendation.INVESTIGATE,
            pattern=InsightPattern(
                title="Mission Pipeline Stability",
                description=f"{pipeline_stability*100:.0f}% success rate across {len(missions)} missions.",
                occurrences=len(missions),
                confidencePercentage=round(pipeline_stability * 100.0, 1),
            ),
            evidence=evidence,
            affectedStrategies=[],
            relatedMissionIds=mission_ids,
            generatedFrom="MissionRepository",
            generatedAt=now,
            generationDurationMs=max(1, int((time.time() - start_time) * 1000)),
        )
        insights.append(insight)
        self._emit_event(insight)
        counter += 1

        # ---- Pattern 8: Market insights — high-confidence SELL signals ----
        sell_candidates = [c for c in all_candidates if "SELL" in str(c.direction).upper()]
        high_conf_sells = [c for c in sell_candidates if float(c.confidence) >= 80.0]
        if high_conf_sells:
            avg_sell_conf = sum(float(c.confidence) for c in high_conf_sells) / len(high_conf_sells)
            strat_sell = list({getattr(c, "strategyId", "unknown") for c in high_conf_sells})
            evidence = [
                InsightEvidence(
                    title="High-Confidence SELL Signal Cluster",
                    description=f"{len(high_conf_sells)} SELL signals with confidence ≥80%. Avg: {avg_sell_conf:.1f}%.",
                    source="SignalCandidateArtifacts",
                    artifactId=f"candidate-sell",
                    timestamp=now,
                ),
            ]
            insight = LearningInsight(
                id=f"learning-{counter:03d}",
                category=LearningCategory.MARKET,
                title="High-Confidence SELL Signal Market Pattern",
                description=(
                    f"Falcon observed {len(high_conf_sells)} high-confidence SELL signals (≥80%) "
                    f"with average confidence {avg_sell_conf:.1f}%. This suggests recurring bearish pressure "
                    "or reversion conditions in the observed market window."
                ),
                severity=InsightSeverity.NOTICE,
                confidence=self._score_to_confidence(avg_sell_conf),
                recommendation=InsightRecommendation.MONITOR,
                pattern=InsightPattern(
                    title="Recurring High-Confidence SELL Cluster",
                    description=f"High-confidence SELL signals from {len(strat_sell)} strategies across {len(missions)} missions.",
                    occurrences=len(high_conf_sells),
                    confidencePercentage=round(avg_sell_conf, 1),
                ),
                evidence=evidence,
                affectedStrategies=strat_sell[:5],
                relatedMissionIds=mission_ids[:5],
                generatedFrom="SignalCandidates",
                generatedAt=now,
                generationDurationMs=max(1, int((time.time() - start_time) * 1000)),
            )
            insights.append(insight)
            self._emit_event(insight)

        return insights

    def build_summary(self, insights: List[LearningInsight]) -> LearningSummary:
        total = len(insights)
        market = sum(1 for i in insights if i.category == LearningCategory.MARKET)
        strategy = sum(1 for i in insights if i.category == LearningCategory.STRATEGY)
        risk = sum(1 for i in insights if i.category == LearningCategory.RISK)
        decision = sum(1 for i in insights if i.category == LearningCategory.DECISION)
        critical = sum(1 for i in insights if i.severity == InsightSeverity.CRITICAL)

        confidence_values = {
            InsightConfidence.LOW: 25.0,
            InsightConfidence.MEDIUM: 55.0,
            InsightConfidence.HIGH: 80.0,
            InsightConfidence.VERY_HIGH: 95.0,
        }
        avg_conf = (
            sum(confidence_values.get(i.confidence, 55.0) for i in insights) / total
            if total > 0 else 0.0
        )

        return LearningSummary(
            totalInsights=total,
            marketInsights=market,
            strategyInsights=strategy,
            riskInsights=risk,
            decisionInsights=decision,
            criticalInsights=critical,
            averageConfidence=round(avg_conf, 1),
        )

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _score_to_confidence(self, score: float) -> InsightConfidence:
        if score >= 90.0:
            return InsightConfidence.VERY_HIGH
        elif score >= 75.0:
            return InsightConfidence.HIGH
        elif score >= 55.0:
            return InsightConfidence.MEDIUM
        else:
            return InsightConfidence.LOW

    def _emit_event(self, insight: LearningInsight) -> None:
        event_payload = {
            "eventName": "LearningInsightGenerated",
            "artifactId": insight.id,
            "category": insight.category.value,
            "severity": insight.severity.value,
            "confidence": insight.confidence.value,
            "timelineOrder": 8,
            "timestamp": insight.generatedAt.isoformat(),
        }
        print(f"[EVENT BUS] {json.dumps(event_payload)}")
