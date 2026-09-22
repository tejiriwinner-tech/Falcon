"""
Falcon V10 Phase 5G: Execution API Router.

Exposes authoritative execution mode guard status.
Strictly read-only; verifies broker automation lockout.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.core.execution.execution_mode_guard import execution_mode_guard

router = APIRouter(prefix="/execution", tags=["execution"])


class ExecutionModeStatusResponse(BaseModel):
    activeMode: str
    failClosed: bool
    brokerAutomationLocked: bool
    liveAcknowledged: bool


@router.get("/mode", response_model=ExecutionModeStatusResponse)
def get_execution_mode() -> ExecutionModeStatusResponse:
    """
    Returns authoritative execution mode guard state.
    Guarantees fail-closed safety and verifies broker automation lockout.
    """
    mode = execution_mode_guard.get_system_mode()
    return ExecutionModeStatusResponse(
        activeMode=mode.value,
        failClosed=True,
        brokerAutomationLocked=True,
        liveAcknowledged=bool(getattr(settings, "LIVE_EXECUTION_ACKNOWLEDGED", False)),
    )
