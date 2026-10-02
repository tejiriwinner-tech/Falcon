"""
Falcon Signal Outcome Resolver and Feedback Engine.

Monitors ALL active open signals against live market price action from ProviderManager,
detects Stop Loss and Take Profit breaches, conducts automated root-cause
post-mortem diagnostics on losses, and records closed trade records into
the Trade Journal.

This triggers automatic self-learning across:
- Trade Intelligence (Win rate, streaks, session PnL)
- Strategy Intelligence and Adaptive Strategy Optimizer (Health scoring and penalties)
- Mobile Trade History
"""

import logging
import threading
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from sqlalchemy import text

from app.core.analytics.adaptive_tuning_engine import adaptive_tuning_engine
from app.core.analytics.regime_memory_engine import regime_memory_engine, _extract_val
from app.core.database import database_enabled, get_session
from app.core.providers import provider_manager
from app.core.repository.mission_repository import mission_repository
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.services.signal_service import signal_service
from app.schemas.regime_memory import PostMortemDiagnostic
from app.schemas.signal_outcome import SignalOutcomeItem, SignalResolutionSummary
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalItem, TradeJournalUpdate

logger = logging.getLogger("falcon.signal_outcome_resolver")

# Stable PostgreSQL transaction advisory lock key for Capital Guardian & Signal Lifecycle
FALCON_GUARDIAN_ADVISORY_LOCK_KEY: int = 8882026


class LifecycleClassification(str, Enum):
    LEGITIMATE_ACTUAL_EXECUTION = "LEGITIMATE_ACTUAL_EXECUTION"
    LEGACY_UNEXECUTED_RESERVATION = "LEGACY_UNEXECUTED_RESERVATION"
    DUPLICATE_SPECULATIVE_EXECUTION = "DUPLICATE_SPECULATIVE_EXECUTION"
    UNKNOWN = "UNKNOWN"


def classify_record(trade: TradeJournalItem, all_trades: List[TradeJournalItem]) -> LifecycleClassification:
    """
    Authoritatively classify a trade journal record using forensic lifecycle evidence.
    Distinguishes genuine executions from unexecuted reservations and speculative duplicates.
    Never guesses; returns UNKNOWN if provenance cannot be established.
    """
    # 1. Authoritative fill information proves actual execution
    if trade.fillPrice is not None or trade.fillTime is not None:
        return LifecycleClassification.LEGITIMATE_ACTUAL_EXECUTION

    if trade.notes and "ticket #" in trade.notes.lower():
        return LifecycleClassification.LEGITIMATE_ACTUAL_EXECUTION

    # 2. PENDING status: Legitimate reservation created by SignalAuthorizationService
    if (trade.status or "").upper() == "PENDING":
        return LifecycleClassification.LEGACY_UNEXECUTED_RESERVATION

    # 3. OPEN status with fillPrice is None: Forensic provenance check
    if (trade.status or "").upper() == "OPEN" and trade.fillPrice is None and trade.fillTime is None:
        # Check if record matches the known defective resolver behavior:
        # Erroneous duplicate creation with note 'Active signal monitored by Falcon'
        # alongside a paired PENDING reservation for the same analytical signalId.
        is_resolver_signature = bool(trade.notes and "Active signal monitored by Falcon" in trade.notes)
        has_paired_reservation = any(
            other.id != trade.id
            and other.signalId == trade.signalId
            and other.signalId is not None
            and (
                (other.status or "").upper() == "PENDING"
                or (other.reasonForEntry and "Capital Guardian authorized reservation" in other.reasonForEntry)
                or (other.notes and "Auto-reserved from signal candidate" in other.notes)
            )
            for other in all_trades
        )
        if is_resolver_signature and has_paired_reservation:
            return LifecycleClassification.DUPLICATE_SPECULATIVE_EXECUTION

        return LifecycleClassification.UNKNOWN

    return LifecycleClassification.UNKNOWN


