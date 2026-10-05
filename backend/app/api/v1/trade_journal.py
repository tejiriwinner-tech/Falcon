from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, status

from decimal import Decimal

from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.services.signal_authorization_service import signal_authorization_service
from app.schemas.capital_guardian import ProposedTradeInput
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
    status_clean = (trade.status or "").strip().upper()
    if status_clean in ("PENDING", "OPEN", "FILLED") and trade.closeDate is None:
        proposal = ProposedTradeInput(
            symbol=trade.symbol.upper(),
            direction=trade.direction.upper(),
            entryPrice=Decimal(str(trade.entryPrice)),
            stopLoss=Decimal(str(trade.stopLoss)),
            takeProfit=Decimal(str(trade.takeProfit)),
            lotSize=Decimal("0.01"),
            riskReward=Decimal(str(round(trade.riskReward, 2))) if trade.riskReward else None,
        )
        decision, res_item = signal_authorization_service.authorize_and_reserve(
            proposal=proposal,
            signal_id=trade.signalId,
            strategy_id=trade.strategyId,
            timeframe=trade.timeframe,
            market_session=trade.marketSession,
            notes=trade.notes,
            confidence=trade.confidence,
            strategy_version=trade.strategyVersion,
            adaptive_rule_version=trade.adaptiveRuleVersion,
            adaptive_stop_multiplier=trade.adaptiveStopMultiplier,
            spread_at_entry=trade.spreadAtEntry,
            atr_at_entry=trade.atrAtEntry,
        )
        if not decision.allowed or res_item is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Capital Guardian rejected trade: {decision.reason}",
            )
        return res_item

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
    existing = trade_journal_repository.get_trade(trade_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Trade '{trade_id}' not found")

    # If closing a trade and realizedRMultiple is not explicitly provided, calculate it
    status_str = (update.status or "").strip().upper()
    if (status_str == "CLOSED" or update.closeDate is not None):
        if update.realizedRMultiple is None:
            res = (update.result or existing.result or "").strip().upper()
            if res in ("WIN", "LOSS", "BREAKEVEN", "BE"):
                init_risk = getattr(existing, "initialMonetaryRisk", None)
                if init_risk is not None and float(init_risk) > 0:
                    pnl = update.profitLoss if update.profitLoss is not None else existing.profitLoss
                    if res == "WIN":
                        update.realizedRMultiple = round(float(pnl) / float(init_risk), 2)
                    elif res == "LOSS":
                        update.realizedRMultiple = -round(abs(float(pnl)) / float(init_risk), 2)
                    elif res in ("BREAKEVEN", "BE"):
                        update.realizedRMultiple = 0.0

        # Phase 5C: Excursion finalization on close if not explicitly provided
        if update.mfeR is None and update.maeR is None and existing.fillPrice is not None:
            from app.core.analytics.execution_quality_service import execution_quality_service
            exit_p = update.exitPrice if update.exitPrice is not None else existing.exitPrice
            final_peak, final_trough, fin_mfe_r, fin_mae_r = execution_quality_service.finalize_closed_trade_excursion(
                trade=existing,
                exit_price=exit_p,
                close_time=update.closeDate or datetime.now(timezone.utc),
            )
            if update.peakPrice is None and final_peak is not None:
                update.peakPrice = final_peak
            if update.troughPrice is None and final_trough is not None:
                update.troughPrice = final_trough
            if update.mfeR is None and fin_mfe_r is not None:
                update.mfeR = fin_mfe_r
            if update.maeR is None and fin_mae_r is not None:
                update.maeR = fin_mae_r

    trade = trade_journal_repository.update_trade(trade_id, update)
    return trade


@router.delete("/trade-journal/history", status_code=200)
def clear_trade_history():
    """Delete finished trades (WIN / LOSS / BREAKEVEN / EXPIRED ...).

    Active trades (OPEN / PENDING / FILLED) are kept so they still resolve and
    re-appear in history when they hit TP, SL or breakeven.
    """
    deleted = trade_journal_repository.clear_history()
    try:
        from app.core.services.signal_outcome_resolver import signal_outcome_resolver
        with signal_outcome_resolver._lock:
            signal_outcome_resolver._resolved_cache.clear()
    except Exception:
        pass
    return {
        "status": "success",
        "deleted": deleted,
        "message": f"Cleared {deleted} finished trade(s). Active trades were kept.",
    }


@router.delete("/trade-journal/{trade_id}", status_code=204)
def delete_trade_journal_entry(trade_id: int):
    if not trade_journal_repository.delete_trade(trade_id):
        raise HTTPException(status_code=404, detail=f"Trade '{trade_id}' not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/trade-journal", status_code=200)
def clear_all_trade_journal():
    """Purge all trade journal records and reset signal signature deduplication memory."""
    trade_journal_repository.clear()
    from app.core.repository.signal_signature_repository import signal_signature_repository
    signal_signature_repository.clear()
    return {"status": "success", "message": "All trade journal and history records cleared successfully"}

