"""
Falcon V10 Phase 5G: Controlled Paper-Trading Runtime.

Automated background runtime for observing market quotes and progressing
simulated PAPER trades through their lifecycle:
PENDING -> Simulated Fill -> OPEN -> Simulated SL/TP -> CLOSED / EXPIRED / INVALIDATED

Key Safety & Concurrency Invariants:
1. Purely Simulated Lifecycle:
   Market Quote -> Paper Engine -> Paper Trade State -> Paper Journal -> Analytics.
   NEVER connects to or places orders with MT5 or Exness.
2. Complete Capital Isolation:
   Paper activity NEVER consumes LIVE Guardian 3-trade slots, never reduces LIVE
   loss capacity, never alters active capital or protected profit, and never modifies
   a LIVE capital cycle.
3. Concurrency & Idempotency:
   Protected by PostgreSQL advisory lock 8882026 and reentrant thread mutex.
   Repeated execution cannot double-fill, double-close, or duplicate reservations.
4. Deterministic Simultaneous SL/TP Handling:
   Ambiguous simultaneous hits resolve fail-closed to Stop Loss (LOSS).
"""

from datetime import datetime, timedelta, timezone
import logging
import threading
from typing import Any, Dict, List, Optional

from app.core.engines.paper_trading_engine import (
    PaperTradingEngine,
    paper_trading_engine,
)
from app.core.execution.execution_mode_guard import (
    ExecutionMode,
    assert_no_broker_automation,
    is_paper_record,
    parse_execution_mode,
)
from app.core.providers import provider_manager
from app.core.repository.trade_journal_repository import (
    TradeJournalRepository,
    trade_journal_repository,
)
from app.schemas.market_quote import MarketQuote
from app.schemas.signal_candidate import SignalCandidate
from app.schemas.trade_journal import TradeJournalItem

logger = logging.getLogger("falcon.paper_runtime")


class PaperTradingRuntime:
    """
    Controlled runtime daemon for evaluating PAPER trades against market quotes.
    """

    def __init__(
        self,
        engine: Optional[PaperTradingEngine] = None,
        journal_repo: Optional[TradeJournalRepository] = None,
        validity_minutes: int = 45,
    ):
        self._engine = engine or paper_trading_engine
        self._journal_repo = journal_repo or trade_journal_repository
        self._validity_minutes = validity_minutes
        self._lock = threading.RLock()

    def reserve_paper_candidate(
        self,
        candidate: SignalCandidate,
        signal_id: int,
        session: Optional[object] = None,
    ) -> Optional[TradeJournalItem]:
        """
        Evaluate and idempotently reserve an eligible signal candidate in PAPER mode.
        """
        from app.core.config.settings import settings
        if not getattr(settings, "ENABLE_PAPER_TRADING", False):
            return None

        with self._lock:
            decision, reserved_item = self._engine.authorize_paper_candidate(
                candidate=candidate,
                signal_id=signal_id,
                session=session,
            )
            if decision.allowed and reserved_item:
                logger.info(f"Reserved paper candidate #{signal_id} as trade #{reserved_item.id}")
                return reserved_item
            return None

    def process_cycle(
        self,
        quotes: Optional[List[MarketQuote]] = None,
        as_of: Optional[datetime] = None,
        session: Optional[object] = None,
    ) -> Dict[str, Any]:
        """
        Run one complete paper trading evaluation cycle across all active paper trades.
        1. Expires stale PENDING trades past validity window.
        2. Simulates fills for PENDING trades whose entry price is crossed.
        3. Evaluates SL/TP for OPEN trades.
        4. Finalizes post-fill excursions and realized R upon closure.
        """
        from app.core.config.settings import settings
        if not getattr(settings, "ENABLE_PAPER_TRADING", False):
            return {"filled_count": 0, "closed_count": 0, "expired_count": 0}

        with self._lock:
            now = as_of or datetime.now(timezone.utc)
            all_trades = self._journal_repo.list_trades(session=session)

            # Filter strictly for active PAPER trades
            active_paper_trades = [
                t for t in all_trades
                if is_paper_record(t)
                and (t.status or "").upper() in ("PENDING", "OPEN")
                and t.closeDate is None
            ]

            filled_count = 0
            closed_count = 0
            expired_count = 0
            evaluated_count = 0

            # 1. Process PENDING expiration
            for trade in active_paper_trades:
                if (trade.status or "").upper() == "PENDING":
                    t_date = trade.tradeDate if trade.tradeDate.tzinfo else trade.tradeDate.replace(tzinfo=timezone.utc)
                    if (now - t_date) > timedelta(minutes=self._validity_minutes):
                        expired = self._engine.expire_paper_trade(
                            trade_id=trade.id,
                            reason=f"Paper setup expired after {self._validity_minutes}m without fill",
                            expiration_time=now,
                            session=session,
                        )
                        if expired:
                            expired_count += 1
                            logger.info(f"Expired stale paper trade #{trade.id} (signal #{trade.signalId})")

            # 2. Process quotes for remaining active trades
            # If explicit quotes provided, use them; otherwise fetch from provider_manager
            symbols = list(set((t.symbol or "").upper() for t in active_paper_trades if t.status in ("PENDING", "OPEN")))

            quote_map: Dict[str, MarketQuote] = {}
            if quotes:
                for q in quotes:
                    quote_map[(q.symbol or "").upper()] = q
            else:
                for sym in symbols:
                    resp = provider_manager.get_market_quote(sym)
                    if resp and resp.quote:
                        quote_map[sym] = resp.quote

            # Feed quotes into paper engine
            for sym, quote in quote_map.items():
                resolved = self._engine.process_quote(quote, session=session)
                for res_item in resolved:
                    evaluated_count += 1
                    if res_item.status == "OPEN":
                        filled_count += 1
                    elif res_item.status == "CLOSED":
                        closed_count += 1

            return {
                "active_checked": len(active_paper_trades),
                "filled_count": filled_count,
                "closed_count": closed_count,
                "expired_count": expired_count,
                "evaluated_count": evaluated_count,
                "cycle_timestamp": now,
            }


paper_trading_runtime = PaperTradingRuntime()
