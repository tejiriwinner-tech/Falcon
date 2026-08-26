"""
Falcon Phase 7 — Decision Context Builder

Builds the single immutable DecisionContext from all upstream pipeline artifacts.

Design rules:
  - Pure function: build_context() has no side effects and makes no external calls.
  - All inputs are Optional — missing data causes graceful degradation, never failure.
  - All derived/cached values are computed here ONCE so evaluators never recompute.
  - Fully deterministic: identical inputs produce identical outputs.
  - Fully testable in isolation without the pipeline running.

Architecture position:
  PipelineOrchestrator Stage 6 calls build_context() before running evaluators.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List

from app.schemas.decision_context import DecisionContext
from app.schemas.signal_candidate import SignalCandidate
from app.schemas.validation_result import ValidationResult
from app.schemas.risk_assessment import RiskAssessment
from app.schemas.execution_readiness import ExecutionReadiness
from app.schemas.strategy import StrategyItem
from app.schemas.market_state import MarketState
from app.schemas.market_regime import MarketRegimeReport

logger = logging.getLogger(__name__)


def build_context(
    candidate_id: str,
    mission_id: str,
    candidate: Optional[SignalCandidate] = None,
    validation: Optional[ValidationResult] = None,
    risk: Optional[RiskAssessment] = None,
    readiness: Optional[ExecutionReadiness] = None,
    strategy: Optional[StrategyItem] = None,
    market_state: Optional[MarketState] = None,
    regime_report: Optional[MarketRegimeReport] = None,
) -> DecisionContext:
    """
    Build an immutable DecisionContext from all upstream pipeline artifacts.

    This is the ONLY function that constructs a DecisionContext.
    All upstream data is normalised and cached here.

    Args:
        candidate_id:   ID of the signal candidate being evaluated
        mission_id:     Parent mission ID
        candidate:      Signal candidate artifact (Optional)
        validation:     ValidationResult for this candidate (Optional)
        risk:           RiskAssessment for this candidate (Optional)
        readiness:      ExecutionReadiness evaluation (Optional)
        strategy:       StrategyItem this candidate was generated from (Optional)
        market_state:   Full live MarketState at evaluation time (Optional)
        regime_report:  Most relevant MarketRegimeReport (Optional — added in M3)

    Returns:
        DecisionContext — immutable, fully populated, ready for evaluators
    """
    logger.debug(
        "Building DecisionContext for candidate=%s mission=%s",
        candidate_id, mission_id
    )

    # ── Derive cached market fields ──────────────────────────────────────────
    # Priority: candidate snapshot > market_state > defaults
    # Candidate snapshot is always more specific (it was recorded at signal time)

    spread = _derive_spread(candidate, market_state)
    session = _derive_session(candidate, market_state)
    trend = _derive_trend(candidate, market_state)
    volatility = _derive_volatility(candidate, market_state)
    news_impact = _derive_news_impact(candidate, market_state)
    market_open = market_state.marketOpen if market_state else False
    data_age = market_state.dataAgeSeconds if market_state else 0

    # ── Derive candidate-specific cached fields ──────────────────────────────
    candidate_direction = "WAIT"
    candidate_confidence = 0.0
    candidate_rr = 0.0

    if candidate is not None:
        candidate_direction = (
            candidate.direction.value
            if hasattr(candidate.direction, "value")
            else str(candidate.direction)
        )
        candidate_confidence = float(candidate.confidence)
        candidate_rr = float(candidate.riskReward)

    # ── Derive strategy-specific cached fields ───────────────────────────────
    strategy_id = ""
    strategy_name = "Unknown"
    preferred_sessions: List[str] = []
    minimum_confidence = 70.0
    minimum_rr = 1.5
    avoid_conditions: List[str] = []
    market_compatibility: List[str] = []

    if strategy is not None:
        strategy_id = strategy.id
        strategy_name = strategy.name
        preferred_sessions = list(strategy.preferredSessions or [])
        minimum_confidence = float(getattr(strategy, "minimumConfidence", 70.0))
        minimum_rr = float(getattr(strategy, "minimumRiskReward", 1.5))
        avoid_conditions = list(strategy.avoidConditions or [])
        market_compatibility = list(strategy.marketCompatibility or [])

    context = DecisionContext(
        candidateId=candidate_id,
        missionId=mission_id,
        candidate=candidate,
        validation=validation,
        risk=risk,
        readiness=readiness,
        strategy=strategy,
        marketState=market_state,
        regimeReport=regime_report,
        # Cached derived values
        spread=spread,
        session=session,
        trend=trend,
        volatility=volatility,
        newsImpact=news_impact,
        marketOpen=market_open,
        dataAgeSeconds=data_age,
        candidateDirection=candidate_direction,
        candidateConfidence=candidate_confidence,
        candidateRiskReward=candidate_rr,
        # Cached strategy fields
        strategyId=strategy_id,
        strategyName=strategy_name,
        preferredSessions=preferred_sessions,
        minimumConfidence=minimum_confidence,
        minimumRiskReward=minimum_rr,
        avoidConditions=avoid_conditions,
        marketCompatibility=market_compatibility,
        builtAt=datetime.now(timezone.utc),
        contextVersion="1.0",
    )

    logger.debug(
        "DecisionContext built: candidate=%s direction=%s trend=%s session=%s spread=%.4f",
        candidate_id, candidate_direction, trend, session, spread
    )

    return context


# ── Private helpers (pure functions) ─────────────────────────────────────────

def _derive_spread(
    candidate: Optional[SignalCandidate],
    market_state: Optional[MarketState],
) -> float:
    """Derive spread from candidate snapshot first, then market state."""
    if candidate is not None and hasattr(candidate, "marketSnapshot"):
        snap = candidate.marketSnapshot
        if snap is not None:
            spread = getattr(snap, "spread", None)
            if spread is not None:
                return float(spread)
    if market_state is not None:
        return float(getattr(market_state, "spread", 0.0))
    return 0.0


def _derive_session(
    candidate: Optional[SignalCandidate],
    market_state: Optional[MarketState],
) -> str:
    """Derive session from candidate snapshot first, then market state."""
    if candidate is not None and hasattr(candidate, "marketSnapshot"):
        snap = candidate.marketSnapshot
        if snap is not None:
            session = getattr(snap, "session", None)
            if session:
                return str(session)
    if market_state is not None:
        return str(getattr(market_state, "session", "Unknown"))
    return "Unknown"


def _derive_trend(
    candidate: Optional[SignalCandidate],
    market_state: Optional[MarketState],
) -> str:
    """Derive trend from candidate snapshot first, then market state."""
    if candidate is not None and hasattr(candidate, "marketSnapshot"):
        snap = candidate.marketSnapshot
        if snap is not None:
            trend = getattr(snap, "trend", None)
            if trend:
                return str(trend)
    if market_state is not None:
        return str(getattr(market_state, "trend", "Neutral"))
    return "Neutral"


def _derive_volatility(
    candidate: Optional[SignalCandidate],
    market_state: Optional[MarketState],
) -> str:
    """Derive volatility from candidate snapshot first, then market state."""
    if candidate is not None and hasattr(candidate, "marketSnapshot"):
        snap = candidate.marketSnapshot
        if snap is not None:
            vol = getattr(snap, "volatility", None)
            if vol:
                return str(vol)
    if market_state is not None:
        return str(getattr(market_state, "volatility", "Moderate"))
    return "Moderate"


def _derive_news_impact(
    candidate: Optional[SignalCandidate],
    market_state: Optional[MarketState],
) -> str:
    """Derive news impact from candidate snapshot first, then market state."""
    if candidate is not None and hasattr(candidate, "marketSnapshot"):
        snap = candidate.marketSnapshot
        if snap is not None:
            impact = getattr(snap, "newsImpact", None)
            if impact:
                return str(impact)
    if market_state is not None:
        return str(getattr(market_state, "currentNewsImpact", "Low"))
    return "Low"
