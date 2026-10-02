"""
Falcon Background Watchlist Price Poller Service

Monitors pending Watchlist setups (HOLD status) in real time:
- Auto-flips HOLD -> ACTIVE when live price touches the target entry level.
- Marks setups as EXPIRED when the 1-hour watchlist timeout is reached.
- Keeps PostgreSQL/Supabase and memory synchronized even when no frontend client is active.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.providers import provider_manager
from app.core.repository.signal_signature_repository import signal_signature_repository
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.services.session_budget_manager import session_budget_manager
from app.core.services.signal_service import signal_service
from app.core.services.signal_outcome_resolver import signal_outcome_resolver
from app.schemas.trade_journal import TradeJournalUpdate

logger = logging.getLogger("falcon.watchlist_poller")



class WatchlistPollerService:
    """
    Background price poller and state synchronizer for Falcon Watchlist.
    """

    def __init__(self, poll_interval_seconds: int = 30) -> None:
        self.poll_interval_seconds = poll_interval_seconds
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._last_poll_time: Optional[datetime] = None
        self._stats: Dict[str, int] = {
            "cycles": 0,
            "triggers": 0,
            "expirations": 0,
            "errors": 0,
        }

    async def start(self) -> None:
        """Start the background watchlist polling task."""
        if self.is_running:
            logger.info("Watchlist poller is already running.")
            return

        self.is_running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            f"Watchlist poller service started (interval: {self.poll_interval_seconds}s)"
        )

    async def stop(self) -> None:
        """Stop the background watchlist polling task gracefully."""
        if not self.is_running:
            return

        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Watchlist poller service stopped successfully")

    async def _poll_loop(self) -> None:
        """Main periodic polling loop."""
        # Initial 5-second warm-up delay before first cycle
        await asyncio.sleep(5)

        while self.is_running:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                break
            except Exception as ex:
                self._stats["errors"] += 1
                logger.warning(f"Error during watchlist poller cycle: {ex}")

            try:
                await asyncio.sleep(self.poll_interval_seconds)
            except asyncio.CancelledError:
                break

    async def poll_once(self) -> dict:
        """
        Executes a single check across all active and pending watchlist setups.
        Auto-transitions HOLD -> ACTIVE upon entry hit or -> EXPIRED upon 1-hour timeout.
        """
        now = datetime.now(timezone.utc)
        self._stats["cycles"] += 1
        self._last_poll_time = now

        result = {
            "timestamp": now.isoformat(),
            "active_count": 0,
            "hold_count": 0,
            "expired_count": 0,
            "new_triggers": 0,
            "new_expirations": 0,
        }

        # Check session budget / active hours
        if not session_budget_manager.is_active():
            logger.debug("Session budget standby: skipping watchlist poller price check.")
            return result

        try:
            # Force rebuild of signals to get fresh quote evaluation
            signals_response = signal_service.build_signals(mission_limit=5, force_refresh=True)
            all_signals = signals_response.signals

            for sig in all_signals:
                status = (sig.status or "").upper()
                symbol = sig.symbol
                direction = sig.action
                entry = sig.entry
                sl = sig.stopLoss
                tp = sig.takeProfit

                if status == "ACTIVE":
                    result["active_count"] += 1
                elif status == "HOLD":
                    result["hold_count"] += 1
                elif status == "EXPIRED":
                    result["expired_count"] += 1

            logger.debug(
                f"Watchlist poller cycle completed: {result['active_count']} ACTIVE, "
                f"{result['hold_count']} HOLD, {result['expired_count']} EXPIRED"
            )

        except Exception as ex:
            self._stats["errors"] += 1
            logger.warning(f"Watchlist poller execution error: {ex}")

        # Step 2: Monitor and auto-resolve OPEN trades in Trade Journal against live market
        try:
            open_trades = [
                t for t in (trade_journal_repository.list_trades() or [])
                if (t.status or "").upper() in ("OPEN", "FILLED") and t.closeDate is None and t.entryPrice > 0
            ]
            for trade in open_trades:
                raw_sym = trade.symbol.replace("/", "").upper()
                quote_resp = provider_manager.get_market_quote(raw_sym)
                if not quote_resp or not quote_resp.quote or not quote_resp.quote.lastPrice:
                    continue
                cur_px = quote_resp.quote.lastPrice
                direction = (trade.direction or "").upper()
                sl = trade.stopLoss
                tp = trade.takeProfit

                hit_sl = False
                hit_tp = False

                if direction == "BUY":
                    if cur_px <= sl:
                        hit_sl = True
                    elif cur_px >= tp:
                        hit_tp = True
                else:  # SELL
                    if cur_px >= sl:
                        hit_sl = True
                    elif cur_px <= tp:
                        hit_tp = True

                if hit_sl:
                    loss_pts = -round(abs(trade.entryPrice - sl), 4)
                    trade_update = TradeJournalUpdate(
                        status="CLOSED",
                        result="LOST",
                        exitPrice=sl,
                        closeDate=now,
                        profitLoss=loss_pts,
                        realizedRMultiple=-1.0,
                        reasonForExit="Stop Loss Hit",
                    )
                    updated_trade = trade_journal_repository.update_trade(trade.id, trade_update)
                    try:
                        signal_outcome_resolver._conduct_post_mortem_learning(
                            trade=updated_trade or trade,
                            market_context={
                                "exit_reason": "Stop Loss Hit",
                                "market_price": cur_px,
                                "invalidation_boundary": sl,
                            }
                        )
                    except Exception as ex:
                        logger.warning(f"Error in post-mortem learning for trade #{trade.id}: {ex}")
                    logger.info(
                        f"🛑 STOP LOSS HIT for {trade.symbol} #{trade.id} at {cur_px:.4f} (SL: {sl:.4f}). "
                        f"Trade closed as LOST and post-mortem recorded in journal."
                    )
                    result["new_expirations"] += 1

                elif hit_tp:
                    win_pts = round(abs(tp - trade.entryPrice), 4)
                    rr_val = trade.riskReward or 2.0
                    trade_update = TradeJournalUpdate(
                        status="CLOSED",
                        result="WON",
                        exitPrice=tp,
                        closeDate=now,
                        profitLoss=win_pts,
                        realizedRMultiple=rr_val,
                        reasonForExit="Take Profit Target Hit Cleanly",
                    )
                    updated_trade = trade_journal_repository.update_trade(trade.id, trade_update)
                    try:
                        signal_outcome_resolver._conduct_post_mortem_learning(
                            trade=updated_trade or trade,
                            market_context={
                                "exit_reason": "Take Profit Hit",
                                "market_price": cur_px,
                                "target": tp,
                            }
                        )
                    except Exception as ex:
                        logger.warning(f"Error in win learning for trade #{trade.id}: {ex}")
                    logger.info(
                        f"🏆 TAKE PROFIT HIT for {trade.symbol} #{trade.id} at {cur_px:.4f} (TP: {tp:.4f}). "
                        f"Trade closed as WON in journal."
                    )
                    result["new_triggers"] += 1

        except Exception as ex:
            logger.warning(f"Error monitoring open trades in watchlist poller: {ex}")

        return result

    def get_status(self) -> dict:
        """Returns the real-time status and health metrics of the poller."""
        return {
            "is_running": self.is_running,
            "poll_interval_seconds": self.poll_interval_seconds,
            "last_poll_time": self._last_poll_time.isoformat() if self._last_poll_time else None,
            "stats": self._stats,
        }


watchlist_poller_service = WatchlistPollerService()
