import json
from datetime import datetime, timezone
from typing import List, Optional

from app.schemas.market_state import MarketState
from app.schemas.strategy import StrategyItem
from app.schemas.signal_candidate import SignalCandidate
from app.schemas.validation_result import ValidationResult
from app.schemas.risk_assessment import RiskAssessment
from app.schemas.execution_readiness import (
    ExecutionReadiness, ExecutionReadinessStatus, ReadinessCategory,
    ReadinessSeverity, ReadinessAction, ReadinessThresholds,
    ReadinessRecommendation, ReadinessReason, ReadinessCategoryScore,
    ExecutionMarketSnapshot
)
from app.core.providers.provider_registry import provider_registry

class ExecutionReadinessEngine:
    def __init__(self):
        self.version = "1.0.0"
        self.thresholds = ReadinessThresholds(
            readyMin=96,
            waitMin=60,
            blockedMin=0
        )

    def evaluate_execution_readiness(
        self,
        risk_assessments: List[RiskAssessment],
        validation_results: List[ValidationResult],
        candidates: List[SignalCandidate],
        strategies: List[StrategyItem],
        market_state: MarketState
    ) -> List[ExecutionReadiness]:
        
        strategy_map = {s.id: s for s in strategies}
        candidate_map = {c.id: c for c in candidates}
        validation_map = {v.id: v for v in validation_results}
        
        readiness_list = []
        
        for i, risk in enumerate(risk_assessments, 1):
            candidate = candidate_map.get(risk.candidateId)
            validation = validation_map.get(risk.validationId)
            strategy = strategy_map.get(risk.strategyId)
            
            if not candidate or not validation or not strategy:
                continue

            # Deterministic duration
            duration_ms = 15 + (i * 7) % 26
            
            # Setup category scores and reasons
            category_scores = []
            reasons = []
            
            # 1. MARKET (Max: 15)
            market_open = market_state.marketOpen
            if market_open:
                m_score = 15
                m_desc = "Market is open and trading normally."
            else:
                m_score = 0
                m_desc = "Market is closed."
                reasons.append(ReadinessReason(
                    title="Market Closed",
                    description="Execution is blocked because the market is currently closed.",
                    severity=ReadinessSeverity.CRITICAL,
                    isBlocking=True
                ))
            category_scores.append(ReadinessCategoryScore(
                category=ReadinessCategory.MARKET,
                score=m_score,
                maxScore=15,
                percentage=int((m_score / 15) * 100),
                description=m_desc
            ))

            # 2. SESSION (Max: 15)
            session = market_state.session or "Closed"
            session_lower = session.lower()
            if "london" in session_lower or "new york" in session_lower or "ny" in session_lower:
                s_score = 15
                s_desc = f"Active session '{session}' matches optimal trading sessions."
            elif "asian" in session_lower or "asia" in session_lower or "tokyo" in session_lower:
                s_score = 10
                s_desc = f"Active session '{session}' has reduced liquidity."
                reasons.append(ReadinessReason(
                    title="Suboptimal Trading Session",
                    description=f"The current session '{session}' is active, but offers lower volume and liquidity.",
                    severity=ReadinessSeverity.WARNING,
                    isBlocking=False
                ))
            else:
                s_score = 0
                s_desc = f"Trading session is closed or inactive ('{session}')."
                reasons.append(ReadinessReason(
                    title="Weekend / Closed Session",
                    description="The trading session is currently closed.",
                    severity=ReadinessSeverity.CRITICAL,
                    isBlocking=True
                ))
            category_scores.append(ReadinessCategoryScore(
                category=ReadinessCategory.SESSION,
                score=s_score,
                maxScore=15,
                percentage=int((s_score / 15) * 100),
                description=s_desc
            ))

            # 3. SPREAD (Max: 15)
            spread = candidate.marketSnapshot.spread
            if spread <= 0.40:
                sp_score = 15
                sp_desc = f"Spread of {spread:.2f} pips is within preferred limits (<= 0.40)."
            elif spread <= 0.60:
                sp_score = 8
                sp_desc = f"Spread of {spread:.2f} pips is slightly elevated, but acceptable."
                reasons.append(ReadinessReason(
                    title="Elevated Spread Warning",
                    description=f"Current spread is {spread:.2f} pips, which is slightly above the ideal 0.40 limit.",
                    severity=ReadinessSeverity.WARNING,
                    isBlocking=False
                ))
            else:
                sp_score = 0
                sp_desc = f"Spread of {spread:.2f} pips exceeds maximum threshold (> 0.60)."
                reasons.append(ReadinessReason(
                    title="Spread Exceeds Threshold",
                    description=f"Execution spread of {spread:.2f} pips is wider than the maximum allowed limit of 0.60 pips.",
                    severity=ReadinessSeverity.CRITICAL,
                    isBlocking=True
                ))
            category_scores.append(ReadinessCategoryScore(
                category=ReadinessCategory.SPREAD,
                score=sp_score,
                maxScore=15,
                percentage=int((sp_score / 15) * 100),
                description=sp_desc
            ))

            # 4. VOLATILITY (Max: 10)
            volatility = candidate.marketSnapshot.volatility
            if volatility == "Extreme":
                v_score = 3
                v_desc = "Market volatility is extreme. Elevated slippage risk."
                reasons.append(ReadinessReason(
                    title="Extreme Volatility",
                    description="Market volatility is extreme. Execution might experience significant slippage.",
                    severity=ReadinessSeverity.WARNING,
                    isBlocking=False
                ))
            else:
                v_score = 10
                v_desc = f"Volatility is '{volatility}' which is suitable for standard execution."
            category_scores.append(ReadinessCategoryScore(
                category=ReadinessCategory.VOLATILITY,
                score=v_score,
                maxScore=10,
                percentage=int((v_score / 10) * 100),
                description=v_desc
            ))

            # 5. NEWS (Max: 15)
            news_impact = candidate.marketSnapshot.newsImpact
            if news_impact == "High":
                n_score = 0
                n_desc = "High-impact news is imminent."
                reasons.append(ReadinessReason(
                    title="High Impact News Block",
                    description="Execution is blocked due to proximity to high-impact economic news.",
                    severity=ReadinessSeverity.CRITICAL,
                    isBlocking=True
                ))
            elif news_impact == "Medium":
                n_score = 7
                n_desc = "Medium-impact news event scheduled near execution window."
                reasons.append(ReadinessReason(
                    title="Upcoming Medium News",
                    description="Medium impact news event scheduled near execution window.",
                    severity=ReadinessSeverity.WARNING,
                    isBlocking=False
                ))
            else:
                n_score = 15
                n_desc = "No high-impact economic news near execution window."
            category_scores.append(ReadinessCategoryScore(
                category=ReadinessCategory.NEWS,
                score=n_score,
                maxScore=15,
                percentage=int((n_score / 15) * 100),
                description=n_desc
            ))

            # 6. RISK (Max: 15)
            risk_level = risk.riskLevel
            risk_status = risk.status
            if risk_status.value == "BLOCKED" or risk_level.value == "EXTREME":
                r_score = 0
                r_desc = "Upstream risk level is EXTREME, or risk assessment is BLOCKED."
                reasons.append(ReadinessReason(
                    title="Risk Level Blocked",
                    description="The risk assessment status is blocked or risk level is extreme.",
                    severity=ReadinessSeverity.CRITICAL,
                    isBlocking=True
                ))
            elif risk_level.value == "HIGH":
                r_score = 5
                r_desc = "Upstream risk level is HIGH."
                reasons.append(ReadinessReason(
                    title="High Risk Warning",
                    description="Position risk level is high. Reduce trade size if proceeding.",
                    severity=ReadinessSeverity.WARNING,
                    isBlocking=False
                ))
            elif risk_level.value == "MEDIUM":
                r_score = 10
                r_desc = "Upstream risk level is MEDIUM."
                reasons.append(ReadinessReason(
                    title="Medium Risk Warning",
                    description="Position risk level is medium. Monitor exposure.",
                    severity=ReadinessSeverity.WARNING,
                    isBlocking=False
                ))
            else:
                r_score = 15
                r_desc = "Upstream risk assessment is LOW."
            category_scores.append(ReadinessCategoryScore(
                category=ReadinessCategory.RISK,
                score=r_score,
                maxScore=15,
                percentage=int((r_score / 15) * 100),
                description=r_desc
            ))

            # 7. VALIDATION (Max: 10)
            val_status = validation.status
            if val_status.value == "FAILED":
                val_score = 0
                val_desc = "Technical validation has FAILED."
                reasons.append(ReadinessReason(
                    title="Failed Technical Validation",
                    description="The signal candidate failed the required technical validation checks.",
                    severity=ReadinessSeverity.CRITICAL,
                    isBlocking=True
                ))
            elif val_status.value == "PARTIALLY_PASSED":
                val_score = 5
                val_desc = "Technical validation has PARTIALLY PASSED."
                reasons.append(ReadinessReason(
                    title="Partial Technical Validation",
                    description="Technical indicators are mixed, resulting in partial validation pass.",
                    severity=ReadinessSeverity.WARNING,
                    isBlocking=False
                ))
            else:
                val_score = 10
                val_desc = "Technical validation has fully PASSED."
            category_scores.append(ReadinessCategoryScore(
                category=ReadinessCategory.VALIDATION,
                score=val_score,
                maxScore=10,
                percentage=int((val_score / 10) * 100),
                description=val_desc
            ))

            # 8. SYSTEM (Max: 5)
            all_providers = provider_registry.get_all_providers()
            offline_providers = [p for p in all_providers if not p.is_online]
            
            critical_names = ["MockPriceProvider", "MockIndicatorProvider", "price_provider", "indicator_provider", "Mock Price Provider", "Mock Indicator Provider"]
            critical_offline = []
            non_critical_offline = []
            
            for p in offline_providers:
                p_name = p.provider_name
                if p_name in critical_names or "price" in p_name.lower() or "indicator" in p_name.lower():
                    critical_offline.append(p_name)
                else:
                    non_critical_offline.append(p_name)

            if critical_offline:
                sys_score = 0
                sys_desc = "Critical system provider(s) offline. Execution blocked."
                reasons.append(ReadinessReason(
                    title="Critical Provider Offline",
                    description=f"Critical providers are offline: {', '.join(critical_offline)}",
                    severity=ReadinessSeverity.CRITICAL,
                    isBlocking=True
                ))
            elif non_critical_offline:
                sys_score = 2
                sys_desc = "Some non-critical system providers are offline."
                reasons.append(ReadinessReason(
                    title="Provider Offline",
                    description=f"One or more non-critical providers are offline: {', '.join(non_critical_offline)}",
                    severity=ReadinessSeverity.WARNING,
                    isBlocking=False
                ))
            else:
                sys_score = 5
                sys_desc = "All system providers are online and functioning normally."
                
            category_scores.append(ReadinessCategoryScore(
                category=ReadinessCategory.SYSTEM,
                score=sys_score,
                maxScore=5,
                percentage=int((sys_score / 5) * 100),
                description=sys_desc
            ))

            # Total score
            overallReadinessScore = sum(c.score for c in category_scores)
            
            if not reasons:
                reasons.append(ReadinessReason(
                    title="Risk Parameters Normal",
                    description="All execution metrics fall within acceptable parameters.",
                    severity=ReadinessSeverity.INFO,
                    isBlocking=False
                ))

            # Overall Status & Recommendation mapping
            is_blocked = any(r.isBlocking for r in reasons)
            
            if is_blocked:
                status = ExecutionReadinessStatus.BLOCKED
                
                # Determine specific retry guidance
                primary_block = "current block resolved"
                for r in reasons:
                    if r.isBlocking:
                        if "Market Closed" in r.title:
                            primary_block = "When market opens"
                            break
                        elif "Session" in r.title:
                            primary_block = "At London Open"
                            break
                        elif "News" in r.title:
                            primary_block = "After news release"
                            break
                        elif "Spread" in r.title:
                            primary_block = "When spread <= 0.40"
                            break
                        elif "Validation" in r.title:
                            primary_block = "After indicator recalculation"
                            break
                        elif "Risk" in r.title:
                            primary_block = "After risk parameters adjustment"
                        elif "Provider" in r.title:
                            primary_block = "When providers are online"
                
                recommendation = ReadinessRecommendation(
                    action=ReadinessAction.BLOCK,
                    title="Execution Blocked",
                    description="Critical operational conditions are blocking execution. Do not proceed.",
                    nextReviewIn=primary_block
                )
            elif overallReadinessScore >= self.thresholds.readyMin:
                status = ExecutionReadinessStatus.READY
                recommendation = ReadinessRecommendation(
                    action=ReadinessAction.PROCEED,
                    title="Execution Ready",
                    description="All system, market, and validation parameters satisfy requirements. Ready to execute.",
                    nextReviewIn="Immediate"
                )
            else:
                status = ExecutionReadinessStatus.WAIT
                
                # Awaiting better conditions
                next_review = "15 minutes"
                for r in reasons:
                    if "Session" in r.title:
                        next_review = "At London Open"
                        break
                    elif "Spread" in r.title:
                        next_review = "When spread <= 0.40"
                        break
                    elif "News" in r.title:
                        next_review = "After news release"
                        break
                    elif "Volatility" in r.title:
                        next_review = "When volatility normalizes"
                        break
                
                recommendation = ReadinessRecommendation(
                    action=ReadinessAction.WAIT,
                    title="Execution Paused",
                    description="Readiness score is below preferred thresholds. Await more favorable conditions.",
                    nextReviewIn=next_review
                )

            # Execution market snapshot
            snapshot = ExecutionMarketSnapshot(
                session=session,
                spread=spread,
                volatility=volatility,
                newsImpact=news_impact,
                marketSentiment=candidate.marketSnapshot.marketSentiment,
                marketConfidence=candidate.marketSnapshot.marketConfidence,
                marketOpen=market_open,
                dataAgeSeconds=market_state.dataAgeSeconds
            )

            timestamp = datetime.now(timezone.utc)
            
            readiness = ExecutionReadiness(
                id=f"execution-{i:03d}",
                candidateId=candidate.id,
                validationId=validation.id,
                riskAssessmentId=risk.id,
                strategyId=risk.strategyId,
                status=status,
                overallReadinessScore=overallReadinessScore,
                thresholds=self.thresholds,
                recommendation=recommendation,
                categoryScores=category_scores,
                reasons=reasons,
                marketSnapshot=snapshot,
                candidateStatus=candidate.status,
                validationStatus=validation.status,
                riskLevel=risk.riskLevel,
                riskStatus=risk.status,
                evaluatedAt=timestamp,
                evaluationDurationMs=duration_ms
            )

            # Event Bus Publish
            event_payload = {
                "eventName": "ExecutionReadinessCompleted",
                "artifactId": readiness.id,
                "artifactType": "ExecutionReadiness",
                "pipelineStage": "EXECUTION",
                "engineVersion": self.version,
                "candidateId": readiness.candidateId,
                "validationId": readiness.validationId,
                "riskAssessmentId": readiness.riskAssessmentId,
                "strategyId": readiness.strategyId,
                "timestamp": timestamp.isoformat()
            }
            print(f"[EVENT BUS] {json.dumps(event_payload)}")
            
            readiness_list.append(readiness)

        return readiness_list
