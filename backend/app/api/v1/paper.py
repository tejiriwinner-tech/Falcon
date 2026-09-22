"""
Falcon V10 Phase 5G: Paper Trading API Router.

Endpoints for inspecting simulated PAPER trading activity.
Strictly read-only; separates PAPER from LIVE and legacy untagged populations.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query

from app.core.execution.execution_mode_guard import (
    ExecutionMode,
    parse_execution_mode,
)
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.schemas.trade_journal import TradeJournalListResponse

router = APIRouter(prefix="/paper", tags=["paper"])


@router.get("/trades", response_model=TradeJournalListResponse)
def get_paper_trades(
    status: Optional[str] = Query(None, description="Filter by status: PENDING, OPEN, CLOSED, EXPIRED, INVALIDATED"),
    limit: int = Query(50, ge=1, le=500),
) -> TradeJournalListResponse:
    """
    Returns strictly PAPER simulated trades.
    Historical untagged records and LIVE trades are strictly excluded.
    """
    all_trades = trade_journal_repository.list_trades()
    paper_trades = [
        t for t in all_trades
        if (getattr(t, "executionMode", None) or parse_execution_mode(t.notes)) == ExecutionMode.PAPER.value
    ]

    if status:
        status_clean = status.strip().upper()
        paper_trades = [t for t in paper_trades if (t.status or "").upper() == status_clean]

    return TradeJournalListResponse(
        trades=paper_trades[:limit],
        lastUpdated=datetime.now(timezone.utc),
    )
