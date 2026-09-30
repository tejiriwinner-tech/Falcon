import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.core.repository.mission_repository import mission_repository
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
    DecisionRecommendation,
)

logger = logging.getLogger("falcon.decision_artifacts")
router = APIRouter()

market_state_engine = MarketStateEngine()
strategy_engine = StrategyEngine()
signal_generation_engine = SignalGenerationEngine()
validation_engine = ValidationEngine()
risk_engine = RiskEngine()
execution_readiness_engine = ExecutionReadinessEngine()
decision_engine = DecisionEngine()

_cache_response: Optional[DecisionArtifactListResponse] = None
_cache_time: Optional[datetime] = None
CACHE_TTL_SECONDS: float = 30.0


def _build_summary(decisions: List[DecisionArtifact]) -> DecisionSummary:
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

    return DecisionSummary(
        totalDecisions=total,
        buyCount=buy_cnt,
        sellCount=sell_cnt,
        waitCount=wait_cnt,
        monitorCount=mon_cnt,
        noTradeCount=no_trade_cnt,
        highestConfidence=high_conf,
        lowestConfidence=low_conf,
        averageConfidence=avg_conf,
    )


@router.get("/decision-artifacts", response_model=DecisionArtifactListResponse)
def get_decision_artifacts():
    """
    Returns stored DecisionArtifacts from recent missions along with calculated summary.
    If no stored missions exist, executes the intelligence pipeline and caches the result.
    """
    global _cache_response, _cache_time
    now = datetime.now(timezone.utc)

    # In-memory cache fast path (< 0.1ms)
    if _cache_response and _cache_time:
        if (now - _cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return _cache_response

    # Fast path: check repository for recent stored mission decisions (LIMIT 3)
    missions = None
    try:
        missions = mission_repository.get_recent_missions(limit=3)
    except Exception:
        pass
    if not missions:
        try:
            all_m = mission_repository.get_all_missions()
            if all_m:
                missions = all_m[-3:]
        except Exception:
            missions = []

    decisions: List[DecisionArtifact] = []
    if missions:
        mission_ids = [m.id for m in missions]
        if hasattr(mission_repository, "get_all_mission_artifacts_bulk"):
            try:
                bulk = mission_repository.get_all_mission_artifacts_bulk(mission_ids) or {}
                for m in reversed(missions):
                    art = bulk.get(m.id) or {}
                    decisions.extend(art.get("decisions", []))
            except Exception:
                pass
        if not decisions:
            for m in reversed(missions):
                art = mission_repository.get_mission_artifacts(m.id) or {}
                decisions.extend(art.get("decisions", []))

    if decisions:
        summary = _build_summary(decisions)
        resp = DecisionArtifactListResponse(
            decisions=decisions,
            summary=summary,
            lastUpdated=now,
        )
        _cache_response = resp
        _cache_time = now
        return resp

    # Cold fallback: compute via engines
    try:
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
    except Exception as exc:
        logger.warning(f"Error computing decision artifacts: {exc}")
        decisions = []

    summary = _build_summary(decisions)
    response = DecisionArtifactListResponse(
        decisions=decisions,
        summary=summary,
        lastUpdated=now,
    )
    _cache_response = response
    _cache_time = now
    return response


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
