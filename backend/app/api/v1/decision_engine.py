from fastapi import APIRouter
from app.schemas.decision_engine import DecisionEngineResponse, RiskAssessment, ExecutionReadiness
from app.schemas.strategy import StrategyValidation, StrategyValidationCheck, MarketSnapshot
from app.core.engines.market_state_engine import MarketStateEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.validation_engine import ValidationEngine
from app.core.engines.risk_engine import RiskEngine
from app.core.engines.decision_engine import DecisionEngine

router = APIRouter()

# Instantiate engines
market_state_engine = MarketStateEngine()
strategy_engine = StrategyEngine()
signal_generation_engine = SignalGenerationEngine()
validation_engine = ValidationEngine()
risk_engine = RiskEngine()
decision_engine = DecisionEngine()

@router.get("/decision-engine", response_model=DecisionEngineResponse)
def get_decision_engine():
    """
    Returns the latest decision engine evaluation, weighted confidence score,
    rejection reasons, missing conditions, and narrative briefings.

    Runs the full Falcon pipeline:
      MarketState → SignalCandidates → ValidationResults → RiskAssessments → Decision
    Selects the primary (first) candidate's pipeline artifacts and adapts them
    into the DecisionEngine contract.
    """
    # 1. Run the full pipeline
    market_state = market_state_engine.get_market_state()
    strategies = strategy_engine.get_strategies()
    candidates = signal_generation_engine.generate_candidates(market_state, strategies)
    validations = validation_engine.validate_candidates(candidates, strategies, market_state)
    assessments = risk_engine.assess_all(validations, candidates, strategies, market_state)

    # 2. Select the primary strategy (strat-001 preferred, else first active)
    strategy = strategy_engine.get_strategy_by_id("strat-001")
    if not strategy:
        strategy = strategies[0] if strategies else None

    # 3. Find the pipeline artifacts for this strategy
    primary_validation = next(
        (v for v in validations if v.strategyId == strategy.id),
        validations[0] if validations else None
    )
    primary_assessment = next(
        (a for a in assessments if a.strategyId == strategy.id),
        assessments[0] if assessments else None
    )

    # 4. Bridge: ValidationResult → StrategyValidation (old contract)
    #    Maps the new immutable ValidationResult to the shape DecisionEngine.get_decision() expects.
    failed_check_titles = [
        c.title for c in primary_validation.checks if not c.passed
    ] if primary_validation else []

    bridge_checks = [
        StrategyValidationCheck(
            name=c.title,
            passed=c.passed,
            value=f"{c.scoreAwarded}/{c.weight}"
        )
        for c in primary_validation.checks
    ] if primary_validation else []

    bridge_snapshot = MarketSnapshot(
        trend=market_state.trend,
        volatility=market_state.volatility,
        liquidity=market_state.liquidity,
        news=market_state.currentNewsImpact,
        session=market_state.session,
        spread=market_state.spread,
        atr=0.0,
        rsi=50.0,
        ema200="above",
        adx=25.0
    )

    bridge_validation = StrategyValidation(
        score=primary_validation.validationScore if primary_validation else 0,
        aiConfidence=primary_validation.validationScore if primary_validation else 0,
        validationDurationSeconds=(primary_validation.validationDurationMs / 1000.0) if primary_validation else 0.0,
        failedChecks=failed_check_titles,
        checks=bridge_checks,
        marketSnapshot=bridge_snapshot
    )

    # 5. Bridge: RiskAssessment (pipeline) → RiskAssessment (decision engine schema)
    bridge_risk = RiskAssessment(
        accountRiskPercent=1.0,
        maxDrawdown=5.0,
        positionSizeRecommendation=0.10,
        riskFactors=[r.title for r in primary_assessment.reasons] if primary_assessment else []
    )

    # 6. Bridge: RiskAssessment (pipeline) → ExecutionReadiness (decision engine schema)
    blocking = [r.title for r in primary_assessment.reasons if r.isBlocking] if primary_assessment else []
    passed_items = [r.title for r in primary_assessment.reasons if not r.isBlocking] if primary_assessment else []
    is_ready = (
        primary_assessment is not None and
        not blocking and
        primary_validation is not None and
        primary_validation.validationScore >= 85
    )

    bridge_readiness = ExecutionReadiness(
        isReady=is_ready,
        overallReadinessScore=primary_validation.validationScore if primary_validation else 0,
        blockingConditions=blocking + failed_check_titles,
        passedChecks=passed_items,
        estimatedTimeUntilReady=None if is_ready else "Awaiting confirmation"
    )

    # 7. Run the DecisionEngine with bridged artifacts
    decision_response = decision_engine.get_decision(
        strategy=strategy,
        market_state=market_state,
        validation=bridge_validation,
        risk_assessment=bridge_risk,
        readiness=bridge_readiness
    )

    return decision_response
