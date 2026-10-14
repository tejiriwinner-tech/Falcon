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

        # Ingest any actionable active signals from signal_service as PENDING watchlist records
        try:
            sig_resp = signal_service.build_signals()
            sigs = getattr(sig_resp, "signals", []) if sig_resp else []
            for s in sigs:
                s_id = getattr(s, "id", None)
                s_st = (getattr(s, "status", "") or "").upper()
                s_act = (getattr(s, "action", "") or "").upper()
                if s_id and s_act in ("BUY", "SELL") and s_st in ("ACTIVE", "GENERATED"):
                    if not any(t.signalId == s_id for t in all_stored_trades):
                        s_sym = getattr(s, "symbol", "")
                        s_hour = now.hour
                        if 0 <= s_hour < 7:
                            s_session = "Asian"
                        elif 7 <= s_hour < 12:
                            s_session = "London"
                        elif 12 <= s_hour < 16:
                            s_session = "NY_Overlap"
                        elif 16 <= s_hour < 21:
                            s_session = "New York"
                        else:
                            s_session = "Asian"

                        new_t = trade_journal_repository.create_trade(
                            TradeJournalCreate(
                                signalId=s_id,
                                strategyId=getattr(s, "strategyId", "strat") or "strat",
                                symbol=s_sym,
                                direction=s_act,
                                entryPrice=float(getattr(s, "entry", 0.0)),
                                stopLoss=float(getattr(s, "stopLoss", 0.0)),
                                takeProfit=float(getattr(s, "takeProfit", 0.0)),
                                timeframe=getattr(s, "timeframe", "H1") or "H1",
                                marketSession=s_session,
                                tradeDate=getattr(s, "timestamp", now) or now,
                                status="PENDING",
                                result="PENDING",
                                fillPrice=None,
                                fillTime=None,
                                confidence=getattr(s, "confidence", 80) or 80,
                                reasonForEntry=getattr(s, "triggerCondition", "Falcon Signal Execution"),
                            ),
                            session=session,
                        )
                        all_stored_trades.append(new_t)
        except Exception as ex:
            logger.debug(f"Signal ingestion in resolver: {ex}")

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
            # Case 1: PENDING Reservations (Section 6)
            # -------------------------------------------------------------
            if trade_status in ("PENDING", "HOLD", "WAITING"):
                # Expiration: 45 minutes elapsed without fill
                if elapsed_seconds > 45 * 60:
                    trade_update = TradeJournalUpdate(
                        status="EXPIRED",
                        result="EXPIRED",
                        closeDate=now,
                        reasonForExit="Reservation expired: 45m elapsed without fill",
                        notes=f"{trade.notes or 'Falcon'} | Auto-expired unexecuted reservation after 45m",
                    )
                    trade_journal_repository.update_trade(trade.id, trade_update, session=session)
                    resolved_count += 1
                    logger.info(f"Expired unexecuted PENDING reservation #{trade.id} (Signal #{trade.signalId})")
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
                    entry_tolerance = trade.entryPrice * 0.0003
                    if trade.direction.upper() == "BUY":
                        if cur_px <= trade.entryPrice or abs(cur_px - trade.entryPrice) <= entry_tolerance:
                            entry_hit = True
                    elif trade.direction.upper() == "SELL":
                        if cur_px >= trade.entryPrice or abs(cur_px - trade.entryPrice) <= entry_tolerance:
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

                # Within 45m and SL not breached: remain PENDING to preserve user's execution window
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

            # Phase 5C & Precision: Track post-fill excursion first for OPEN/FILLED trades
            if (trade.status or "").upper() in ("OPEN", "FILLED"):
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
                        trade.peakPrice = new_peak
                        trade.troughPrice = new_trough
                        trade.mfeR = cur_mfe_r
                        trade.maeR = cur_mae_r
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

            # Institutional Round-Trip Protection: Evaluate Breakeven and TP1 Scale-Out BEFORE exit breach
            initial_sl = getattr(trade, "initialStopLoss", None) or trade.stopLoss
            risk_d = abs(entry - initial_sl)
            if risk_d <= 1e-6:
                risk_d = abs(entry - stop_loss)

            is_buy = direction == "BUY"
            be_threshold = entry + risk_d if is_buy else entry - risk_d
            tp1_threshold = entry + (1.5 * risk_d) if is_buy else entry - (1.5 * risk_d)

            # Max excursion reached across lifetime of this trade
            max_reach = trade.peakPrice if (is_buy and trade.peakPrice) else (trade.troughPrice if (not is_buy and trade.troughPrice) else current_price)

            be_reached = (
                (trade.mfeR is not None and trade.mfeR >= 1.0)
                or "BE_PROTECTED" in (trade.notes or "")
                or (is_buy and (current_price >= be_threshold or (bid > 0 and bid >= be_threshold) or max_reach >= be_threshold))
                or (not is_buy and (current_price <= be_threshold or (ask > 0 and ask <= be_threshold) or max_reach <= be_threshold))
            )

            tp1_hit = (
                (trade.mfeR is not None and trade.mfeR >= 1.5)
                or "TP1_REACHED" in (trade.notes or "")
                or "TP1_SCALED_OUT_50" in (trade.notes or "")
                or (is_buy and (current_price >= tp1_threshold or (bid > 0 and bid >= tp1_threshold) or max_reach >= tp1_threshold))
                or (not is_buy and (current_price <= tp1_threshold or (ask > 0 and ask <= tp1_threshold) or max_reach <= tp1_threshold))
            )

            if be_reached and "BE_PROTECTED" not in (trade.notes or ""):
                notes_append = " | [BE_PROTECTED: Locked at entry at +1.0R]"
                if tp1_hit and "TP1" not in (trade.notes or ""):
                    notes_append += " | [TP1_SCALED_OUT_50: 50% profit banked at +1.5R]"
                new_notes = f"{trade.notes or 'Falcon'}{notes_append}"
                trade.stopLoss = entry
                trade.notes = new_notes
                stop_loss = entry
                try:
                    trade_journal_repository.update_trade(trade.id, TradeJournalUpdate(stopLoss=entry, notes=new_notes), session=session)
                    logger.info(f"Promoted trade #{trade.id} to Breakeven protection (stopLoss={entry})")
                except Exception as ex:
                    logger.warning(f"Error shifting trade #{trade.id} to breakeven: {ex}")
            elif be_reached:
                stop_loss = entry
                trade.stopLoss = entry

            result: Optional[str] = None
            exit_price = current_price

            # Evaluate boundary hits
            if direction == "BUY":
                # Take profit achieved
                if current_price >= take_profit or (bid > 0 and bid >= take_profit):
                    result = "WIN"
                    exit_price = take_profit
                # Invalidation hit
                elif current_price <= stop_loss or (bid > 0 and bid <= stop_loss):
                    if be_reached or "BE_PROTECTED" in (trade.notes or "") or stop_loss >= entry:
                        result = "BREAKEVEN"
                        exit_price = entry
                    else:
                        result = "LOSS"
                        exit_price = stop_loss
            elif direction == "SELL":
                # Take profit achieved
                if current_price <= take_profit or (ask > 0 and ask <= take_profit):
                    result = "WIN"
                    exit_price = take_profit
                # Invalidation hit
                elif current_price >= stop_loss or (ask > 0 and ask >= stop_loss):
                    if be_reached or "BE_PROTECTED" in (trade.notes or "") or stop_loss <= entry:
                        result = "BREAKEVEN"
                        exit_price = entry
                    else:
                        result = "LOSS"
                        exit_price = stop_loss

            # Handle optional simulation trigger for testing
            if result is None and force_simulate:
                sig_key = trade.signalId or trade.id
                if sig_key % 3 == 0:
                    result = "WIN"
                    exit_price = take_profit
                elif sig_key % 3 == 1:
                    result = "LOSS"
                    exit_price = stop_loss
                else:
                    result = "BREAKEVEN"
                    exit_price = entry

            if result is None:
                open_count += 1
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
            if result in ("LOSS", "LOST") and pnl >= 0:
                pnl = -round(risk_dist * multiplier, 2)
            elif result in ("WIN", "WON") and pnl <= 0:
                pnl = round(reward_dist * multiplier, 2)
            elif result in ("BREAKEVEN", "BE"):
                pnl = max(0.0, round(price_delta * multiplier, 2))

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

                if result in ("WIN", "WON"):
                    realized_r = round(float(monetary_pnl) / float(initial_risk), 2)
                elif result in ("LOSS", "LOST"):
                    realized_r = -round(abs(float(monetary_pnl)) / float(initial_risk), 2)
                elif result in ("BREAKEVEN", "BE"):
                    realized_r = 0.75 if ("TP1" in (trade.notes or "") or "SCALED_OUT" in (trade.notes or "")) else 0.0

            if realized_r is None:
                if result in ("WIN", "WON"):
                    realized_r = risk_reward
                elif result in ("LOSS", "LOST"):
                    realized_r = -1.0
                elif result in ("BREAKEVEN", "BE"):
                    realized_r = 0.75 if ("TP1" in (trade.notes or "") or "SCALED_OUT" in (trade.notes or "")) else 0.0

            # Phase 5C: Excursion peak / trough & R finalization on close
            from app.core.analytics.execution_quality_service import execution_quality_service
            peak_val, trough_val, final_mfe_r, final_mae_r = execution_quality_service.finalize_closed_trade_excursion(
                trade=trade,
                exit_price=exit_price,
                close_time=now,
            )

            # Step 5: Closed-Loop Autonomous Forensic Diagnostics via Regime Memory Engine
            if result in ("LOSS", "LOST"):
                losses_count += 1
            elif result in ("WIN", "WON"):
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

            if result in ("LOSS", "LOST") and "stop loss" not in diagnostic.rationale.lower():
                reason_exit = f"Stop Loss hit: {diagnostic.rationale}"
            elif result in ("WIN", "WON") and "take profit" not in diagnostic.rationale.lower():
                reason_exit = f"Take Profit hit: {diagnostic.rationale}"
            else:
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
