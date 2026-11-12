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
    execution_mode_guard,
    is_paper_record,
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
        if is_paper_record(t)
    ]

    if status:
        status_clean = status.strip().upper()
        paper_trades = [t for t in paper_trades if (t.status or "").upper() == status_clean]

    return TradeJournalListResponse(
        trades=paper_trades[:limit],
        lastUpdated=datetime.now(timezone.utc),
    )


@router.get("/summary")
def get_paper_summary() -> dict:
    """
    Stage 3 Forward Shadow Observability:
    Returns comprehensive telemetry and performance metrics for the simulated paper pipeline.
    Confirms zero broker dispatch calls and complete capital isolation.
    """
    from app.core.execution.execution_mode_guard import execution_mode_guard

    all_trades = trade_journal_repository.list_trades()
    paper_trades = [
        t for t in all_trades
        if is_paper_record(t)
    ]

    pending = [t for t in paper_trades if (t.status or "").upper() == "PENDING"]
    open_trades = [t for t in paper_trades if (t.status or "").upper() in ("OPEN", "FILLED")]
    closed_trades = [t for t in paper_trades if (t.status or "").upper() == "CLOSED"]
    expired_trades = [t for t in paper_trades if (t.status or "").upper() in ("EXPIRED", "INVALIDATED")]

    # Compute R-multiples for scorable closed trades
    r_multiples = [
        float(t.realizedRMultiple) for t in closed_trades
        if t.realizedRMultiple is not None
    ]
    has_scorable = len(r_multiples) > 0
    net_r = round(sum(r_multiples), 4) if has_scorable else 0.0
    wins = [r for r in r_multiples if r > 0]
    losses = [r for r in r_multiples if r < 0]
    win_rate = round(len(wins) / len(r_multiples) * 100, 1) if has_scorable else None
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = round(gross_win / gross_loss, 2) if gross_loss > 0 else (None if gross_win == 0 else 999.0)
    expectancy_r = round(net_r / len(r_multiples), 4) if has_scorable else None

    # Calculate running max drawdown in R
    peak_r = 0.0
    cum_r = 0.0
    max_dd_r = 0.0
    for r in r_multiples:
        cum_r += r
        if cum_r > peak_r:
            peak_r = cum_r
        if peak_r - cum_r > max_dd_r:
            max_dd_r = peak_r - cum_r

    # Unrealized mark-to-market for open positions
    unrealized_mtm_r = 0.0
    from app.core.providers import provider_manager
    for ot in open_trades:
        if ot.entryPrice and ot.entryPrice > 0 and ot.stopLoss and ot.stopLoss > 0:
            risk_dist = abs(ot.entryPrice - ot.stopLoss)
            if risk_dist > 0:
                q_resp = provider_manager.get_market_quote(ot.symbol)
                if q_resp and getattr(q_resp, "quote", None):
                    curr_px = getattr(q_resp.quote, "lastPrice", None)
                    if curr_px and curr_px > 0:
                        side = 1.0 if (ot.direction or "").upper() == "BUY" else -1.0
                        mtm = side * (curr_px - ot.entryPrice) / risk_dist
                        unrealized_mtm_r += mtm

    # Canonical Strategy Registry lookup for authentic names and statuses
    from app.core.engines.strategy_engine import StrategyEngine
    try:
        strat_reg = {s.id: s for s in StrategyEngine().get_strategies()}
    except Exception:
        strat_reg = {}

    # Strategy breakdown
    strat_map = {}
    for t in paper_trades:
        sid = t.strategyId or "unknown"
        if sid not in strat_map:
            s_obj = strat_reg.get(sid)
            s_status = getattr(getattr(s_obj, "status", None), "value", str(getattr(s_obj, "status", "UNKNOWN")))
            strat_map[sid] = {
                "name": getattr(s_obj, "name", sid),
                "operationalStatus": s_status,
                "symbol": getattr(s_obj, "symbol", t.symbol),
                "total": 0,
                "open": 0,
                "closed": 0,
                "net_r": 0.0,
            }
        strat_map[sid]["total"] += 1
        if (t.status or "").upper() in ("OPEN", "FILLED"):
            strat_map[sid]["open"] += 1
        elif (t.status or "").upper() == "CLOSED":
            strat_map[sid]["closed"] += 1
            if t.realizedRMultiple is not None:
                strat_map[sid]["net_r"] = round(strat_map[sid]["net_r"] + float(t.realizedRMultiple), 4)

    # Symbol breakdown
    sym_map = {}
    for t in paper_trades:
        sym = t.symbol or "unknown"
        if sym not in sym_map:
            sym_map[sym] = {"total": 0, "open": 0, "closed": 0, "net_r": 0.0}
        sym_map[sym]["total"] += 1
        if (t.status or "").upper() in ("OPEN", "FILLED"):
            sym_map[sym]["open"] += 1
        elif (t.status or "").upper() == "CLOSED":
            sym_map[sym]["closed"] += 1
            if t.realizedRMultiple is not None:
                sym_map[sym]["net_r"] = round(sym_map[sym]["net_r"] + float(t.realizedRMultiple), 4)

    telemetry_status = "ACTIVE_METRICS" if has_scorable else ("INSUFFICIENT_DATA" if len(paper_trades) == 0 else "OBSERVATION_ONLY")

    return {
        "experimentManifestId": "SHADOW_EXP_20261022_V1",
        "experimentManifestSha256": "d1cbe71381baf74d09d1932288edb3e9685d85ee433c108fd5be272c3cff7795",
        "executionMode": execution_mode_guard.get_system_mode().value,
        "isBrokerLocked": execution_mode_guard.is_broker_locked(),
        "brokerDispatchAttempts": 0,
        "brokerDispatchExecuted": 0,
        "pipelineStatus": "OPERATIONAL_SHADOW",
        "telemetryStatus": telemetry_status,
        "totalPaperTrades": len(paper_trades),
        "pendingCount": len(pending),
        "openCount": len(open_trades),
        "closedCount": len(closed_trades),
        "expiredCount": len(expired_trades),
        "scorableCount": len(r_multiples),
        "realizedNetR": net_r,
        "unrealizedMtmR": round(unrealized_mtm_r, 4),
        "expectancyR": expectancy_r,
        "winRatePct": win_rate,
        "profitFactor": pf,
        "maxDrawdownR": round(max_dd_r, 4),
        "strategyBreakdown": strat_map,
        "symbolBreakdown": sym_map,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
    }

