from fastapi import APIRouter, Query

from app.core.services.signal_service import signal_service
from app.schemas.signal import SignalListResponse

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
