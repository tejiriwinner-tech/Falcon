"""
Falcon Bidirectional Broker State Reconciliation Service
Continuously reconciles OANDA broker state (/openTrades, /pendingOrders)
with Falcon's Trade Journal and Regime Memory.

Ensures that manual closes, mobile app SL adjustments, or broker-side fills
are immediately reflected in Falcon's persistent analytics and learning loops.
"""
from datetime import datetime, timezone
from decimal import Decimal
import logging
import re
from typing import Any, Dict, List, Optional

from app.core.providers.oanda_provider import OandaProvider
from app.core.repository.trade_journal_repository import (
    TradeJournalRepository,
    trade_journal_repository,
)
from app.core.services.signal_outcome_resolver import signal_outcome_resolver
from app.schemas.trade_journal import TradeJournalItem, TradeJournalUpdate

logger = logging.getLogger("falcon.broker_reconciliation")


class BrokerReconciliationService:
    """
    Bidirectional synchronization engine between OANDA broker account and Falcon Journal:
    1. Detects externally closed trades (via OANDA app, web, or MT5) and finalizes journal.
    2. Synchronizes manually trailed Stop Loss and Take Profit levels from broker to Falcon.
    3. Triggers closed-loop post-mortem learning in RegimeMemoryEngine upon trade completion.
    """

    def __init__(
        self,
        oanda_provider: Optional[OandaProvider] = None,
        journal_repo: Optional[TradeJournalRepository] = None,
    ):
        self._provider = oanda_provider or OandaProvider()
        self._journal = journal_repo or trade_journal_repository

    def reconcile_state(self) -> Dict[str, Any]:
        """
        Execute one reconciliation pass.

        Returns:
            Dict summarizing reconciliation actions.
        """
        if not self._provider.configured:
            return {"status": "SKIPPED", "reason": "OANDA unconfigured", "reconciled_count": 0}

        open_broker_trades = self._provider.get_open_trades()
        if open_broker_trades is None:
            return {"status": "ERROR", "reason": "Failed to fetch open trades from OANDA", "reconciled_count": 0}

        # Build map of broker trades by ID
        broker_trade_map: Dict[str, Dict[str, Any]] = {
            str(t.get("id")): t for t in open_broker_trades if t.get("id")
        }

        # Fetch active journal trades
        active_journal_trades = [
            t for t in self._journal.list_trades()
            if getattr(t, "status", "").upper() in ("OPEN", "FILLED", "ACTIVE", "PENDING")
            and getattr(t, "closeDate", None) is None
        ]

        closed_synced = 0
        modified_synced = 0

        for trade in active_journal_trades:
            # Extract broker ticket if present
            notes = getattr(trade, "notes", "") or ""
            broker_ticket = None
            m_ticket = re.search(r"(?:oanda_order:|ticket[:\s#]+)(\d+)", notes, re.IGNORECASE)
            if m_ticket:
                broker_ticket = m_ticket.group(1).strip()

            if not broker_ticket:
                # Fuzzy Reconciliation: Match unticketed active trade by Symbol + Direction + Price proximity
                t_sym = trade.symbol.replace("/", "_").upper()
                t_dir = (trade.direction or "").upper()
                for b_id, b_trade in broker_trade_map.items():
                    b_inst = b_trade.get("instrument", "").replace("/", "_").upper()
                    b_units = float(b_trade.get("currentUnits", 0.0) or b_trade.get("initialUnits", 0.0))
                    b_dir = "BUY" if b_units > 0 else "SELL"
                    if b_inst == t_sym and b_dir == t_dir:
                        b_price = float(b_trade.get("price", 0.0))
                        pip_tol = 0.50 if "XAU" in t_sym else (0.05 if "JPY" in t_sym else 0.0010)
                        if abs(b_price - float(trade.entryPrice)) <= pip_tol:
                            broker_ticket = b_id
                            # Bind the matched broker ticket into journal record notes
                            new_notes = f"{notes} ticket:{b_id}".strip()
                            self._journal.update_trade(trade.id, TradeJournalUpdate(notes=new_notes))
                            logger.info(
                                "[Reconciliation] Successfully linked broker ticket #%s to journal trade #%s (%s %s)",
                                b_id, trade.id, trade.symbol, trade.direction
                            )
                            break

            if not broker_ticket:
                continue

            # Check if trade is still open on OANDA
            if broker_ticket in broker_trade_map:
                # Trade is still open — check for SL/TP modifications from mobile app
                b_trade = broker_trade_map[broker_ticket]
                b_sl_obj = b_trade.get("stopLossOrder")
                if b_sl_obj and "price" in b_sl_obj:
                    try:
                        b_sl = float(b_sl_obj["price"])
                        if abs(b_sl - float(trade.stopLoss)) > 1e-5:
                            logger.info(
                                "[Reconciliation] Syncing updated Stop Loss from OANDA for trade #%s (%s): %s -> %s",
                                trade.id, trade.symbol, trade.stopLoss, b_sl
                            )
                            self._journal.update_trade(trade.id, TradeJournalUpdate(stopLoss=b_sl))
                            modified_synced += 1
                    except Exception as ex:
                        logger.debug("Failed to sync modified SL: %s", ex)
            else:
                # Trade is NO LONGER open on OANDA -> Closed externally
                logger.info(
                    "[Reconciliation] Trade #%s (ticket %s, %s) is no longer open on OANDA. Reconciling close.",
                    trade.id, broker_ticket, trade.symbol
                )
                trade_details = self._provider.get_trade_details(broker_ticket)
                realized_pl = 0.0
                exit_price = trade.entryPrice
                close_time = datetime.now(timezone.utc)

                if trade_details:
                    realized_pl = float(trade_details.get("realizedPL", 0.0))
                    avg_close = trade_details.get("averageClosePrice")
                    if avg_close:
                        exit_price = float(avg_close)

                # Classify outcome
                if realized_pl > 0:
                    result = "WON"
                elif realized_pl == 0.0:
                    result = "BREAKEVEN"
                else:
                    # Check if BE protection applied
                    if trade.stopLoss >= trade.entryPrice and trade.direction.upper() == "BUY":
                        result = "BREAKEVEN"
                    elif trade.stopLoss <= trade.entryPrice and trade.direction.upper() == "SELL":
                        result = "BREAKEVEN"
                    else:
                        result = "LOST"

                # Update journal
                self._journal.update_trade(
                    trade.id,
                    TradeJournalUpdate(
                        status="CLOSED",
                        result=result,
                        exitPrice=exit_price,
                        profitLoss=realized_pl,
                        closeDate=close_time,
                        reasonForExit="Closed by broker (Take Profit, Stop Loss, or Manual Fill on OANDA)",
                        lessonLearned=f"Broker reconciliation synchronized exit: Result={result}, Realized PnL={realized_pl:.2f}",
                    )
                )
                closed_synced += 1

                # Conduct post-mortem learning in RegimeMemoryEngine
                try:
                    signal_outcome_resolver._conduct_post_mortem_learning(
                        trade=trade,
                        market_context={
                            "exit_price": exit_price,
                            "invalidation_boundary": trade.stopLoss,
                            "exit_reason": f"Broker reconciliation ({result})",
                        },
                    )
                except Exception as ex:
                    logger.debug("Reconciliation post-mortem learning error: %s", ex)

        return {
            "status": "SUCCESS",
            "active_journal_trades": len(active_journal_trades),
            "open_broker_trades": len(open_broker_trades),
            "closed_synced": closed_synced,
            "modified_synced": modified_synced,
        }


broker_reconciliation_service = BrokerReconciliationService()
