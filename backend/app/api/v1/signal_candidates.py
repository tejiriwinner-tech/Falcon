import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.core.repository.mission_repository import mission_repository
from app.core.engines.market_state_engine import MarketStateEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.services.research_promotion_service import research_promotion_service
from app.schemas.signal_candidate import SignalCandidate, SignalCandidateListResponse

logger = logging.getLogger("falcon.signal_candidates")
router = APIRouter()

market_state_engine = MarketStateEngine()
strategy_engine = StrategyEngine()
signal_generation_engine = SignalGenerationEngine()

_cache_response: Optional[SignalCandidateListResponse] = None
_cache_time: Optional[datetime] = None
CACHE_TTL_SECONDS: float = 30.0


@router.get("/signal-candidates", response_model=SignalCandidateListResponse)
def get_signal_candidates():
    """
    Returns the list of generated, waiting, and rejected signal candidates
    from recent missions or Signal Generation Engine.
    """
    global _cache_response, _cache_time
    now = datetime.now(timezone.utc)

    # In-memory cache fast path
    if _cache_response and _cache_time:
        if (now - _cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return _cache_response

    # Fast path: check repository for recent stored mission candidates (LIMIT 3)
    missions = None
    try:
        all_m = mission_repository.get_all_missions()
        if all_m:
            missions = all_m[-3:]
    except Exception:
        pass
    if not missions:
        try:
            missions = mission_repository.get_recent_missions(limit=3)
        except Exception:
            missions = []

    candidates: List[SignalCandidate] = []
    if missions:
        mission_ids = [m.id for m in missions]
        if hasattr(mission_repository, "get_all_mission_artifacts_bulk"):
            try:
                bulk = mission_repository.get_all_mission_artifacts_bulk(mission_ids) or {}
                for m in reversed(missions):
                    art = bulk.get(m.id) or {}
                    candidates.extend(art.get("candidates", []))
            except Exception:
                pass
        if not candidates:
            for m in reversed(missions):
                art = mission_repository.get_mission_artifacts(m.id) or {}
                candidates.extend(art.get("candidates", []))

    if candidates:
        resp = SignalCandidateListResponse(
            candidates=candidates,
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
    except Exception as exc:
        logger.warning(f"Error generating candidates: {exc}")
        candidates = []

    response = SignalCandidateListResponse(
        candidates=candidates,
        lastUpdated=now,
    )
    _cache_response = response
    _cache_time = now
    return response


@router.get("/signal-candidates/{candidate_id}", response_model=SignalCandidate)
def get_signal_candidate(candidate_id: str):
    """
    Returns a single SignalCandidate artifact by its deterministic ID (e.g. cand-001).
    Returns 404 if no candidate with the given ID exists.
    """
    res = get_signal_candidates()
    for candidate in res.candidates:
        if candidate.id == candidate_id:
            return candidate
    raise HTTPException(status_code=404, detail=f"Signal candidate '{candidate_id}' not found.")
