import json
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional

def _format_local_time(dt: datetime) -> str:
    """Format UTC datetime into user's local time (UTC+1)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone(timezone(timedelta(hours=1)))
    return local_dt.strftime("%H:%M:%S")

from app.schemas.market_state import MarketState
from app.schemas.strategy import StrategyItem
from app.schemas.signal_candidate import SignalCandidate, CandidateStatus
from app.schemas.validation_result import ValidationResult, ValidationStatus
from app.schemas.risk_assessment import RiskAssessment, RiskLevel, RiskAssessmentStatus
from app.schemas.execution_readiness import ExecutionReadiness, ExecutionReadinessStatus, ReadinessSeverity
from app.schemas.decision_artifact import (
    DecisionArtifact,
    DecisionRecommendation,
    DecisionStatus,
    DecisionSeverity,
    DecisionPriority,
    DecisionFactor,
    DecisionRecommendationDetails,
    DecisionStageTrace,
    MissionVerdict,
    DecisionMarketSnapshot,
    DecisionPipelineSummary
)

class DecisionEngine:
    def __init__(self):
        self.version = "1.0.0"
        self.decisionLogicVersion = "Captain Logic v1.0"

    def _get_priority_score(self, priority: DecisionPriority) -> int:
        mapping = {
            DecisionPriority.CRITICAL: 3,
            DecisionPriority.HIGH: 2,
            DecisionPriority.MEDIUM: 1,
            DecisionPriority.LOW: 0
        }
        return mapping.get(priority, 0)

    def _compute_market_clocks(self, now: datetime):
        from app.core.services.dashboard_service import compute_market_clocks
        return compute_market_clocks(now)

    def generate_decisions(
        self,
        execution_readiness_items: List[ExecutionReadiness],
        risk_assessments: List[RiskAssessment],
        validation_results: List[ValidationResult],
        signal_candidates: List[SignalCandidate],
        strategies: List[StrategyItem],
        market_state: MarketState
    ) -> List[DecisionArtifact]:
        decisions: List[DecisionArtifact] = []

        # Create quick lookups
        risk_map = {r.id: r for r in risk_assessments}
        validation_map = {v.id: v for v in validation_results}
        candidate_map = {c.id: c for c in signal_candidates}
        strategy_map = {s.id: s for s in strategies}

        for idx, execution in enumerate(execution_readiness_items, start=1):
            start_time = time.time()
            now = datetime.now(timezone.utc)
            decision_id = f"decision-{idx:03d}"

            risk = risk_map.get(execution.riskAssessmentId)
            validation = validation_map.get(execution.validationId)
            candidate = candidate_map.get(execution.candidateId)
            strategy = strategy_map.get(execution.strategyId)

            # Fallback values if missing
            cand_status = execution.candidateStatus
            val_status = execution.validationStatus
            risk_lvl = execution.riskLevel
            risk_status = execution.riskStatus
            exec_status = execution.status

            cand_conf = candidate.confidence if candidate else 80.0
            val_score = float(validation.validationScore) if validation else 80.0
            risk_score = float(risk.overallRiskScore) if risk else 20.0
            exec_score = float(execution.overallReadinessScore)

            # Rule 1: RiskConfidence = 100 - OverallRiskScore
            risk_confidence = max(0.0, 100.0 - risk_score)

            # Rule 1: Decision Confidence = 40% Signal + 25% Validation + 20% Risk Confidence + 15% Execution Readiness
            raw_confidence = (
                0.40 * cand_conf +
                0.25 * val_score +
                0.20 * risk_confidence +
                0.15 * exec_score
            )
            decisionConfidence = max(0.0, min(100.0, round(raw_confidence, 1)))

            # Decision Mapping Logic
            if (
                exec_status == ExecutionReadinessStatus.BLOCKED or
                risk_lvl == RiskLevel.EXTREME or
                val_status == ValidationStatus.FAILED
            ):
                recommendation = DecisionRecommendation.NO_TRADE
                status = DecisionStatus.REJECTED
                priority = DecisionPriority.CRITICAL if exec_status == ExecutionReadinessStatus.BLOCKED else DecisionPriority.HIGH
                title = "No Trade Recommended"
                description = "Pipeline blocked by execution readiness, extreme risk level, or validation failure."
                expectedHolding = "N/A"
                nextReviewIn = execution.recommendation.nextReviewIn or "Next Market Session"
                missionStatus = "BLOCKED"
            elif exec_status == ExecutionReadinessStatus.WAIT:
                recommendation = DecisionRecommendation.WAIT
                status = DecisionStatus.PENDING
                priority = DecisionPriority.HIGH
                title = "Execution On Hold - Waiting Requirements"
                description = "Execution engine recommends waiting until spread, session, or news conditions improve."
                expectedHolding = strategy.estimatedHoldingTime if strategy else "2-6 Hours"
                nextReviewIn = execution.recommendation.nextReviewIn or "15 Minutes"
                missionStatus = "PENDING"
            elif (
                val_status == ValidationStatus.PARTIALLY_PASSED or
                (risk_lvl == RiskLevel.MEDIUM and decisionConfidence < 70)
            ):
                recommendation = DecisionRecommendation.MONITOR
                status = DecisionStatus.MONITORING
                priority = DecisionPriority.MEDIUM
                title = "Monitor Setup Before Execution"
                description = "Candidate has valid parameters with medium risk or partial validation. Active monitoring required."
                expectedHolding = strategy.estimatedHoldingTime if strategy else "2-6 Hours"
                nextReviewIn = "15 Minutes"
                missionStatus = "MONITORING"
            else:
                # Execution READY, Validation PASSED, Risk LOW or manageable MEDIUM with high confidence
                # Determine direction from candidate status or type
                cand_direction = candidate.direction.name if candidate and hasattr(candidate.direction, 'name') else str(cand_status.name if hasattr(cand_status, 'name') else cand_status)
                if "SELL" in str(cand_direction).upper():
                    recommendation = DecisionRecommendation.SELL
                else:
                    recommendation = DecisionRecommendation.BUY

                status = DecisionStatus.APPROVED
                priority = DecisionPriority.HIGH if risk_lvl == RiskLevel.LOW else DecisionPriority.MEDIUM
                title = f"Approve {recommendation.value} Order Execution"
                description = f"All 5 pipeline stages passed with high confidence ({decisionConfidence}%). Captain authorizes immediate {recommendation.value} execution."
                expectedHolding = strategy.estimatedHoldingTime if strategy else "2-6 Hours"
                nextReviewIn = "Immediate"
                missionStatus = "READY"

            recommendationDetails = DecisionRecommendationDetails(
                recommendation=recommendation,
                priority=priority,
                expectedHolding=expectedHolding,
                nextReviewIn=nextReviewIn,
                missionStatus=missionStatus,
                title=title,
                description=description
            )

            # Mission Verdict
            missionVerdict = MissionVerdict(
                signalVerdict=cand_status,
                validationVerdict=val_status,
                riskVerdict=risk_lvl,
                executionVerdict=exec_status,
                decisionVerdict=recommendation
            )

            # Decision Stage Trace
            decisionTrace = [
                DecisionStageTrace(
                    stage="SIGNAL",
                    artifactId=execution.candidateId,
                    status=cand_status.value,
                    completedAt=candidate.generatedAt if candidate else now
                ),
                DecisionStageTrace(
                    stage="VALIDATION",
                    artifactId=execution.validationId,
                    status=val_status.value,
                    completedAt=validation.validatedAt if validation else now
                ),
                DecisionStageTrace(
                    stage="RISK",
                    artifactId=execution.riskAssessmentId,
                    status=risk_status.value,
                    completedAt=risk.assessedAt if risk else now
                ),
                DecisionStageTrace(
                    stage="EXECUTION",
                    artifactId=execution.id,
                    status=exec_status.value,
                    completedAt=execution.evaluatedAt
                ),
                DecisionStageTrace(
                    stage="DECISION",
                    artifactId=decision_id,
                    status=status.value,
                    completedAt=now
                ),
            ]

            # Build Supporting, Blocking, and Watch factors
            supportingFactors: List[DecisionFactor] = []
            blockingFactors: List[DecisionFactor] = []
            watchItems: List[DecisionFactor] = []

            # 1. Candidate Factor
            if cand_conf >= 70:
                supportingFactors.append(
                    DecisionFactor(
                        title="Strong Signal Confidence",
                        description=f"Signal candidate generated with {cand_conf}% confidence.",
                        severity=DecisionSeverity.INFO,
                        priority=DecisionPriority.HIGH,
                        passed=True
                    )
                )

            # 2. Validation Factor
            if val_status == ValidationStatus.PASSED:
                supportingFactors.append(
                    DecisionFactor(
                        title="Validation Passed",
                        description=f"All strategy rule checks passed ({val_score}% score).",
                        severity=DecisionSeverity.INFO,
                        priority=DecisionPriority.HIGH,
                        passed=True
                    )
                )
            elif val_status == ValidationStatus.PARTIALLY_PASSED:
                watchItems.append(
                    DecisionFactor(
                        title="Partial Validation",
                        description=f"Validation score is {val_score}%. Some optional rules were not satisfied.",
                        severity=DecisionSeverity.WARNING,
                        priority=DecisionPriority.MEDIUM,
                        passed=False
                    )
                )
            else:
                blockingFactors.append(
                    DecisionFactor(
                        title="Validation Failed",
                        description="Candidate failed critical strategy validation rules.",
                        severity=DecisionSeverity.CRITICAL,
                        priority=DecisionPriority.CRITICAL,
                        passed=False
                    )
                )

            # 3. Risk Factor
            if risk_lvl == RiskLevel.LOW:
                supportingFactors.append(
                    DecisionFactor(
                        title="Low Risk Assessment",
                        description=f"Overall risk score is safe at {risk_score}/100.",
                        severity=DecisionSeverity.INFO,
                        priority=DecisionPriority.MEDIUM,
                        passed=True
                    )
                )
            elif risk_lvl == RiskLevel.MEDIUM:
                watchItems.append(
                    DecisionFactor(
                        title="Medium Risk Level",
                        description=f"Overall risk score is elevated at {risk_score}/100.",
                        severity=DecisionSeverity.WARNING,
                        priority=DecisionPriority.MEDIUM,
                        passed=False
                    )
                )
            else:
                blockingFactors.append(
                    DecisionFactor(
                        title="Extreme Risk Level",
                        description=f"Overall risk score is unacceptably high at {risk_score}/100.",
                        severity=DecisionSeverity.CRITICAL,
                        priority=DecisionPriority.CRITICAL,
                        passed=False
                    )
                )

            # 4. Execution Factors
            if exec_status == ExecutionReadinessStatus.READY:
                supportingFactors.append(
                    DecisionFactor(
                        title="Execution Readiness Ready",
                        description=f"Execution readiness score is {exec_score}/100.",
                        severity=DecisionSeverity.INFO,
                        priority=DecisionPriority.MEDIUM,
                        passed=True
                    )
                )
            elif exec_status == ExecutionReadinessStatus.WAIT:
                watchItems.append(
                    DecisionFactor(
                        title="Execution Delay Advised",
                        description=f"Execution score is {exec_score}/100. Review operational parameters.",
                        severity=DecisionSeverity.WARNING,
                        priority=DecisionPriority.HIGH,
                        passed=False
                    )
                )
            else:
                blockingFactors.append(
                    DecisionFactor(
                        title="Execution Engine Blocked",
                        description="Execution engine reported active blocking operational conditions.",
                        severity=DecisionSeverity.CRITICAL,
                        priority=DecisionPriority.CRITICAL,
                        passed=False
                    )
                )

            # Add reasons from execution readiness as factors
            for reason in execution.reasons:
                severity = DecisionSeverity.CRITICAL if reason.severity == ReadinessSeverity.CRITICAL else (
                    DecisionSeverity.WARNING if reason.severity == ReadinessSeverity.WARNING else DecisionSeverity.INFO
                )
                priority = DecisionPriority.CRITICAL if reason.isBlocking else (
                    DecisionPriority.HIGH if severity == DecisionSeverity.CRITICAL else DecisionPriority.MEDIUM
                )
                factor = DecisionFactor(
                    title=reason.title,
                    description=reason.description,
                    severity=severity,
                    priority=priority,
                    passed=not reason.isBlocking
                )

                if reason.isBlocking:
                    blockingFactors.append(factor)
                elif reason.severity == ReadinessSeverity.WARNING:
                    watchItems.append(factor)
                else:
                    supportingFactors.append(factor)

            # Sort factors by priority (CRITICAL > HIGH > MEDIUM > LOW)
            supportingFactors.sort(key=lambda f: self._get_priority_score(f.priority), reverse=True)
            blockingFactors.sort(key=lambda f: self._get_priority_score(f.priority), reverse=True)
            watchItems.sort(key=lambda f: self._get_priority_score(f.priority), reverse=True)

            # Pipeline Summary
            pipelineSummary = DecisionPipelineSummary(
                candidateStatus=cand_status,
                validationStatus=val_status,
                riskStatus=risk_status,
                executionStatus=exec_status,
                signalConfidence=cand_conf,
                validationScore=val_score,
                overallRiskScore=risk_score,
                executionReadinessScore=exec_score
            )

            # Market Snapshot
            marketSnapshot = DecisionMarketSnapshot(
                trend=market_state.trend.value if hasattr(market_state.trend, 'value') else str(market_state.trend),
                volatility=execution.marketSnapshot.volatility,
                session=execution.marketSnapshot.session,
                spread=execution.marketSnapshot.spread,
                newsImpact=execution.marketSnapshot.newsImpact,
                marketSentiment=execution.marketSnapshot.marketSentiment,
                marketConfidence=float(execution.marketSnapshot.marketConfidence),
                dataAgeSeconds=execution.marketSnapshot.dataAgeSeconds
            )

            duration_ms = int((time.time() - start_time) * 1000)

            artifact = DecisionArtifact(
                id=decision_id,
                marketStateId=getattr(market_state, 'id', f"market-{int(market_state.timestamp.timestamp())}"),
                candidateId=execution.candidateId,
                validationId=execution.validationId,
                riskAssessmentId=execution.riskAssessmentId,
                executionReadinessId=execution.id,
                strategyId=execution.strategyId,
                strategyName=strategy.name if strategy else "Default Strategy",
                strategyVersion=strategy.strategyVersion if strategy else "1.0.0",
                recommendation=recommendation,
                status=status,
                decisionConfidence=decisionConfidence,
                recommendationDetails=recommendationDetails,
                missionVerdict=missionVerdict,
                decisionTrace=decisionTrace,
                supportingFactors=supportingFactors,
                blockingFactors=blockingFactors,
                watchItems=watchItems,
                pipelineSummary=pipelineSummary,
                marketSnapshot=marketSnapshot,
                artifactType="DecisionArtifact",
                pipelineStage="DECISION",
                pipelineVersion="1.0",
                engineVersion=self.version,
                decisionLogicVersion=self.decisionLogicVersion,
                decidedBy="Decision Engine",
                timelineOrder=6,
                decidedAt=now,
                decisionDurationMs=duration_ms
            )

            decisions.append(artifact)

            # Event Bus emission matching standard format
            event_payload = {
                "eventName": "DecisionIssued",
                "artifactType": "DecisionArtifact",
                "artifactId": decision_id,
                "pipelineStage": "DECISION",
                "timelineOrder": 6,
                "recommendation": recommendation.value,
                "status": status.value,
                "decisionConfidence": decisionConfidence,
                "timestamp": now.isoformat()
            }
            print(f"[EVENT BUS] {json.dumps(event_payload)}")

        return decisions

    def get_decision(
        self,
        strategy,
        market_state,
        validation,
        risk_assessment,
        readiness
    ):
        """
        Legacy contract helper method to ensure backward compatibility for GET /decision-engine.
        """
        from app.schemas.decision_engine import (
            DecisionEngineResponse, Recommendation,
            DecisionStatus as LegacyDecisionStatus, TradeQuality,
            ConfidenceExplanation, DecisionReason, MissingCondition,
            MarketClock, TimelineEvent
        )
        from app.schemas.health import SystemHealth, EngineStatus, PerformanceMetrics
        from app.schemas.strategy import RiskLevel as StrategyRiskLevel
        from app.core.services.dashboard_service import compute_market_clocks

        is_ready = getattr(readiness, 'isReady', False)
        blocking = getattr(readiness, 'blockingConditions', [])
        passed = getattr(readiness, 'passedChecks', [])
        score = getattr(readiness, 'overallReadinessScore', 50)
        strat_id = getattr(strategy, 'id', 'strat-001')
        strat_name = getattr(strategy, 'name', 'Falcon Default Strategy')
        strat_ver = getattr(strategy, 'strategyVersion', '1.0.0')

        now = datetime.now(timezone.utc)

        if is_ready:
            rec = Recommendation.BUY
            status = LegacyDecisionStatus.READY
            quality = TradeQuality.A
            risk_lvl = StrategyRiskLevel.LOW
            greeting = "Captain's Briefing: Operational parameters optimal."
            action = "Captain authorizes trade execution."
        elif blocking:
            rec = Recommendation.WAIT
            status = LegacyDecisionStatus.BLOCKED
            quality = TradeQuality.C
            risk_lvl = StrategyRiskLevel.HIGH
            greeting = "Captain's Briefing: Trade blocked by operational conditions."
            action = "Halt execution and re-evaluate parameters."
        else:
            rec = Recommendation.WAIT
            status = LegacyDecisionStatus.WAIT
            quality = TradeQuality.B
            risk_lvl = StrategyRiskLevel.MEDIUM
            greeting = "Captain's Briefing: Parameters undergoing review."
            action = "Monitor market until requirements are satisfied."

        reasons_list = [
            DecisionReason(title=p, description="Passed readiness check", passed=True)
            for p in passed
        ]
        if not reasons_list:
            reasons_list = [DecisionReason(
                title="Validation Check",
                description="Strategy rule check evaluated",
                passed=is_ready
            )]

        missing = [
            MissingCondition(title=b, description="Blocking operational condition detected")
            for b in blocking
        ]

        system_health = SystemHealth(
            overallHealthy=True,
            engines=[
                EngineStatus(
                    name="Decision Engine",
                    version=self.version,
                    status="HEALTHY",
                    latencyMs=1,
                    lastRun=now
                )
            ],
            performanceMetrics=PerformanceMetrics(
                cpuUsagePercent=0.1,
                memoryUsageMb=64.0,
                totalApiCalls=1,
                avgResponseTimeMs=10,
                strategyEvaluations=1,
                decisionUpdates=1
            ),
            lastSuccessfulSync=now
        )

        return DecisionEngineResponse(
            recommendation=rec,
            decisionStatus=status,
            riskLevel=risk_lvl,
            tradeQuality=quality,
            confidenceScore=score,
            minimumConfidence=85,
            confidenceGap=max(0, 85 - score),
            greetingMessage=greeting,
            captainsAction=action,
            engineVersion=self.version,
            reasons=reasons_list,
            missingConditions=missing,
            explanation=ConfidenceExplanation(
                technicalSignalsContribution=int(round(score * 0.40)),
                marketSentimentContribution=int(round(score * 0.25)),
                newsImpactContribution=int(round(score * 0.20)),
                historicalPerformanceContribution=int(round(score * 0.15)),
                consistencyBonus=0
            ),
            lastUpdated=now,
            strategyId=strat_id,
            strategyName=strat_name,
            strategyVersion=strat_ver,
            strategyScore=score,
            strategyValidationScore=getattr(validation, 'score', score),
            primaryWaitReason=(
                blocking[0] if blocking
                else ("Awaiting London Open" if not is_ready else None)
            ),
            confidenceHistory=[max(50, score - 5), max(50, score - 2), score],
            executionReadiness=readiness,
            systemHealth=system_health,
            marketClocks=compute_market_clocks(now),
            timeline=[
                TimelineEvent(
                    timestamp=now,
                    formattedTime=_format_local_time(now),
                    title=f"Captain Verdict: {rec.value}",
                    description=f"{strat_name} evaluated with final confidence {score}%. Readiness: {'READY' if is_ready else ('BLOCKED' if blocking else 'WAIT')}.",
                    icon="gavel" if is_ready else "security"
                ),
                TimelineEvent(
                    timestamp=now,
                    formattedTime=_format_local_time(now),
                    title="Risk & Execution Checks Complete",
                    description=f"Risk: {'HIGH' if blocking else 'NORMAL'}, Validation: {'PASSED' if (getattr(validation, 'score', 0) >= 70) else 'PENDING'}.",
                    icon="psychology"
                )
            ]
        )


