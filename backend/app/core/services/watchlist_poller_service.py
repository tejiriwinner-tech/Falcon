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
                latest_mission = None
                if hasattr(mission_repository, "get_latest_mission"):
                    latest_mission = mission_repository.get_latest_mission()
                elif hasattr(mission_repository, "get_recent_missions"):
                    recent = mission_repository.get_recent_missions(limit=1)
                    latest_mission = recent[-1] if recent else None

                needs_mission_refresh = True
                if latest_mission and getattr(latest_mission, "completedAt", None):
                    m_age = (now - latest_mission.completedAt).total_seconds()
                    if m_age < 300.0:
                        needs_mission_refresh = False
                if needs_mission_refresh:
                    from app.core.services.live_intelligence_service import LiveIntelligenceService
                    LiveIntelligenceService().generate_dashboard_intelligence()
                    logger.info("Autonomous background mission refresh completed across all active strategies.")
            except Exception as ex:
                logger.warning(f"Autonomous background mission refresh skipped: {ex}")

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

        # Step 3: Authoritative Exit Management delegated strictly to SignalOutcomeResolver
        try:
            resolver_summary = signal_outcome_resolver.resolve_signals()
            if resolver_summary:
                result["new_triggers"] += getattr(resolver_summary, "winsCount", 0)
                result["new_expirations"] += getattr(resolver_summary, "lossesCount", 0)
                logger.debug(
                    f"Authoritative signal resolver cycle: {resolver_summary.resolvedCount} resolved, "
                    f"{resolver_summary.winsCount} wins, {resolver_summary.lossesCount} losses, "
                    f"{resolver_summary.openCount} remaining open."
                )
        except Exception as ex:
            logger.warning(f"Error executing authoritative SignalOutcomeResolver: {ex}")

        # Step 4: Advance isolated paper/shadow trading lifecycle (DISABLED for clean live trading)
        if getattr(settings, "ENABLE_PAPER_TRADING", False):
            try:
                from app.core.engines.paper_runtime import paper_trading_runtime
                from app.core.engines.signal_generation_engine import SignalGenerationEngine
                from app.core.engines.strategy_engine import StrategyEngine
                from app.core.engines.market_state_engine import MarketStateEngine
                from app.schemas.strategy import StrategyStatus

                # Advance exits, expirations, and fills on existing paper positions
                paper_res = paper_trading_runtime.process_cycle()
                if paper_res.get("filled_count", 0) > 0 or paper_res.get("closed_count", 0) > 0:
                    logger.info(f"Paper trading cycle advanced: {paper_res}")

                # Safe shadow candidate evaluation across incubation strategies
                strat_engine = StrategyEngine()
                all_strats = strat_engine.get_strategies()
                incubation_strats = [s for s in all_strats if s.status == StrategyStatus.INCUBATION]
                if incubation_strats:
                    market_state = MarketStateEngine().get_market_state()
                    if market_state and market_state.quoteStatus != "INSUFFICIENT_DATA":
                        sig_gen = SignalGenerationEngine()
                        shadow_cands = sig_gen.generate_shadow_candidates(
                            market_state=market_state,
                            strategies=incubation_strats,
                            as_of=now,
                        )
                        for cand in shadow_cands:
                            cand_dir = getattr(cand.direction, "value", str(cand.direction)).upper()
                            if cand_dir in ("BUY", "SELL"):
                                s_id_val = int(cand.id.split("-")[-1]) if ("-" in cand.id and cand.id.split("-")[-1].isdigit()) else abs(hash(cand.id)) % 1000000
                                paper_trading_runtime.reserve_paper_candidate(
                                    candidate=cand,
                                    signal_id=s_id_val,
                                )
            except Exception as ex:
                logger.debug(f"Paper trading cycle pass error: {ex}")

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
