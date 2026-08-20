from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, status

from app.core.repository.trade_journal_repository import trade_journal_repository
from app.schemas.trade_journal import (
    TradeJournalCreate,
    TradeJournalItem,
    TradeJournalListResponse,
    TradeJournalUpdate,
)

router = APIRouter()


@router.get("/trade-journal", response_model=TradeJournalListResponse)
def get_trade_journal():
    """Returns every stored journal entry, newest trade first."""
    return TradeJournalListResponse(
        trades=trade_journal_repository.list_trades(),
        lastUpdated=datetime.now(timezone.utc),
    )


@router.post("/trade-journal", response_model=TradeJournalItem, status_code=201)
def create_trade_journal(trade: TradeJournalCreate):
    """Stores a new journal entry and returns it with its assigned id."""
    return trade_journal_repository.create_trade(trade)


@router.get("/trade-journal/{trade_id}", response_model=TradeJournalItem)
def get_trade_journal_entry(trade_id: int):
    trade = trade_journal_repository.get_trade(trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail=f"Trade '{trade_id}' not found")
    return trade


@router.patch("/trade-journal/{trade_id}", response_model=TradeJournalItem)
def update_trade_journal_entry(trade_id: int, update: TradeJournalUpdate):
    """Applies a partial update, typically to close an open trade."""
    trade = trade_journal_repository.update_trade(trade_id, update)
    if trade is None:
        raise HTTPException(status_code=404, detail=f"Trade '{trade_id}' not found")
    return trade


@router.delete("/trade-journal/{trade_id}", status_code=204)
def delete_trade_journal_entry(trade_id: int):
    if not trade_journal_repository.delete_trade(trade_id):
        raise HTTPException(status_code=404, detail=f"Trade '{trade_id}' not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
