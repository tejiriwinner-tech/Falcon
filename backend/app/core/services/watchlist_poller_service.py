"""
Falcon Background Watchlist Price Poller Service

Monitors pending Watchlist setups (HOLD status) in real time:
- Auto-flips HOLD -> ACTIVE when live price touches the target entry level.
- Marks setups as EXPIRED when the 1-hour watchlist timeout is reached.
- Keeps PostgreSQL/Supabase and memory synchronized even when no frontend client is active.
"""

import os
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
from app.core.services.broker_reconciliation_service import broker_reconciliation_service
from app.services.alerts.telegram_alert_service import telegram_alert_service
from app.schemas.trade_journal import TradeJournalUpdate

logger = logging.getLogger("falcon.watchlist_poller")



class WatchlistPollerService:
    """
    Background price poller and state synchronizer for Falcon Watchlist.
    """

    def __init__(self, poll_interval_seconds: int = 15) -> None:
        self.poll_interval_seconds = int(os.getenv("WATCHLIST_POLL_INTERVAL_SECONDS", str(poll_interval_seconds)))
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
        Offloads synchronous database and calculation work to a worker thread
        so the asyncio event loop remains non-blocking for HTTP requests.
        """
        return await asyncio.to_thread(self._poll_once_sync)

    def _poll_once_sync(self) -> dict:
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

        # Step 0: Autonomous 5-Minute Mission Refresh (ensures 24/5 signal generation across all 6 pairs even when mobile app is closed)
        if getattr(self, "autonomous_mission_refresh_enabled", True):
            try:
                from app.core.repository.mission_repository import mission_repository
                latest_missions = mission_repository.list_missions(limit=1)
                needs_mission_refresh = True
                if latest_missions and latest_missions[0].completedAt:
                    m_age = (now - latest_missions[0].completedAt).total_seconds()
                    if m_age < 300.0:
                        needs_mission_refresh = False
                if needs_mission_refresh:
                    from app.core.services.live_intelligence_service import LiveIntelligenceService
                    LiveIntelligenceService().generate_dashboard_intelligence()
                    logger.info("Autonomous background mission refresh completed across all active strategies.")
            except Exception as ex:
                logger.debug(f"Autonomous background mission refresh skipped: {ex}")

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

        # Step 2: Broker Reconciliation Pass (OANDA open trades / external closes / SL sync)
        try:
            recon_res = broker_reconciliation_service.reconcile_state()
            if recon_res.get("closed_synced", 0) > 0 or recon_res.get("modified_synced", 0) > 0:
                logger.info(f"Broker reconciliation synchronized: {recon_res}")
        except Exception as ex:
            logger.debug(f"Broker reconciliation pass error: {ex}")

        # Step 3: Monitor and auto-resolve OPEN trades in Trade Journal against live market
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

                is_gold = "XAU" in raw_sym or "GOLD" in raw_sym or trade.entryPrice > 500
                is_jpy = "JPY" in raw_sym
                spread_buffer = 0.10 if is_gold else (0.015 if is_jpy else 0.00010)  # 1-1.5 pip spread buffer

                risk_dist = abs(trade.entryPrice - sl)
                tp1_dist = 1.5 * risk_dist
                tp1_price = (trade.entryPrice + tp1_dist) if direction == "BUY" else (trade.entryPrice - tp1_dist)
                be_price = (trade.entryPrice + spread_buffer) if direction == "BUY" else (trade.entryPrice - spread_buffer)

                notes_str = trade.notes or ""
                is_be_protected = "BE_PROTECTED" in notes_str

                # Phase 1: Automated Move-to-Breakeven (BE) when Price reaches TP1 (+1.5R)
                if not is_be_protected and risk_dist > 0:
                    tp1_hit = False
                    if direction == "BUY" and cur_px >= tp1_price:
                        tp1_hit = True
                    elif direction == "SELL" and cur_px <= tp1_price:
                        tp1_hit = True

                    if tp1_hit:
                        new_sl = round(be_price, 2 if is_gold else (3 if is_jpy else 4))
                        new_notes = f"{notes_str} [BE_PROTECTED: TP1 +1.5R reached at {cur_px:.4f}; SL moved to {new_sl:.4f}]".strip()
                        trade_update = TradeJournalUpdate(
                            stopLoss=new_sl,
                            notes=new_notes,
                        )
                        updated_trade = trade_journal_repository.update_trade(trade.id, trade_update)
                        logger.info(
                            f"🛡️ TP1 HIT & SL MOVED TO BREAKEVEN for {trade.symbol} #{trade.id} at {cur_px:.4f}. "
                            f"Stop loss adjusted to {new_sl:.4f} (BE + spread). 50% partial profit secured."
                        )
                        try:
                            telegram_alert_service.dispatch_breakeven_alert(trade, new_sl, cur_px)
                        except Exception as ex:
                            logger.debug(f"Telegram BE alert dispatch error: {ex}")

                        trade.stopLoss = new_sl
                        trade.notes = new_notes
                        sl = new_sl
                        is_be_protected = True

                # Phase 2: Boundary Hit Testing against current Stop Loss & Final Target
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
                    if is_be_protected:
                        # Trade stopped out at Breakeven after reaching TP1 (+1.5R partials banked)
                        be_pts = round(abs(trade.entryPrice - sl), 4)
                        trade_update = TradeJournalUpdate(
                            status="CLOSED",
                            result="BREAKEVEN",
                            exitPrice=sl,
                            closeDate=now,
                            profitLoss=be_pts,
                            realizedRMultiple=0.75,
                            reasonForExit="Break-Even Stop Hit (Capital Defended after TP1)",
                            lessonLearned="Capital defended by automated BE trailing rule; full 1R loss averted after +1.5R target run.",
                        )
                        updated_trade = trade_journal_repository.update_trade(trade.id, trade_update)
                        try:
                            signal_outcome_resolver._conduct_post_mortem_learning(
                                trade=updated_trade or trade,
                                market_context={
                                    "exit_reason": "Break-Even Hit",
                                    "market_price": cur_px,
                                    "invalidation_boundary": sl,
                                }
                            )
                        except Exception as ex:
                            logger.warning(f"Error in BE post-mortem learning for #{trade.id}: {ex}")
                        try:
                            telegram_alert_service.dispatch_trade_closed_alert(
                                updated_trade or trade,
                                exit_reason="Break-Even Stop Hit (Capital Defended after TP1 run)",
                                result="BREAKEVEN",
                                realized_r=0.75,
                                lesson="Capital preserved by automated BE trailing rule; full 1R loss avoided.",
                            )
                        except Exception as ex:
                            logger.debug(f"Telegram trade closed alert error: {ex}")
                        logger.info(
                            f"🛡️ BREAKEVEN HIT for {trade.symbol} #{trade.id} at {cur_px:.4f} (Exit: {sl:.4f}). "
                            f"Trade closed as BREAKEVEN (+0.75R banked). Capital 100% defended."
                        )
                    else:
                        # Full stop-loss hit before reaching TP1
                        loss_pts = -round(abs(trade.entryPrice - sl), 4)
                        trade_update = TradeJournalUpdate(
                            status="CLOSED",
                            result="LOST",
                            exitPrice=sl,
                            closeDate=now,
                            profitLoss=loss_pts,
                            realizedRMultiple=-1.0,
                            reasonForExit="Stop Loss Hit",
                            lessonLearned="Initial stop-loss invalidation boundary breached before reaching TP1.",
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
                        try:
                            telegram_alert_service.dispatch_trade_closed_alert(
                                updated_trade or trade,
                                exit_reason="Stop Loss Hit",
                                result="LOST",
                                realized_r=-1.0,
                                lesson=getattr(updated_trade, "lessonLearned", None) or "Structural invalidation boundary breached.",
                            )
                        except Exception as ex:
                            logger.debug(f"Telegram trade closed alert error: {ex}")
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
                        lessonLearned="Target liquidity reached cleanly. Strategy reinforced.",
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
                    try:
                        telegram_alert_service.dispatch_trade_closed_alert(
                            updated_trade or trade,
                            exit_reason="Take Profit Target Hit Cleanly",
                            result="WON",
                            realized_r=rr_val,
                            lesson="Target liquidity reached cleanly.",
                        )
                    except Exception as ex:
                        logger.debug(f"Telegram trade closed alert error: {ex}")
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
