from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from app.core.engines.market_state_engine import MarketStateEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.validation_engine import ValidationEngine
from app.core.engines.risk_engine import RiskEngine
from app.core.engines.execution_readiness_engine import ExecutionReadinessEngine

from app.schemas.execution_readiness import (
    ExecutionReadiness, ExecutionReadinessListResponse, ExecutionSummary, ExecutionReadinessStatus
)

router = APIRouter()

market_state_engine = MarketStateEngine()
strategy_engine = StrategyEngine()
signal_generation_engine = SignalGenerationEngine()
validation_engine = ValidationEngine()
risk_engine = RiskEngine()
execution_readiness_engine = ExecutionReadinessEngine()

@router.get("/execution-readiness", response_model=ExecutionReadinessListResponse)
def get_execution_readiness():
    """
    Runs the full Falcon intelligence pipeline up to the Execution stage.
    Returns the list of ExecutionReadiness artifacts and calculated summary.
    """
    market_state = market_state_engine.get_market_state()
    strategies = strategy_engine.get_strategies()
    candidates = signal_generation_engine.generate_candidates(market_state, strategies)
    validations = validation_engine.validate_candidates(candidates, strategies, market_state)
    assessments = risk_engine.assess_all(validations, candidates, strategies, market_state)
    readiness_items = execution_readiness_engine.evaluate_execution_readiness(
        assessments, validations, candidates, strategies, market_state
    )

    total = len(readiness_items)
    ready = sum(1 for a in readiness_items if a.status == ExecutionReadinessStatus.READY)
    waiting = sum(1 for a in readiness_items if a.status == ExecutionReadinessStatus.WAIT)
    blocked = sum(1 for a in readiness_items if a.status == ExecutionReadinessStatus.BLOCKED)
    avg_score = int(sum(a.overallReadinessScore for a in readiness_items) / total) if total > 0 else 0

    summary = ExecutionSummary(
        totalAssessments=total,
        ready=ready,
        waiting=waiting,
        blocked=blocked,
        averageReadinessScore=avg_score
    )

    return ExecutionReadinessListResponse(
        assessments=readiness_items,
        summary=summary,
        lastUpdated=datetime.now(timezone.utc)
    )

@router.get("/execution-readiness/{readiness_id}", response_model=ExecutionReadiness)
def get_execution_readiness_by_id(readiness_id: str):
    """
    Returns a single ExecutionReadiness artifact by its deterministic ID (e.g. execution-001).
    """
    market_state = market_state_engine.get_market_state()
    strategies = strategy_engine.get_strategies()
    candidates = signal_generation_engine.generate_candidates(market_state, strategies)
    validations = validation_engine.validate_candidates(candidates, strategies, market_state)
    assessments = risk_engine.assess_all(validations, candidates, strategies, market_state)
    readiness_items = execution_readiness_engine.evaluate_execution_readiness(
        assessments, validations, candidates, strategies, market_state
    )

    for item in readiness_items:
        if item.id == readiness_id:
            return item
            
    raise HTTPException(status_code=404, detail=f"Execution readiness artifact '{readiness_id}' not found.")
