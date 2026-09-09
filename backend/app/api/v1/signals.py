from typing import List
from fastapi import APIRouter, Query

from app.core.services.signal_service import signal_service
from app.core.services.signal_outcome_resolver import signal_outcome_resolver
from app.schemas.signal import SignalListResponse
from app.schemas.signal_outcome import SignalOutcomeItem, SignalResolutionSummary

router = APIRouter()


@router.get("/signals", response_model=SignalListResponse, tags=["signals"])
async def get_signals(
    missionLimit: int = Query(
        default=5, ge=1, le=50, description="How many recent missions to project"
    )
):
    """
    Signals projected from the candidates and decisions of recent stored missions.
    """
    return signal_service.build_signals(mission_limit=missionLimit)


@router.post("/signals/resolve", response_model=SignalResolutionSummary, tags=["signals"])
def resolve_signals(
    forceSimulate: bool = Query(
        default=False,
        description="When true, force simulation resolution of pending candidates for verification"
    )
):
    """
    Scan active signals and past candidates against live market quotes,
    detect Stop Loss and Take Profit boundary breaches, run automated root-cause
    diagnostics on failures, and log closed trade records into Trade Journal.
    """
    return signal_outcome_resolver.resolve_signals(force_simulate=forceSimulate)


@router.get("/signals/outcomes", response_model=List[SignalOutcomeItem], tags=["signals"])
def get_signal_outcomes(
    limit: int = Query(
        default=50, ge=1, le=200, description="Maximum number of resolved outcomes to return"
    )
):
    """
    Return all auto-resolved signal outcomes with their post-mortem diagnostics and lessons learned.
    """
    return signal_outcome_resolver.get_outcomes(limit=limit)

