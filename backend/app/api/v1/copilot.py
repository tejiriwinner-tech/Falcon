"""
Falcon AI Co-Pilot & Scheduled Briefing API Router (Pillar 3)
Exposes REST endpoints for conversational query reasoning and intelligence briefings.
"""

from fastapi import APIRouter
from app.schemas.copilot import (
    CopilotQueryRequest,
    CopilotQueryResponse,
    IntelligenceBriefing,
)
from app.core.services.copilot_service import copilot_service
from app.core.services.briefing_service import briefing_service

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/query", response_model=CopilotQueryResponse)
def query_copilot(request: CopilotQueryRequest) -> CopilotQueryResponse:
    """
    Submits a natural language query to the Falcon AI Co-Pilot.
    
    Supports:
    - Trade Rationale ("Why did you trigger this Gold buy?", "Why SELL GBP/USD?")
    - Streak & Risk ("What is our current streak and recovery status?", "How much can we lose?")
    - Forensic Diagnostics ("What did you learn from the last loss?")
    - Strategy Architecture ("What strategies are active?", "What is active capital?")
    """
    return copilot_service.handle_query(request)


@router.get("/briefings/london-open", response_model=IntelligenceBriefing)
def get_london_open_briefing() -> IntelligenceBriefing:
    """
    Generates and returns the London Open (07:00 UTC) scheduled intelligence briefing:
    Asian session ranges, institutional Order Blocks & FVGs, macro calendar events, and top 3 watchpoints.
    """
    return briefing_service.generate_london_open_briefing()


@router.get("/briefings/daily-review", response_model=IntelligenceBriefing)
def get_daily_review_briefing() -> IntelligenceBriefing:
    """
    Generates and returns the Daily Performance Review (20:00 UTC) scheduled intelligence briefing:
    Session PnL, trades executed, streak and recovery status, forensic root cause, and parameter adjustments.
    """
    return briefing_service.generate_daily_review_briefing()


@router.get("/briefings/latest", response_model=IntelligenceBriefing)
def get_latest_briefing() -> IntelligenceBriefing:
    """
    Retrieves the most recent scheduled briefing, or generates a London Open briefing if none exists.
    """
    return briefing_service.get_latest_briefing()


@router.post("/briefings/dispatch-telegram")
async def dispatch_briefing_to_telegram(
    briefing_type: str = "latest",
    custom_chat_id: str = None,
):
    return {"status": "disabled", "delivered": False, "message": "Telegram is permanently disconnected from Falcon."}

