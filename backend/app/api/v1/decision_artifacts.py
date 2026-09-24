from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from app.core.engines.market_state_engine import MarketStateEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.validation_engine import ValidationEngine
from app.core.engines.risk_engine import RiskEngine
from app.core.engines.execution_readiness_engine import ExecutionReadinessEngine
from app.core.engines.decision_engine import DecisionEngine
from app.core.services.research_promotion_service import research_promotion_service

from app.schemas.decision_artifact import (
    DecisionArtifact,
    DecisionArtifactListResponse,
    DecisionSummary,
    DecisionRecommendation
)

router = APIRouter()

market_state_engine = MarketStateEngine()
strategy_engine = StrategyEngine()
signal_generation_engine = SignalGenerationEngine()
validation_engine = ValidationEngine()
risk_engine = RiskEngine()
execution_readiness_engine = ExecutionReadinessEngine()
decision_engine = DecisionEngine()

@router.get("/decision-artifacts", response_model=DecisionArtifactListResponse)
def get_decision_artifacts():
    """
    Runs the complete 5-stage Falcon intelligence pipeline up to the Decision stage.
    Returns the list of DecisionArtifacts and calculated summary.
    """
    market_state = market_state_engine.get_market_state()
    strategies = strategy_engine.get_strategies()
    research_contexts = research_promotion_service.get_active_promoted_contexts()
    candidates = signal_generation_engine.generate_candidates(
        market_state, strategies, research_contexts=research_contexts
    )
    validations = validation_engine.validate_candidates(candidates, strategies, market_state)
    assessments = risk_engine.assess_all(validations, candidates, strategies, market_state)
    readiness_items = execution_readiness_engine.evaluate_execution_readiness(
        assessments, validations, candidates, strategies, market_state
    )
    decisions = decision_engine.generate_decisions(
        readiness_items, assessments, validations, candidates, strategies, market_state
    )

    total = len(decisions)
    buy_cnt = sum(1 for d in decisions if d.recommendation == DecisionRecommendation.BUY)
    sell_cnt = sum(1 for d in decisions if d.recommendation == DecisionRecommendation.SELL)
    wait_cnt = sum(1 for d in decisions if d.recommendation == DecisionRecommendation.WAIT)
    mon_cnt = sum(1 for d in decisions if d.recommendation == DecisionRecommendation.MONITOR)
    no_trade_cnt = sum(1 for d in decisions if d.recommendation == DecisionRecommendation.NO_TRADE)

    confidences = [d.decisionConfidence for d in decisions]
    high_conf = max(confidences, default=0.0)
    low_conf = min(confidences, default=0.0)
    avg_conf = round(sum(confidences) / total, 1) if total > 0 else 0.0

    summary = DecisionSummary(
        totalDecisions=total,
        buyCount=buy_cnt,
        sellCount=sell_cnt,
        waitCount=wait_cnt,
        monitorCount=mon_cnt,
        noTradeCount=no_trade_cnt,
        highestConfidence=high_conf,
        lowestConfidence=low_conf,
        averageConfidence=avg_conf
    )

    return DecisionArtifactListResponse(
        decisions=decisions,
        summary=summary,
        lastUpdated=datetime.now(timezone.utc)
    )

@router.get("/decision-artifacts/{decision_id}", response_model=DecisionArtifact)
def get_decision_artifact_by_id(decision_id: str):
    """
    Returns a single decision artifact by ID.
    """
    res = get_decision_artifacts()
    for decision in res.decisions:
        if decision.id == decision_id:
            return decision
    raise HTTPException(status_code=404, detail="Decision artifact not found")
