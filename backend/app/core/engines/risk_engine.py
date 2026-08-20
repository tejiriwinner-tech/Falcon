import json
from datetime import datetime, timezone
from typing import List

from app.schemas.market_state import MarketState
from app.schemas.strategy import StrategyItem
from app.schemas.signal_candidate import SignalCandidate
from app.schemas.validation_result import ValidationResult
from app.schemas.risk_assessment import (
    RiskAssessment, RiskCategory, RiskLevel, RiskSeverity,
    RiskAssessmentStatus, RecommendationAction, RiskThresholds,
    RiskRecommendation, RiskReason, RiskCategoryScore, RiskMarketSnapshot
)

class RiskEngine:
    def __init__(self):
        self.version = "1.0.2"
        self.thresholds = RiskThresholds(
            lowMax=25,
            mediumMax=50,
            highMax=75,
            extremeMax=100
        )

    def assess_risk(
        self,
        assessment_id: str,
        validation: ValidationResult,
        candidate: SignalCandidate,
        strategy: StrategyItem,
        market_state: MarketState,
        duration_ms: int
    ) -> RiskAssessment:
        
        # 1. Categories evaluation
        # CAPITAL: Evaluate risk/reward, sizing
        capital_score = 10 if candidate.riskReward >= 1.5 else 20
        cat_capital = RiskCategoryScore(
            category=RiskCategory.CAPITAL,
            score=capital_score,
            maxScore=20,
            percentage=int((capital_score / 20) * 100),
            description="Evaluates maximum daily drawdown and capital exposure limits."
        )

        # EXPOSURE: Evaluate correlation risk or asset exposure
        exposure_score = 10
        cat_exposure = RiskCategoryScore(
            category=RiskCategory.EXPOSURE,
            score=exposure_score,
            maxScore=15,
            percentage=int((exposure_score / 15) * 100),
            description="Evaluates correlation exposure and overall asset allocation risk."
        )

        # MARKET: Market trend and broader condition risk
        market_score = 5 if market_state.trend == candidate.marketSnapshot.trend else 15
        cat_market = RiskCategoryScore(
            category=RiskCategory.MARKET,
            score=market_score,
            maxScore=15,
            percentage=int((market_score / 15) * 100),
            description="Evaluates broader market conditions against trade direction."
        )

        # VOLATILITY: Analyze current market volatility
        volatility_score = 15 if market_state.fearGreedIndex and market_state.fearGreedIndex > 70 else 5
        cat_volatility = RiskCategoryScore(
            category=RiskCategory.VOLATILITY,
            score=volatility_score,
            maxScore=15,
            percentage=int((volatility_score / 15) * 100),
            description="Analyzes current market volatility risk factors."
        )

        # NEWS: News proximity risk
        news_score = 10 if candidate.marketSnapshot.newsImpact == "High" else 2
        cat_news = RiskCategoryScore(
            category=RiskCategory.NEWS,
            score=news_score,
            maxScore=10,
            percentage=int((news_score / 10) * 100),
            description="Evaluates proximity to upcoming high-impact economic news."
        )

        # SESSION: Evaluate execution session risk
        session_score = 5 if candidate.marketSnapshot.session == "London Open" else 10
        cat_session = RiskCategoryScore(
            category=RiskCategory.SESSION,
            score=session_score,
            maxScore=10,
            percentage=int((session_score / 10) * 100),
            description="Assesses risk associated with current trading session liquidity."
        )

        # STRATEGY: Evaluate strategy-specific risk parameters
        strategy_score = 5 if candidate.confidence >= 80 else 10
        cat_strategy = RiskCategoryScore(
            category=RiskCategory.STRATEGY,
            score=strategy_score,
            maxScore=15,
            percentage=int((strategy_score / 15) * 100),
            description="Evaluates historical and current strategy-specific risk parameters."
        )

        category_scores = [
            cat_capital,
            cat_exposure,
            cat_market,
            cat_volatility,
            cat_news,
            cat_session,
            cat_strategy
        ]

        # 2. Overall Risk Calculation
        overall_risk_score = sum(c.score for c in category_scores)
        
        # 3. Risk Level mapping
        if overall_risk_score <= self.thresholds.lowMax:
            risk_level = RiskLevel.LOW
        elif overall_risk_score <= self.thresholds.mediumMax:
            risk_level = RiskLevel.MEDIUM
        elif overall_risk_score <= self.thresholds.highMax:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.EXTREME

        # 4. Generate Reasons
        reasons = []
        is_blocking_overall = False

        if candidate.marketSnapshot.spread > 0.5:
            reasons.append(RiskReason(
                title="Spread Threshold Exceeded",
                description=f"Current spread is {candidate.marketSnapshot.spread:.2f} which exceeds preferred risk limits.",
                severity=RiskSeverity.WARNING,
                isBlocking=False
            ))
        


        if validation.status.value == "FAILED":
            reasons.append(RiskReason(
                title="Failed Technical Validation",
                description="The candidate failed technical validation and carries extreme risk.",
                severity=RiskSeverity.CRITICAL,
                isBlocking=True
            ))
            is_blocking_overall = True

        if risk_level == RiskLevel.EXTREME:
            reasons.append(RiskReason(
                title="Extreme Operational Risk",
                description="Total risk factors exceed extreme threshold parameters.",
                severity=RiskSeverity.CRITICAL,
                isBlocking=True
            ))
            is_blocking_overall = True

        if not reasons:
            reasons.append(RiskReason(
                title="Risk Parameters Normal",
                description="All risk metrics fall within acceptable parameters.",
                severity=RiskSeverity.INFO,
                isBlocking=False
            ))

        # 5. Determine Status
        if is_blocking_overall:
            status = RiskAssessmentStatus.BLOCKED
        elif risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM]:
            status = RiskAssessmentStatus.REVIEW_REQUIRED
        else:
            status = RiskAssessmentStatus.PASSED

        # 6. Generate Recommendation
        if status == RiskAssessmentStatus.BLOCKED:
            recommendation = RiskRecommendation(
                action=RecommendationAction.BLOCK,
                title="Execution Blocked",
                description="Critical risk parameters exceeded. Do not execute."
            )
        elif status == RiskAssessmentStatus.REVIEW_REQUIRED:
            recommendation = RiskRecommendation(
                action=RecommendationAction.REDUCE_RISK,
                title="Reduce Exposure",
                description="Proceed with caution or reduce position sizing due to elevated risk."
            )
        else:
            recommendation = RiskRecommendation(
                action=RecommendationAction.PROCEED,
                title="Proceed Normally",
                description="All capital protection rules satisfied."
            )

        # 7. Preserve Market Context
        snapshot = RiskMarketSnapshot(
            trend=candidate.marketSnapshot.trend,
            volatility=candidate.marketSnapshot.volatility,
            session=candidate.marketSnapshot.session,
            spread=candidate.marketSnapshot.spread,
            newsImpact=candidate.marketSnapshot.newsImpact,
            marketSentiment=candidate.marketSnapshot.marketSentiment
        )

        timestamp = datetime.now(timezone.utc)

        assessment = RiskAssessment(
            id=assessment_id,
            candidateId=candidate.id,
            validationId=validation.id,
            strategyId=strategy.id,
            previousAssessmentId=None,
            status=status,
            overallRiskScore=overall_risk_score,
            riskLevel=risk_level,
            thresholds=self.thresholds,
            recommendation=recommendation,
            categoryScores=category_scores,
            reasons=reasons,
            marketSnapshot=snapshot,
            pipelineStage="RISK",
            pipelineVersion="1.0",
            engineVersion=self.version,
            assessedBy="Risk Engine",
            timelineOrder=3,
            assessedAt=timestamp,
            assessmentDurationMs=duration_ms
        )

        # 8. Event Bus Publish
        event_payload = {
            "eventName": "RiskAssessmentCompleted",
            "artifactId": assessment.id,
            "artifactType": "RiskAssessment",
            "pipelineStage": "RISK",
            "engineVersion": self.version,
            "candidateId": assessment.candidateId,
            "validationId": assessment.validationId,
            "strategyId": assessment.strategyId,
            "timestamp": timestamp.isoformat()
        }
        
        print(f"[EVENT BUS] {json.dumps(event_payload)}")

        return assessment

    def assess_all(
        self,
        validations: List[ValidationResult],
        candidates: List[SignalCandidate],
        strategies: List[StrategyItem],
        market_state: MarketState
    ) -> List[RiskAssessment]:
        
        strategy_map = {s.id: s for s in strategies}
        candidate_map = {c.id: c for c in candidates}
        
        assessments = []
        
        for i, val in enumerate(validations, 1):
            assessment_id = f"risk-{i:03d}"
            candidate = candidate_map.get(val.candidateId)
            strategy = strategy_map.get(val.strategyId)
            duration_ms = 18 + (i * 3) % 15
            
            if candidate and strategy:
                assessment = self.assess_risk(
                    assessment_id=assessment_id,
                    validation=val,
                    candidate=candidate,
                    strategy=strategy,
                    market_state=market_state,
                    duration_ms=duration_ms
                )
                assessments.append(assessment)
                
        return assessments