class SignalOutcomeResolver:
    """Automated signal tracking, boundary breach detection, and post-mortem learning."""

    def __init__(self):
        self._resolved_cache: Dict[int, SignalOutcomeItem] = {}
        self._lock = threading.Lock()

    def get_outcomes(self, limit: int = 50) -> List[SignalOutcomeItem]:
        """Return all resolved signal outcomes, latest first."""
        trades = trade_journal_repository.list_trades()
        for trade in trades:
            if trade.signalId and trade.signalId not in self._resolved_cache:
                if trade.status.upper() == "CLOSED":
                    self._resolved_cache[trade.signalId] = SignalOutcomeItem(
                        signalId=trade.signalId,
                        symbol=trade.symbol,
                        direction=trade.direction,
                        strategyId=trade.strategyId or "unknown",
                        strategyName=trade.notes or "Falcon Strategy",
                        entryPrice=trade.entryPrice,
                        exitPrice=trade.exitPrice or trade.entryPrice,
                        stopLoss=trade.stopLoss,
                        takeProfit=trade.takeProfit,
                        result=trade.result,
                        profitLoss=trade.profitLoss,
                        riskReward=trade.riskReward,
                        reasonForExit=trade.reasonForExit,
                        lessonLearned=trade.lessonLearned,
                        resolvedAt=trade.closeDate or trade.updatedAt,
                    )
        outcomes = sorted(self._resolved_cache.values(), key=lambda x: x.resolvedAt, reverse=True)
        return outcomes[:limit]

    def _conduct_post_mortem_learning(
        self,
        trade: Union[TradeJournalItem, Dict[str, Any]],
        market_context: Optional[Dict[str, Any]] = None,
        session: Optional[object] = None,
    ) -> PostMortemDiagnostic:
        """Alias for resolve_trade_outcome to support background poller invocation."""
        return self.resolve_trade_outcome(trade=trade, market_context=market_context, session=session)

    def resolve_trade_outcome(
        self,
        trade: Union[TradeJournalItem, Dict[str, Any]],
        market_context: Optional[Dict[str, Any]] = None,
        session: Optional[object] = None,
    ) -> PostMortemDiagnostic:
        """
        Forensically resolve closed trade outcome and trigger closed-loop learning:
        1. Invokes regime_memory_engine.diagnose_and_record(trade, market_context).
        2. Populates trade.reasonForExit and trade.lessonLearned directly from the forensic diagnostic.
        3. Persists diagnostic outcomes to trade journal repository if trade record exists.
        4. Triggers regime_memory_engine.evaluate_strategy_health(strategy_id) (quarantines underperforming
           strategies with win rate < 35% or >= 3 consecutive losses to QUARANTINED_PAPER, and boosts
           resilient strategies with win rate >= 60% and PF >= 1.8 to BOOSTED).
        5. Synchronizes with AdaptiveRuleTuningEngine and coordinates loss-recovery metrics
           (1 loss = 2.0x, 2 losses = 4.0x, hard $20 ceiling, reset on win).
        """
        ctx = market_context or {}

        # 1. Forensic Diagnosis & Record in Regime Memory Ledger
        diagnostic = regime_memory_engine.diagnose_and_record(trade_record=trade, market_context=ctx)

        # 2. Populate reasonForExit and lessonLearned directly from forensic diagnostic result
        reason_exit = diagnostic.rationale
        lesson = diagnostic.lesson_learned

        if isinstance(trade, dict):
            trade["reasonForExit"] = reason_exit
            trade["lessonLearned"] = lesson
            trade["reason_for_exit"] = reason_exit
            trade["lesson_learned"] = lesson
        else:
            if hasattr(trade, "reasonForExit"):
                trade.reasonForExit = reason_exit
            if hasattr(trade, "lessonLearned"):
                trade.lessonLearned = lesson

        # 3. Update database repository if trade has an existing ID
        trade_id = _extract_val(trade, "id", "trade_id")
        if trade_id is not None:
            try:
                tid = int(trade_id)
                existing = trade_journal_repository.get_trade(tid, session=session)
                if existing:
                    update_kwargs: Dict[str, Any] = {
                        "reasonForExit": reason_exit,
                        "lessonLearned": lesson,
                    }
                    raw_res = _extract_val(trade, "result", "outcome")
                    if raw_res and existing.status != "CLOSED":
                        update_kwargs["status"] = "CLOSED"
                        update_kwargs["result"] = raw_res
                    trade_journal_repository.update_trade(
                        tid, TradeJournalUpdate(**update_kwargs), session=session
                    )
            except Exception as ex:
                logger.warning(f"Could not persist diagnostic updates for trade #{trade_id}: {ex}")

        # 4. Trigger strategy health evaluation
        strategy_id = str(_extract_val(trade, "strategy_id", "strategyId", default="unknown"))
        symbol = str(_extract_val(trade, "symbol", default="ALL")).upper()

        if strategy_id and strategy_id.lower() != "unknown":
            try:
                regime_memory_engine.evaluate_strategy_health(strategy_id=strategy_id, session=session)
            except Exception as ex:
                logger.warning(f"Error evaluating strategy health for '{strategy_id}': {ex}")

        # 5. Synchronize with AdaptiveRuleTuningEngine
        try:
            regime_memory_engine.sync_with_adaptive_tuning_engine(
                strategy_id=strategy_id, symbol=symbol, tuning_engine=adaptive_tuning_engine
            )
            adaptive_tuning_engine.get_strategy_tuning(
                strategy_id=strategy_id, symbol=symbol, session=session
            )
            adaptive_tuning_engine.get_loss_recovery_metrics(
                strategy_id=strategy_id, session=session
            )
        except Exception as ex:
            logger.warning(f"Error synchronizing adaptive tuning for strategy '{strategy_id}': {ex}")

        return diagnostic

    def resolve_signals(self, force_simulate: bool = False) -> SignalResolutionSummary:
        """
        Scan active signals and mission candidates against real-time quotes.
        Immediately purges any dummy non-trades, monitors ALL open trades in the database,
        detects SL/TP breaches, diagnoses root causes, and updates trade journal and intelligence.
        Protected by PostgreSQL advisory lock (8882026) and thread lock for concurrency.
        """
        with self._lock:
            if trade_journal_repository.persistent and database_enabled():
                with get_session() as session:
                    with session.begin():
                        self._acquire_advisory_lock_if_postgres(session)
                        return self._execute_resolve_signals(force_simulate=force_simulate, session=session)
            return self._execute_resolve_signals(force_simulate=force_simulate, session=None)

    def _acquire_advisory_lock_if_postgres(self, session: object) -> None:
        """Acquire PostgreSQL transaction advisory lock if connected to PostgreSQL."""
        try:
            bind = session.get_bind()
            if bind is not None and bind.dialect.name == "postgresql":
                session.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_id)"),
                    {"lock_id": FALCON_GUARDIAN_ADVISORY_LOCK_KEY},
                )
                logger.debug(f"Acquired pg_advisory_xact_lock({FALCON_GUARDIAN_ADVISORY_LOCK_KEY}) for resolver")
        except Exception as ex:
            logger.warning(f"Could not acquire PostgreSQL advisory lock in resolver: {ex}")

    def _execute_resolve_signals(
        self, force_simulate: bool = False, session: Optional[object] = None
    ) -> SignalResolutionSummary:
        now = datetime.now(timezone.utc)

        # Step 0: Purge any invalid dummy non-trades (e.g. WAIT with entry=0)
        try:
            trade_journal_repository.purge_invalid_trades()
        except Exception as ex:
            logger.warning(f"Error purging invalid trades: {ex}")

        # Step 1: Query ALL currently OPEN and PENDING trades from the database
        all_stored_trades = trade_journal_repository.list_trades(session=session)
        active_trades = [
            t for t in all_stored_trades
            if (t.status or "").upper() in ("OPEN", "PENDING", "FILLED")
            and t.closeDate is None
            and t.entryPrice > 0
        ]

        total_checked = len(active_trades)
        resolved_count = 0
        wins_count = 0
        losses_count = 0
        open_count = 0
        new_outcomes: List[SignalOutcomeItem] = []

        # Step 2: Evaluate every active trade
        for trade in active_trades:
            trade_status = (trade.status or "").upper()
            t_date = trade.tradeDate if trade.tradeDate.tzinfo else trade.tradeDate.replace(tzinfo=timezone.utc)
            elapsed_seconds = (now - t_date).total_seconds()

            # -------------------------------------------------------------
            # Case 1: PENDING / HOLD Watchlist Lifecycle (1h Expiration & Live Entry Hit Activation)
            # -------------------------------------------------------------
            if trade_status in ("PENDING", "HOLD", "WAITING"):
                # Expiration: 1 hour (60 minutes) elapsed on watchlist without hitting entry price
                if elapsed_seconds > 60 * 60:
                    trade_update = TradeJournalUpdate(
                        status="EXPIRED",
                        result="EXPIRED",
                        closeDate=now,
                        reasonForExit="Signal validity window (1h) elapsed on watchlist without hitting entry price",
                        notes=f"{trade.notes or 'Falcon'} | Auto-expired from watchlist after 1h",
                    )
                    trade_journal_repository.update_trade(trade.id, trade_update, session=session)
                    resolved_count += 1
                    logger.info(f"Expired unexecuted watchlist signal #{trade.id} (Signal #{trade.signalId}) after 1h")
                    continue

                # Authoritative market data check
                quote_resp = provider_manager.get_market_quote(trade.symbol)
                if quote_resp and quote_resp.quote and quote_resp.quote.lastPrice > 0:
                    cur_px = quote_resp.quote.lastPrice
                    is_invalidated = False
                    if trade.direction.upper() == "BUY" and cur_px <= trade.stopLoss:
                        is_invalidated = True
                    elif trade.direction.upper() == "SELL" and cur_px >= trade.stopLoss:
                        is_invalidated = True

                    if is_invalidated:
                        trade_update = TradeJournalUpdate(
                            status="INVALIDATED",
                            result="INVALIDATED",
                            closeDate=now,
                            reasonForExit="Setup invalidated: market price breached stop loss level prior to execution",
                            notes=f"{trade.notes or 'Falcon'} | Auto-invalidated unexecuted reservation",
                        )
                        trade_journal_repository.update_trade(trade.id, trade_update, session=session)
                        resolved_count += 1
                        logger.info(f"Invalidated unexecuted PENDING reservation #{trade.id} (Signal #{trade.signalId})")
                        continue

                    # Check if live price hit entry price
                    entry_hit = False
                    if trade.direction.upper() == "BUY":
                        if cur_px <= trade.entryPrice or abs(cur_px - trade.entryPrice) <= (trade.entryPrice * 0.0003):
                            entry_hit = True
                    elif trade.direction.upper() == "SELL":
                        if cur_px >= trade.entryPrice or abs(cur_px - trade.entryPrice) <= (trade.entryPrice * 0.0003):
                            entry_hit = True

                    if entry_hit:
                        trade_update = TradeJournalUpdate(
                            status="OPEN",
                            fillPrice=trade.entryPrice,
                            fillTime=now,
                            notes=f"{trade.notes or 'Falcon'} | Activated - Market hit entry price {trade.entryPrice}",
                        )
                        trade_journal_repository.update_trade(trade.id, trade_update, session=session)
                        logger.info(f"Signal #{trade.signalId or trade.id} reached entry price {trade.entryPrice} -> Activated to OPEN/ACTIVE")
                        open_count += 1
                        continue

                # Within 1h and entry not hit: remain HOLD/PENDING on watchlist
                open_count += 1
                continue

            # -------------------------------------------------------------
            # Case 2: OPEN / FILLED Lifecycle & Forensic Classification
            # -------------------------------------------------------------
            if trade_status in ("OPEN", "FILLED"):
                # If unexecuted (fillPrice is None and fillTime is None), classify forensically (Section 7, 8, 9)
                if not force_simulate and trade.fillPrice is None and trade.fillTime is None and not (trade.notes and "ticket #" in trade.notes.lower()):
                    classification = classify_record(trade, all_stored_trades)
                    if classification == LifecycleClassification.DUPLICATE_SPECULATIVE_EXECUTION:
                        if elapsed_seconds > 45 * 60:
                            trade_update = TradeJournalUpdate(
                                status="EXPIRED",
                                result="EXPIRED",
                                closeDate=now,
                                reasonForExit="Duplicate speculative record retired; parent signal expired without execution",
                                notes=f"{trade.notes or 'Falcon'} | Auto-expired duplicate speculative record",
                            )
                            trade_journal_repository.update_trade(trade.id, trade_update, session=session)
                            resolved_count += 1
                            logger.info(f"Retired duplicate speculative record #{trade.id} (Signal #{trade.signalId})")
                            continue
                    elif classification == LifecycleClassification.UNKNOWN:
                        # Section 8: UNKNOWN -> DO NOT MUTATE IT
                        logger.info(f"Legacy record #{trade.id} classified as UNKNOWN. Preserving without mutation.")
                        open_count += 1
                        continue

            # -------------------------------------------------------------
            # Case 3: Genuine Executed Trade Monitoring (SL/TP Boundary Breach)
            # -------------------------------------------------------------
            symbol = trade.symbol
            direction = trade.direction.upper()
            entry = trade.entryPrice
            stop_loss = trade.stopLoss
            take_profit = trade.takeProfit

            quote_resp = provider_manager.get_market_quote(symbol)
            if not quote_resp or not quote_resp.quote:
                if not force_simulate:
                    open_count += 1
                    continue
                current_price = entry
                bid = entry - 0.0001
                ask = entry + 0.0001
                spread = 0.0002
                quote = None
            else:
                quote = quote_resp.quote
                current_price = quote.lastPrice
                bid = quote.bidAsk.bid
                ask = quote.bidAsk.ask
                spread = quote.bidAsk.spread

            result: Optional[str] = None
            exit_price = current_price

            # Evaluate boundary hits
            if direction == "BUY":
                # For a BUY position, if current price or bid is at/below SL -> LOSS
                if current_price <= stop_loss or (bid > 0 and bid <= stop_loss):
                    result = "LOSS"
                    exit_price = stop_loss
                # If current price or bid is at/above TP -> WIN
                elif current_price >= take_profit or (bid > 0 and bid >= take_profit):
                    result = "WIN"
                    exit_price = take_profit
            elif direction == "SELL":
                # For a SELL position, if current price or ask is at/above SL -> LOSS
                if current_price >= stop_loss or (ask > 0 and ask >= stop_loss):
                    result = "LOSS"
                    exit_price = stop_loss
                # If current price or ask is at/below TP -> WIN
                elif current_price <= take_profit or (ask > 0 and ask <= take_profit):
                    result = "WIN"
                    exit_price = take_profit

            # Handle optional simulation trigger for testing
            if result is None and force_simulate:
                sig_key = trade.signalId or trade.id
                if sig_key % 2 == 0:
                    result = "WIN"
                    exit_price = take_profit
                else:
                    result = "LOSS"
                    exit_price = stop_loss

            if result is None:
                open_count += 1
                # Phase 5C: Track post-fill excursion for OPEN/FILLED trades
                if (trade.status or "").upper() in ("OPEN", "FILLED") and trade.fillPrice is not None:
                    obs_time = getattr(quote, "timestamp", now)
                    obs_price = bid if (direction == "BUY" and bid and bid > 0) else (
                        ask if (direction == "SELL" and ask and ask > 0) else current_price
                    )
                    if obs_price and obs_price > 0:
                        from app.core.analytics.execution_quality_service import execution_quality_service
                        new_peak, new_trough, cur_mfe_r, cur_mae_r = execution_quality_service.update_open_trade_excursion(
                            trade=trade,
                            observed_price=obs_price,
                            observation_time=obs_time,
                        )
                        if new_peak != trade.peakPrice or new_trough != trade.troughPrice:
                            trade_update = TradeJournalUpdate(
                                peakPrice=new_peak,
                                troughPrice=new_trough,
                                mfeR=cur_mfe_r,
                                maeR=cur_mae_r,
                            )
                            try:
                                trade_journal_repository.update_trade(trade.id, trade_update, session=session)
                            except Exception as ex:
                                logger.warning(f"Error updating open trade excursion for trade #{trade.id}: {ex}")
                continue

            # Step 4: Calculate PnL and excursion metrics
            risk_dist = abs(entry - stop_loss)
            reward_dist = abs(take_profit - entry)
            risk_reward = round(reward_dist / risk_dist, 2) if risk_dist > 0 else 1.0

            multiplier = 10.0 if "XAU" in symbol else 10000.0
            if direction == "BUY":
                price_delta = exit_price - entry
            else:
                price_delta = entry - exit_price

            pnl = round(price_delta * multiplier, 2)
            if result == "LOSS" and pnl >= 0:
                pnl = -round(risk_dist * multiplier, 2)
            elif result == "WIN" and pnl <= 0:
                pnl = round(reward_dist * multiplier, 2)

            # Phase 5A / Blocker 1: Authoritative Realized R Multiple Calculation
            realized_r = None
            initial_risk = getattr(trade, "initialMonetaryRisk", None)
            if initial_risk is not None and float(initial_risk) > 0:
                if "XAU" in symbol or "GOLD" in symbol:
                    monetary_pnl = round(price_delta * 1.0, 2)
                elif "JPY" in symbol:
                    monetary_pnl = round(price_delta * 1000.0 / 150.0, 2)
                else:
                    monetary_pnl = round(price_delta * 1000.0, 2)

                if result == "WIN":
                    realized_r = round(float(monetary_pnl) / float(initial_risk), 2)
                elif result == "LOSS":
                    realized_r = -round(abs(float(monetary_pnl)) / float(initial_risk), 2)
                elif result in ("BREAKEVEN", "BE"):
                    realized_r = 0.0

            # Phase 5C: Excursion peak / trough & R finalization on close
            from app.core.analytics.execution_quality_service import execution_quality_service
            peak_val, trough_val, final_mfe_r, final_mae_r = execution_quality_service.finalize_closed_trade_excursion(
                trade=trade,
                exit_price=exit_price,
                close_time=now,
            )

            # Step 5: Closed-Loop Autonomous Forensic Diagnostics via Regime Memory Engine
            if result == "LOSS":
                losses_count += 1
            else:
                wins_count += 1

            market_context = {
                "spread": spread,
                "bid": bid,
                "ask": ask,
                "current_price": current_price,
                "session": trade.marketSession or "",
                "peak_price": peak_val,
                "trough_price": trough_val,
                "exit_price": exit_price,
                "post_stop_price": current_price,
            }

            trade_diag_data = trade.model_dump() if hasattr(trade, "model_dump") else dict(trade)
            trade_diag_data.update({
                "exit_price": exit_price,
                "exitPrice": exit_price,
                "close_date": now,
                "closeDate": now,
                "status": "CLOSED",
                "result": result,
                "profit_loss": pnl,
                "profitLoss": pnl,
                "peak_price": peak_val,
                "trough_price": trough_val,
            })

            diagnostic = self.resolve_trade_outcome(
                trade=trade_diag_data,
                market_context=market_context,
                session=session,
            )

            reason_exit = diagnostic.rationale
            lesson = diagnostic.lesson_learned

            trade_update = TradeJournalUpdate(
                exitPrice=exit_price,
                closeDate=now,
                status="CLOSED",
                result=result,
                profitLoss=pnl,
                riskReward=risk_reward,
                realizedRMultiple=realized_r,
                peakPrice=peak_val,
                troughPrice=trough_val,
                mfeR=final_mfe_r,
                maeR=final_mae_r,
                confidence=trade.confidence,
                reasonForExit=reason_exit,
                lessonLearned=lesson,
                notes=f"Auto-resolved by Falcon Outcome Resolver ({trade.notes or 'Falcon'})",
                executionMode=getattr(trade, "executionMode", None),
            )


            try:
                trade_journal_repository.update_trade(trade.id, trade_update, session=session)
                trade.reasonForExit = reason_exit
                trade.lessonLearned = lesson
                trade.status = "CLOSED"
                trade.result = result
                resolved_count += 1

                strat_id = trade.strategyId or "unknown"
                if strat_id and strat_id.lower() != "unknown":
                    try:
                        regime_memory_engine.evaluate_strategy_health(strategy_id=strat_id, session=session)
                    except Exception as ex:
                        logger.warning(f"Error evaluating strategy health for '{strat_id}': {ex}")

                sig_identifier = trade.signalId or trade.id
                outcome_item = SignalOutcomeItem(
                    signalId=sig_identifier,
                    symbol=symbol,
                    direction=direction,
                    strategyId=trade.strategyId or "unknown",
                    strategyName=trade.notes or "Falcon Strategy",
                    entryPrice=entry,
                    exitPrice=exit_price,
                    stopLoss=stop_loss,
                    takeProfit=take_profit,
                    result=result,
                    profitLoss=pnl,
                    riskReward=risk_reward,
                    reasonForExit=reason_exit,
                    lessonLearned=lesson,
                    resolvedAt=now,
                )
                self._resolved_cache[sig_identifier] = outcome_item
                new_outcomes.append(outcome_item)
                logger.info(f"Resolved open trade #{trade.id} (Signal #{sig_identifier} {symbol} {direction}) -> {result} ({pnl:+0.2f})")
            except Exception as e:
                logger.error(f"Failed to update trade #{trade.id} in journal: {e}")

        return SignalResolutionSummary(
            totalChecked=total_checked,
            resolvedCount=resolved_count,
            winsCount=wins_count,
            lossesCount=losses_count,
            openCount=open_count,
            outcomes=new_outcomes,
            timestamp=now,
        )


signal_outcome_resolver = SignalOutcomeResolver()
