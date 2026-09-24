from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.core.engines.market_state_engine import MarketStateEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.services.research_promotion_service import research_promotion_service
from app.schemas.signal_candidate import SignalCandidate, SignalCandidateListResponse

router = APIRouter()

market_state_engine = MarketStateEngine()
strategy_engine = StrategyEngine()
signal_generation_engine = SignalGenerationEngine()

@router.get("/signal-candidates", response_model=SignalCandidateListResponse)
def get_signal_candidates():
    """
    Returns the list of generated, waiting, and rejected signal candidates
    from the Signal Generation Engine for all active trading strategies.
    """
    market_state = market_state_engine.get_market_state()
    strategies = strategy_engine.get_strategies()
    research_contexts = research_promotion_service.get_active_promoted_contexts()
    candidates = signal_generation_engine.generate_candidates(
        market_state, strategies, research_contexts=research_contexts
    )
    return SignalCandidateListResponse(
        candidates=candidates,
        lastUpdated=datetime.now(timezone.utc)
    )

@router.get("/signal-candidates/{candidate_id}", response_model=SignalCandidate)
def get_signal_candidate(candidate_id: str):
    """
    Returns a single SignalCandidate artifact by its deterministic ID (e.g. cand-001).
    Returns 404 if no candidate with the given ID exists.
    """
    market_state = market_state_engine.get_market_state()
    strategies = strategy_engine.get_strategies()
    research_contexts = research_promotion_service.get_active_promoted_contexts()
    candidates = signal_generation_engine.generate_candidates(
        market_state, strategies, research_contexts=research_contexts
    )
    for candidate in candidates:
        if candidate.id == candidate_id:
            return candidate
    raise HTTPException(status_code=404, detail=f"Signal candidate '{candidate_id}' not found.")
