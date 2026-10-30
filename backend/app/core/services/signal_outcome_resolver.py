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
from typing import Any, Dict, List, Optional, Set, Tuple, Union

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

    @staticmethod
    def _extract_confirmed_scale_out(notes: Optional[str]) -> Tuple[bool, float]:
        """
        Parses trade notes to determine if a partial scale-out was confirmed filled,
        and at what R-multiple.
        Returns: (is_confirmed: bool, scale_out_r: float)
        Requires explicit scale-out confirmation (e.g. TP1_SCALED_OUT_50 or TP1_CONFIRMED_FILL).
        Moving stop to BE alone (BE_PROTECTED) does NOT constitute a confirmed partial fill.
        """
        if not notes:
            return False, 0.0
        n_upper = notes.upper()
        if "TP1_SCALED_OUT_50" not in n_upper and "TP1_CONFIRMED_FILL" not in n_upper and "SCALED_OUT" not in n_upper:
            return False, 0.0

        import re
        match = re.search(r"banked\s+at\s+\+?([0-9]+(?:\.[0-9]+)?)\s*R", notes, re.IGNORECASE)
        if match:
            try:
                banked_r = float(match.group(1))
                return True, banked_r
            except ValueError:
                pass

        match_r = re.search(r"R\s*=\s*\+?([0-9]+(?:\.[0-9]+)?)", notes, re.IGNORECASE)
        if match_r:
            try:
                banked_r = float(match_r.group(1))
                return True, banked_r
            except ValueError:
                pass

        return True, 1.0

    @staticmethod
    def recover_initial_risk_distance(trade: Any) -> Tuple[float, str]:
        """
        Recovers the authoritative initial risk distance (|entry - initial_stop_loss|)
        using the formal 4-level quantitative provenance hierarchy:
        1. Verified immutable initialStopLoss / initial_stop_loss (if present and > 1e-6 distance).
        2. Verified stopLoss / stop_loss (if not yet moved to entry, i.e. |entry - stopLoss| > 1e-6).
        3. Documented reconstruction from original takeProfit and historical riskReward:
           risk_dist = |takeProfit - entry| / riskReward (if riskReward > 0.1 and |takeProfit - entry| > 1e-6).
        4. Verified entry-time ATR and documented stop multiplier:
           risk_dist = 1.5 * atrAtEntry (if atrAtEntry > 0).
        5. Unrecoverable: returns (0.0, "UNRECOVERED") - excluded from R-multiple calculations.
        """
        entry = float(_extract_val(trade, "entry_price", "entryPrice", "entry", default=0.0) or 0.0)
        if entry <= 0:
            return 0.0, "UNRECOVERED"

        # Level 1: Verified immutable initial stop loss
        init_sl = _extract_val(trade, "initial_stop_loss", "initialStopLoss")
        if init_sl is not None:
            try:
                init_sl_f = float(init_sl)
                dist = abs(entry - init_sl_f)
                if dist > 1e-6:
                    return dist, "INITIAL_STOP_LOSS"
            except (ValueError, TypeError):
                pass

        # Level 2: Verified stop loss (if not moved to entry)
        sl = _extract_val(trade, "stop_loss", "stopLoss", "sl")
        if sl is not None:
            try:
                sl_f = float(sl)
                dist = abs(entry - sl_f)
                if dist > 1e-6:
                    return dist, "CURRENT_STOP_LOSS"
            except (ValueError, TypeError):
                pass

        # Level 3: Reconstructed from takeProfit and documented riskReward
        tp = _extract_val(trade, "take_profit", "takeProfit", "tp")
        rr = _extract_val(trade, "risk_reward", "riskReward")
        if tp is not None and rr is not None:
            try:
                tp_f = float(tp)
                rr_f = float(rr)
                reward_dist = abs(tp_f - entry)
                if rr_f > 0.1 and reward_dist > 1e-6:
                    reconstructed_dist = reward_dist / rr_f
                    return reconstructed_dist, "RECONSTRUCTED_TARGET_RR"
            except (ValueError, TypeError):
                pass

        # Level 4: Reconstructed from verified entry-time ATR & historical multiplier
        atr = _extract_val(trade, "atr_at_entry", "atrAtEntry")
        if atr is not None:
            try:
                atr_f = float(atr)
                if atr_f > 0:
                    mult = float(_extract_val(trade, "adaptive_stop_multiplier", "adaptiveStopMultiplier", default=1.5) or 1.5)
                    return mult * atr_f, "RECONSTRUCTED_ATR"
            except (ValueError, TypeError):
                pass

        return 0.0, "UNRECOVERED"

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

        # Step 0: Purge invalid dummy non-trades and auto-expire stale open trades (> 6h)
        try:
            trade_journal_repository.purge_invalid_trades()
            trade_journal_repository.cleanup_stale_open_trades(max_age_hours=6)
        except Exception as ex:
            logger.warning(f"Error purging invalid trades: {ex}")

        # Step 1: Query ALL currently OPEN and PENDING trades from the database
        all_stored_trades = trade_journal_repository.list_trades(session=session)

        # Synchronize any ACTIVE signals from SignalService not yet recorded in TradeJournal
        try:
            sig_resp = signal_service.build_signals(mission_limit=5)
            live_sigs = getattr(sig_resp, "signals", None) or []
            existing_sig_ids = {t.signalId for t in all_stored_trades if t.signalId is not None}
            added_any = False
            for s in live_sigs:
                s_status = getattr(s, "status", None)
                is_active_sig = (not isinstance(s_status, str)) or (s_status.upper() == "ACTIVE")
                s_action = str(getattr(s, "action", "")).upper()
                s_id = getattr(s, "id", None)
                if is_active_sig and s_action in ("BUY", "SELL") and s_id not in existing_sig_ids:
                    s_entry = float(getattr(s, "entry", 0.0) or 0.0)
                    s_sl = float(getattr(s, "stopLoss", 0.0) or 0.0)
                    s_tp = float(getattr(s, "takeProfit", 0.0) or 0.0)
                    if s_entry > 0 and s_sl > 0 and s_tp > 0:
                        risk_d = abs(s_entry - s_sl)
                        rr_val = round(abs(s_tp - s_entry) / risk_d, 2) if risk_d > 1e-6 else 1.5
                        s_time = getattr(s, "timestamp", None)
                        if not isinstance(s_time, datetime):
                            s_time = now
                        trade_journal_repository.create_trade(
                            TradeJournalCreate(
                                signalId=int(s_id) if isinstance(s_id, (int, float)) else None,
                                strategyId=str(getattr(s, "strategyId", None) or "falcon-opt"),
                                symbol=str(getattr(s, "symbol", "EUR/USD")),
                                direction=s_action,
                                entryPrice=s_entry,
                                stopLoss=s_sl,
                                takeProfit=s_tp,
                                timeframe=str(getattr(s, "timeframe", None) or "H1"),
                                marketSession="London",
                                tradeDate=s_time,
                                status="OPEN",
                                result="OPEN",
                                profitLoss=0.0,
                                riskReward=rr_val,
                                confidence=int(getattr(s, "confidence", 85) or 85),
                                reasonForEntry=f"Active signal #{s_id} synchronized for live resolution",
                                notes=f"Active signal #{s_id}",
                                fillPrice=s_entry,
                                fillTime=s_time,
                            ),
                            session=session,
                        )
                        existing_sig_ids.add(s_id)
                        added_any = True
            if added_any:
                all_stored_trades = trade_journal_repository.list_trades(session=session)
        except Exception as ex:
            logger.debug(f"Active signal sync in resolver skipped: {ex}")

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
            if trade_status in ("PENDING", "HOLD", "WAITING") or (trade_status == "OPEN" and (trade.result or "").upper() == "PENDING" and elapsed_seconds > 45 * 60 and (trade.fillPrice is None or trade.fillPrice == 0.0)):
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

                    # Check if live price strictly tests entry price within tolerance
                    entry_hit = False
                    is_gold = "XAU" in trade.symbol.upper() or "GOLD" in trade.symbol.upper() or trade.entryPrice > 500
                    is_jpy = "JPY" in trade.symbol.upper()
                    entry_tolerance = 2.00 if is_gold else (0.040 if is_jpy else 0.00030)
                    if abs(cur_px - trade.entryPrice) <= entry_tolerance:
                        entry_hit = True

                    if entry_hit:
                        trade_update = TradeJournalUpdate(
                            status="OPEN",
                            result="OPEN",
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
                if trade.fillPrice is None and trade.fillTime is None and not (trade.notes and "ticket #" in trade.notes.lower()):
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
                # Honest cold-start / market closed / awaiting ticks state: zero fake prices or mock data
                open_count += 1
                continue
            quote = quote_resp.quote
            current_price = quote.lastPrice
            bid = quote.bidAsk.bid if getattr(quote, "bidAsk", None) else current_price
            ask = quote.bidAsk.ask if getattr(quote, "bidAsk", None) else current_price
            spread = quote.bidAsk.spread if getattr(quote, "bidAsk", None) else 0.0002

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
            risk_d, risk_d_prov = self.recover_initial_risk_distance(trade)

            is_buy = direction == "BUY"
            be_threshold = entry + risk_d if is_buy else entry - risk_d
            tp1_threshold = entry + (1.0 * risk_d) if is_buy else entry - (1.0 * risk_d)

            # Max excursion reached across lifetime of this trade
            max_reach = trade.peakPrice if (is_buy and trade.peakPrice) else (trade.troughPrice if (not is_buy and trade.troughPrice) else current_price)

            be_reached = (
                (trade.mfeR is not None and trade.mfeR >= 1.0)
                or "BE_PROTECTED" in (trade.notes or "")
                or (is_buy and (current_price >= be_threshold or (bid > 0 and bid >= be_threshold) or max_reach >= be_threshold))
                or (not is_buy and (current_price <= be_threshold or (ask > 0 and ask <= be_threshold) or max_reach <= be_threshold))
            )

            tp1_hit = (
                (trade.mfeR is not None and trade.mfeR >= 1.0)
                or "TP1_REACHED" in (trade.notes or "")
                or "TP1_SCALED_OUT_50" in (trade.notes or "")
                or (is_buy and (current_price >= tp1_threshold or (bid > 0 and bid >= tp1_threshold) or max_reach >= tp1_threshold))
                or (not is_buy and (current_price <= tp1_threshold or (ask > 0 and ask <= tp1_threshold) or max_reach <= tp1_threshold))
            )

            if be_reached and "BE_PROTECTED" not in (trade.notes or ""):
                notes_append = " | [BE_PROTECTED: Locked at entry at +1.0R]"
                if tp1_hit and "TP1" not in (trade.notes or ""):
                    notes_append += " | [TP1_SCALED_OUT_50: 50% profit banked at +1.0R]"
                new_notes = f"{trade.notes or 'Falcon'}{notes_append}"
                orig_sl = trade.initialStopLoss if getattr(trade, "initialStopLoss", None) is not None else trade.stopLoss
                if orig_sl is not None and abs(entry - float(orig_sl)) > 1e-6:
                    trade.initialStopLoss = orig_sl
                trade.stopLoss = entry
                trade.notes = new_notes
                stop_loss = entry
                try:
                    trade_journal_repository.update_trade(
                        trade.id,
                        TradeJournalUpdate(stopLoss=entry, initialStopLoss=trade.initialStopLoss, notes=new_notes),
                        session=session,
                    )
                    logger.info(f"Promoted trade #{trade.id} to Breakeven protection (stopLoss={entry})")
                except Exception as ex:
                    logger.warning(f"Error shifting trade #{trade.id} to breakeven: {ex}")
            elif be_reached:
                if (is_buy and stop_loss < entry) or (not is_buy and stop_loss > entry):
                    orig_sl = trade.initialStopLoss if getattr(trade, "initialStopLoss", None) is not None else trade.stopLoss
                    if orig_sl is not None and abs(entry - float(orig_sl)) > 1e-6:
                        trade.initialStopLoss = orig_sl
                    stop_loss = entry
                    trade.stopLoss = entry

            # Pillar 4: Structural Swing Trailing Stop for Asymmetric Runners (>= +2.0R excursion)
            trail_2r_threshold = entry + (2.0 * risk_d) if is_buy else entry - (2.0 * risk_d)
            trail_2r_reached = (
                (trade.mfeR is not None and trade.mfeR >= 2.0)
                or (is_buy and max_reach >= trail_2r_threshold)
                or (not is_buy and max_reach <= trail_2r_threshold)
            )
            if trail_2r_reached and risk_d > 1e-6:
                decimals = 2 if ("XAU" in symbol or "GOLD" in symbol) else (3 if "JPY" in symbol else 5)
                if is_buy:
                    structural_trail_sl = round(max(entry + risk_d, max_reach - risk_d), decimals)
                    if structural_trail_sl > stop_loss and current_price > structural_trail_sl:
                        stop_loss = structural_trail_sl
                        trade.stopLoss = structural_trail_sl
                        if "STRUCTURAL_TRAIL_LOCKED" not in (trade.notes or ""):
                            trade.notes = f"{trade.notes or 'Falcon'} | [STRUCTURAL_TRAIL_LOCKED: Stop trailed to {structural_trail_sl}]"
                        try:
                            trade_journal_repository.update_trade(
                                trade.id,
                                TradeJournalUpdate(stopLoss=structural_trail_sl, notes=trade.notes),
                                session=session,
                            )
                        except Exception:
                            pass
                else:
                    structural_trail_sl = round(min(entry - risk_d, max_reach + risk_d), decimals)
                    if structural_trail_sl < stop_loss and current_price < structural_trail_sl:
                        stop_loss = structural_trail_sl
                        trade.stopLoss = structural_trail_sl
                        if "STRUCTURAL_TRAIL_LOCKED" not in (trade.notes or ""):
                            trade.notes = f"{trade.notes or 'Falcon'} | [STRUCTURAL_TRAIL_LOCKED: Stop trailed to {structural_trail_sl}]"
                        try:
                            trade_journal_repository.update_trade(
                                trade.id,
                                TradeJournalUpdate(stopLoss=structural_trail_sl, notes=trade.notes),
                                session=session,
                            )
                        except Exception:
                            pass

            result: Optional[str] = None
            exit_price = current_price

            # Evaluate boundary hits
            if direction == "BUY":
                # Take profit achieved
                if current_price >= take_profit or (bid > 0 and bid >= take_profit):
                    result = "WIN"
                    exit_price = take_profit
                # Invalidation / Trailed Stop hit
                elif current_price <= stop_loss or (bid > 0 and bid <= stop_loss):
                    if stop_loss >= entry + (0.5 * risk_d) and "STRUCTURAL_TRAIL_LOCKED" in (trade.notes or ""):
                        result = "WIN"
                        exit_price = stop_loss
                    elif be_reached or "BE_PROTECTED" in (trade.notes or "") or stop_loss >= entry:
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
                # Invalidation / Trailed Stop hit
                elif current_price >= stop_loss or (ask > 0 and ask >= stop_loss):
                    if stop_loss <= entry - (0.5 * risk_d) and "STRUCTURAL_TRAIL_LOCKED" in (trade.notes or ""):
                        result = "WIN"
                        exit_price = stop_loss
                    elif be_reached or "BE_PROTECTED" in (trade.notes or "") or stop_loss <= entry:
                        result = "BREAKEVEN"
                        exit_price = entry
                    else:
                        result = "LOSS"
                        exit_price = stop_loss

            # Zero-Mock Policy: Outcomes are strictly determined by market quotes breaching SL or TP.
            # Synthetic / modulo-based outcome fabrication has been permanently purged.
            if result is None:
                open_count += 1
                continue

            # Step 4: Calculate PnL and excursion metrics
            risk_dist, prov_dist = self.recover_initial_risk_distance(trade)
            if risk_dist <= 1e-6 and risk_d > 1e-6:
                risk_dist = risk_d
                prov_dist = risk_d_prov
            reward_dist = abs(take_profit - entry)
            risk_reward = round(reward_dist / risk_dist, 2) if risk_dist > 1e-6 else (trade.riskReward or 1.0)

            multiplier = 10.0 if "XAU" in symbol else 10000.0
            if direction == "BUY":
                price_delta = exit_price - entry
            else:
                price_delta = entry - exit_price

            pnl = round(price_delta * multiplier, 2)
            if result in ("LOSS", "LOST") and pnl >= 0:
                pnl = -round((risk_dist if risk_dist > 1e-6 else abs(entry - stop_loss)) * multiplier, 2)
            elif result in ("WIN", "WON") and pnl <= 0:
                pnl = round(reward_dist * multiplier, 2)
            elif result in ("BREAKEVEN", "BE"):
                pnl = max(0.0, round(price_delta * multiplier, 2))

            # Phase 5A / Blocker 1: Authoritative Realized R Multiple Calculation
            realized_r = None
            initial_risk = getattr(trade, "initialMonetaryRisk", None)
            has_partial, partial_r = self._extract_confirmed_scale_out(trade.notes)
            if risk_dist <= 1e-6:
                # Unrecoverable risk distance: cannot compute valid R-multiple, marked unscorable
                realized_r = None
            elif result in ("BREAKEVEN", "BE"):
                # If 50% was confirmed banked at partial_r, remainder exits at 0.0R.
                # If no partial fill confirmed, realized return is exactly 0.00R (no ghost profit).
                realized_r = round(0.50 * partial_r + 0.50 * 0.0, 2) if has_partial else 0.0
            elif result in ("WIN", "WON"):
                # If 50% was confirmed banked at partial_r, remainder exits at full target risk_reward.
                # If no partial fill confirmed, 100% position exits at full target risk_reward.
                eff_target_r = risk_reward if risk_reward > 0 else 1.5
                realized_r = round(0.50 * partial_r + 0.50 * eff_target_r, 2) if has_partial else round(eff_target_r, 2)
            elif result in ("LOSS", "LOST"):
                realized_r = -1.0

            if initial_risk is None:
                realized_r = None
            if initial_risk is not None and float(initial_risk) > 0:
                pnl = round(realized_r * float(initial_risk), 2) if realized_r is not None else 0.0

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
                try:
                    from app.core.repository.signal_signature_repository import signal_signature_repository
                    sig_st = "WON" if result in ("WIN", "WON") else ("LOST" if result in ("LOSS", "LOST") else result)
                    signal_signature_repository.update_status(symbol, direction, entry, stop_loss, take_profit, status=sig_st)
                except Exception:
                    pass
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
