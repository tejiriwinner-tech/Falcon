from typing import List, Optional
from app.schemas.market_state import MarketState
from app.schemas.strategy import StrategyItem, StrategyValidation
from app.schemas.decision_engine import RiskAssessment, ExecutionReadiness

class ExecutionEngine:
    def __init__(self):
        self.version = "1.0.0"

    def assess_readiness(
        self,
        strategy: StrategyItem,
        market_state: MarketState,
        validation: StrategyValidation,
        risk_assessment: RiskAssessment
    ) -> ExecutionReadiness:
        passed_checks = []
        blocking_conditions = []
        
        # Check market open
        if market_state.marketOpen:
            passed_checks.append("Market is open")
        else:
            blocking_conditions.append("Market is closed")

        # Check sessions
        if market_state.session in strategy.preferredSessions or any(s in market_state.session for s in strategy.preferredSessions):
            passed_checks.append(f"Active session matches preferred sessions ({', '.join(strategy.preferredSessions)})")
        else:
            blocking_conditions.append(f"Active session ({market_state.session}) does not match preferred sessions ({', '.join(strategy.preferredSessions)})")

        # Check validation failed checks
        if not validation.failedChecks:
            passed_checks.append("All technical validation checks passed")
        else:
            blocking_conditions.extend(validation.failedChecks)

        # Check strategy status
        if strategy.readyForExecution and strategy.status == "ACTIVE":
            passed_checks.append("Strategy is active and ready for execution")
        else:
            blocking_conditions.append(f"Strategy status is {strategy.status}")

        # Check news filter
        if not market_state.upcomingHighImpactNews:
            passed_checks.append("No imminent high-impact news events")
        else:
            blocking_conditions.append("High-impact news event expected within 20 minutes")

        is_ready = len(blocking_conditions) == 0
        
        # Simple readiness score calculation
        total_checks = len(passed_checks) + len(blocking_conditions)
        score = int((len(passed_checks) / total_checks) * 100) if total_checks > 0 else 0

        # Estimated wait time
        est_wait = None
        if not is_ready:
            if "High-impact news event expected within 20 minutes" in blocking_conditions:
                est_wait = "18 minutes"
            elif "London" in strategy.bestSession and "Asian" in market_state.session:
                est_wait = "5 hours"
            else:
                est_wait = "14 minutes"

        return ExecutionReadiness(
            isReady=is_ready,
            overallReadinessScore=score,
            blockingConditions=blocking_conditions,
            passedChecks=passed_checks,
            estimatedTimeUntilReady=est_wait
        )
