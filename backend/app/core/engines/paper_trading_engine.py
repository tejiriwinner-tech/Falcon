"""
Falcon V10 Phase 5F: Paper Trading Engine.

Implements the complete simulated trade lifecycle:
Signal Candidate -> Capital Guardian -> Authorization/Reservation -> PENDING
    -> Simulated Fill -> OPEN -> Simulated SL/TP -> CLOSED -> Canonical Analytics

Key Safety & Integrity Invariants:
1. Native pipeline integration: Uses existing Signal Candidate, Capital Guardian,
   and Trade Journal infrastructure. Does NOT create a second strategy engine.
2. Capital Isolation: PAPER trades pass through Capital Guardian decision rules in
   their own isolated PAPER context. PAPER reservations NEVER consume LIVE Guardian slots,
   never reduce LIVE active trading capital, never increase aggregate LIVE worst-case loss,
   and NEVER modify real active trading capital or protected profit.
3. Market Data: Uses authoritative market quotes from ProviderManager or provided
   quotes. Preserves BUY/SELL bid/ask conventions.
4. Deterministic Simultaneous SL/TP Handling: If both SL and TP are genuinely breached
   in the same market observation, Stop Loss (LOSS) takes priority as a conservative,
   fail-closed policy (zero optimistic bias).
5. Terminal Protection: Terminal trades (CLOSED, EXPIRED, INVALIDATED) cannot receive
   further market observations.
6. Provenance & Execution Quality: Full Phase 5C (MFE/MAE excursions), Phase 5D
   (version snapshot provenance), and Phase 5E (as_of lookahead protection) preserved.
7. Zero Automated Broker Execution: Strictly decision-support. No MT5 or Exness orders.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Dict, List, Optional, Tuple

from app.core.analytics.execution_quality_service import (
    ExecutionQualityService,
    execution_quality_service,
)
from app.core.execution.execution_mode_guard import (
    ExecutionMode,
    execution_mode_guard,
    parse_execution_mode,
)
from app.core.providers import provider_manager
from app.core.repository.trade_journal_repository import (
    TradeJournalRepository,
    trade_journal_repository,
)
from app.core.services.capital_guardian_service import (
    CapitalGuardianService,
    capital_guardian_service,
)
from app.core.services.signal_authorization_service import (
    SignalAuthorizationService,
    signal_authorization_service,
)
from app.schemas.capital_guardian import (
    CapitalGuardianDecision,
    ProposedTradeInput,
)
from app.schemas.market_quote import MarketQuote
from app.schemas.signal_candidate import SignalCandidate
from app.schemas.trade_journal import (
    TradeJournalCreate,
    TradeJournalItem,
    TradeJournalUpdate,
)

logger = logging.getLogger("falcon.paper_trading_engine")

TERMINAL_STATUSES = {"CLOSED", "EXPIRED", "INVALIDATED"}


class PaperTradingEngine:
    """
    Engine executing the simulated trade lifecycle in PAPER mode with strict
    capital isolation and Guardian safety.
    """

    def __init__(
        self,
        auth_service: Optional[SignalAuthorizationService] = None,
        guardian_service: Optional[CapitalGuardianService] = None,
        journal_repo: Optional[TradeJournalRepository] = None,
        quality_service: Optional[ExecutionQualityService] = None,
    ):
        self._auth_service = auth_service or signal_authorization_service
        self._guardian_service = guardian_service or capital_guardian_service
        self._journal_repo = journal_repo or trade_journal_repository
        self._quality_service = quality_service or execution_quality_service

    # ==========================================================================
    # 1. Candidate Authorization & Reservation (PENDING)
    # ==========================================================================

    def authorize_paper_candidate(
        self,
        candidate: SignalCandidate,
        signal_id: int,
        lot_size: Optional[Decimal | float] = None,
        strategy_id: Optional[str] = None,
        timeframe: Optional[str] = None,
        market_session: Optional[str] = None,
        notes: Optional[str] = None,
        confidence: Optional[int] = None,
        session: Optional[object] = None,
        as_of: Optional[datetime] = None,
    ) -> Tuple[CapitalGuardianDecision, Optional[TradeJournalItem]]:
        """
        Evaluate a candidate signal through Capital Guardian in the PAPER execution
        context and create a PENDING paper reservation if authorized.

        Safety:
        - Passed through the exact same Guardian invariants (3-trade limit & capital preservation).
        - Scoped strictly to execution_mode='PAPER' so paper trades NEVER consume LIVE capacity.
        - Preserves PostgreSQL transaction advisory lock (8882026).
        - Records Phase 5D provenance snapshots.
        """
        paper_notes = notes or f"Paper trade reservation for candidate #{signal_id}"

        return self._auth_service.authorize_candidate(
            candidate=candidate,
            signal_id=signal_id,
            lot_size=lot_size,
            strategy_id=strategy_id,
            timeframe=timeframe,
            market_session=market_session,
            notes=paper_notes,
            confidence=confidence,
            session=session,
            execution_mode=ExecutionMode.PAPER.value,
        )

    def authorize_and_reserve_paper(
        self,
        proposal: ProposedTradeInput,
        signal_id: Optional[int] = None,
        strategy_id: Optional[str] = None,
        timeframe: Optional[str] = None,
        market_session: Optional[str] = None,
        notes: Optional[str] = None,
        confidence: Optional[int] = None,
        session: Optional[object] = None,
        strategy_version: Optional[str] = None,
        adaptive_rule_version: Optional[str] = None,
        adaptive_stop_multiplier: Optional[float] = None,
        spread_at_entry: Optional[float] = None,
        atr_at_entry: Optional[float] = None,
    ) -> Tuple[CapitalGuardianDecision, Optional[TradeJournalItem]]:
        """Direct proposal authorization for paper trading."""
        paper_notes = notes or f"Paper trade reservation for proposal #{signal_id or 'N/A'}"
        return self._auth_service.authorize_and_reserve(
            proposal=proposal,
            signal_id=signal_id,
            strategy_id=strategy_id,
            timeframe=timeframe,
            market_session=market_session,
            notes=paper_notes,
            confidence=confidence,
            session=session,
            strategy_version=strategy_version,
            adaptive_rule_version=adaptive_rule_version,
            adaptive_stop_multiplier=adaptive_stop_multiplier,
            spread_at_entry=spread_at_entry,
            atr_at_entry=atr_at_entry,
            execution_mode=ExecutionMode.PAPER.value,
        )

    # ==========================================================================
    # 2. Simulated Fill (PENDING -> OPEN)
    # ==========================================================================

    def simulate_fill(
        self,
        trade_id: int,
        quote: Optional[MarketQuote] = None,
        fill_price: Optional[float] = None,
        fill_time: Optional[datetime] = None,
        session: Optional[object] = None,
    ) -> Optional[TradeJournalItem]:
        """
        Transition a PENDING paper trade to OPEN using authoritative market price.

        Rules:
        - Trade must exist and be in PENDING status.
        - Trade must be a PAPER trade (executionMode == 'PAPER').
        - Uses authoritative quote (BUY at Ask, SELL at Bid) or explicit fill_price.
        - Records fillTime, fillPrice, and initializes MFE/MAE excursion baseline.
        - Authoritative initialMonetaryRisk is strictly preserved from reservation.
        """
        trade = self._journal_repo.get_trade(trade_id, session=session)
        if not trade:
            logger.warning(f"Simulate fill failed: Trade #{trade_id} not found.")
            return None

        status_clean = (trade.status or "").strip().upper()
        if status_clean != "PENDING":
            logger.warning(
                f"Simulate fill failed: Trade #{trade_id} is '{trade.status}', expected PENDING."
            )
            return None

        # Verify paper mode
        trade_mode = getattr(trade, "executionMode", None) or parse_execution_mode(trade.notes)
        if trade_mode != ExecutionMode.PAPER.value:
            logger.warning(
                f"Simulate fill rejected: Trade #{trade_id} has execution mode '{trade_mode}', not PAPER."
            )
            return None

        now = fill_time or datetime.now(timezone.utc)
        resolved_fill_price: Optional[float] = fill_price

        if resolved_fill_price is None:
            # Resolve from market quote
            resolved_quote = quote
            if resolved_quote is None:
                quote_resp = provider_manager.get_market_quote(trade.symbol)
                if quote_resp and quote_resp.quote:
                    resolved_quote = quote_resp.quote

            if resolved_quote:
                direction = (trade.direction or "").upper()
                bid = getattr(getattr(resolved_quote, "bidAsk", None), "bid", None)
                ask = getattr(getattr(resolved_quote, "bidAsk", None), "ask", None)
                last_price = getattr(resolved_quote, "lastPrice", None)

                if direction == "BUY":
                    # Buy fills at Ask (or last price fallback)
                    resolved_fill_price = ask if (ask and ask > 0) else last_price
                elif direction == "SELL":
                    # Sell fills at Bid (or last price fallback)
                    resolved_fill_price = bid if (bid and bid > 0) else last_price
                else:
                    resolved_fill_price = last_price

        if resolved_fill_price is None or resolved_fill_price <= 0:
            # Fallback to intended entryPrice if no market quote available
            resolved_fill_price = trade.entryPrice

        update_payload = TradeJournalUpdate(
            status="OPEN",
            result="OPEN",
            fillPrice=float(resolved_fill_price),
            fillTime=now,
            peakPrice=float(resolved_fill_price),
            troughPrice=float(resolved_fill_price),
            mfeR=0.0,
            maeR=0.0,
            initialMonetaryRisk=trade.initialMonetaryRisk,
            executionMode=ExecutionMode.PAPER.value,
        )

        updated = self._journal_repo.update_trade(trade_id, update_payload, session=session)
        logger.info(
            f"[PAPER_FILLED] Trade #{trade_id} filled @ {resolved_fill_price:.5f} ({trade.symbol} {trade.direction}). Status -> OPEN."
        )
        return updated


    # ==========================================================================
    # 3. Market Price Evaluation & SL/TP Resolution (OPEN -> CLOSED)
    # ==========================================================================

    def evaluate_paper_trade(
        self,
        trade_id: int,
        current_price: Optional[float] = None,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        high: Optional[float] = None,
        low: Optional[float] = None,
        observation_time: Optional[datetime] = None,
        session: Optional[object] = None,
    ) -> Optional[TradeJournalItem]:
        """
        Evaluate an OPEN paper trade against market observations for SL/TP breaches.

        Exit Priority & Deterministic Resolution (Mandatory Requirement):
        - Evaluates boundary conditions against signal's intended SL and TP.
        - BUY:
            SL reached when price <= stop_loss (or bid <= stop_loss).
            TP reached when price >= take_profit (or bid >= take_profit).
        - SELL:
            SL reached when price >= stop_loss (or ask >= stop_loss).
            TP reached when price <= take_profit (or ask <= take_profit).
        - High/Low Bar Evaluation:
            If a bar (high, low) is supplied:
            BUY: sl_hit if low <= stop_loss; tp_hit if high >= take_profit.
            SELL: sl_hit if high >= stop_loss; tp_hit if low <= take_profit.
        - SIMULTANEOUS SL/TP HIT:
            When the observation genuinely indicates that BOTH SL and TP were reached
            (e.g. extreme volatility bar where low <= SL and high >= TP),
            Falcon adheres to its conservative, fail-closed policy:
            Stop Loss (LOSS) takes strict priority over Take Profit (WIN).
            Zero optimistic bias is allowed.
        - Terminal trades CANNOT receive further observations.
        - Capital Isolation: Real active trading capital and protected profit are
          NEVER modified by paper trade outcomes.
        """
        trade = self._journal_repo.get_trade(trade_id, session=session)
        if not trade:
            return None

        # Terminal check: once CLOSED, EXPIRED, or INVALIDATED, no further observations accepted
        status_clean = (trade.status or "").strip().upper()
        if status_clean in TERMINAL_STATUSES or trade.closeDate is not None:
            logger.debug(
                f"Trade #{trade_id} is in terminal state '{trade.status}'. Ignoring further observation."
            )
            return trade

        if status_clean != "OPEN":
            # PENDING trades must be filled before evaluation
            return trade

        now = observation_time or datetime.now(timezone.utc)
        direction = (trade.direction or "").upper()
        stop_loss = trade.stopLoss
        take_profit = trade.takeProfit
        entry = trade.fillPrice or trade.entryPrice

        # Primary observation price
        obs_price = current_price
        if obs_price is None:
            if direction == "BUY" and bid is not None and bid > 0:
                obs_price = bid
            elif direction == "SELL" and ask is not None and ask > 0:
                obs_price = ask

        if obs_price is None and high is None and low is None:
            return trade

        # Determine SL and TP breaches
        sl_hit = False
        tp_hit = False

        if direction == "BUY":
            # Spot price / bid checks
            if obs_price is not None:
                if obs_price <= stop_loss or (bid is not None and bid > 0 and bid <= stop_loss):
                    sl_hit = True
                if obs_price >= take_profit or (bid is not None and bid > 0 and bid >= take_profit):
                    tp_hit = True
            # Bar high/low checks
            if low is not None and low <= stop_loss:
                sl_hit = True
            if high is not None and high >= take_profit:
                tp_hit = True

        elif direction == "SELL":
            # Spot price / ask checks
            if obs_price is not None:
                if obs_price >= stop_loss or (ask is not None and ask > 0 and ask >= stop_loss):
                    sl_hit = True
                if obs_price <= take_profit or (ask is not None and ask > 0 and ask <= take_profit):
                    tp_hit = True
            # Bar high/low checks
            if high is not None and high >= stop_loss:
                sl_hit = True
            if low is not None and low <= take_profit:
                tp_hit = True

        # If neither hit: update excursion and remain OPEN
        if not sl_hit and not tp_hit:
            if obs_price and obs_price > 0:
                new_peak, new_trough, cur_mfe_r, cur_mae_r = (
                    self._quality_service.update_open_trade_excursion(
                        trade=trade,
                        observed_price=obs_price,
                        observation_time=now,
                    )
                )
                if new_peak != trade.peakPrice or new_trough != trade.troughPrice:
                    update_payload = TradeJournalUpdate(
                        peakPrice=new_peak,
                        troughPrice=new_trough,
                        mfeR=cur_mfe_r,
                        maeR=cur_mae_r,
                    )
                    return self._journal_repo.update_trade(
                        trade_id, update_payload, session=session
                    )
            return trade

        # ======================================================================
        # Exit Resolution (Deterministic Fail-Closed Convention)
        # ======================================================================
        result: str
        exit_price: float
        reason_exit: str
        lesson: str

        if sl_hit and tp_hit:
            # Genuine simultaneous breach: Stop Loss takes priority (fail closed)
            result = "LOSS"
            exit_price = stop_loss
            reason_exit = (
                f"Simultaneous SL/TP breach detected at {exit_price:.4f}. "
                "Resolved fail-closed to Stop Loss (conservative capital-preservation policy)."
            )
            lesson = (
                "Extreme price range breached both boundaries in single observation; "
                "fail-closed policy prevented optimistic outcome."
            )
            logger.warning(
                f"Ambiguous simultaneous SL/TP breach for PAPER trade #{trade_id}. "
                "Resolved fail-closed to LOSS at Stop Loss."
            )
        elif sl_hit:
            result = "LOSS"
            exit_price = stop_loss
            reason_exit = f"Paper Stop Loss reached at {exit_price:.4f}."
            lesson = "Counter-trend movement triggered risk boundary; capital preserved."
        else:  # tp_hit
            result = "WIN"
            exit_price = take_profit
            reason_exit = f"Paper Take Profit reached cleanly at {exit_price:.4f}."
            lesson = "Target reached according to strategy parameters."

        # Calculate monetary PnL
        symbol = trade.symbol.upper()
        price_delta = (exit_price - entry) if direction == "BUY" else (entry - exit_price)

        if "XAU" in symbol or "GOLD" in symbol:
            monetary_pnl = round(price_delta * 1.0, 2)
            multiplier = 10.0
        elif "JPY" in symbol:
            monetary_pnl = round(price_delta * 1000.0 / 150.0, 2)
            multiplier = 100.0
        else:
            monetary_pnl = round(price_delta * 1000.0, 2)
            multiplier = 10000.0

        pnl = round(price_delta * multiplier, 2)
        risk_dist = abs(entry - stop_loss)
        reward_dist = abs(take_profit - entry)

        if result == "LOSS" and pnl >= 0:
            pnl = -round(risk_dist * multiplier, 2)
        elif result == "WIN" and pnl <= 0:
            pnl = round(reward_dist * multiplier, 2)

        # Authoritative realized R Multiple (Phase 5A.1)
        realized_r = None
        initial_risk = getattr(trade, "initialMonetaryRisk", None)
        if initial_risk is not None and float(initial_risk) > 0:
            if risk_dist > 0:
                if result == "WIN":
                    realized_r = round(abs(price_delta) / risk_dist, 2)
                elif result == "LOSS":
                    realized_r = -round(abs(price_delta) / risk_dist, 2)
                elif result in ("BREAKEVEN", "BE"):
                    realized_r = 0.0
                if realized_r is not None:
                    monetary_pnl = round(realized_r * float(initial_risk), 2)
            else:
                if result == "WIN":
                    realized_r = round(float(monetary_pnl) / float(initial_risk), 2)
                elif result == "LOSS":
                    realized_r = -round(abs(float(monetary_pnl)) / float(initial_risk), 2)
                elif result in ("BREAKEVEN", "BE"):
                    realized_r = 0.0

        # Phase 5C: Finalize excursion metrics on close
        peak_val, trough_val, final_mfe_r, final_mae_r = (
            self._quality_service.finalize_closed_trade_excursion(
                trade=trade,
                exit_price=exit_price,
                close_time=now,
            )
        )

        risk_reward = round(reward_dist / risk_dist, 2) if risk_dist > 0 else 1.0

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
            reasonForExit=reason_exit,
            lessonLearned=lesson,
            executionMode=ExecutionMode.PAPER.value,
        )

        closed_trade = self._journal_repo.update_trade(trade_id, trade_update, session=session)
        logger.info(
            f"[PAPER_CLOSED] Trade #{trade_id} CLOSED -> {result} (PnL: {pnl:+0.2f}, Realized R: {realized_r}) @ {exit_price:.5f}. "
            "Reservation released. Real capital cycle untouched."
        )
        return closed_trade


    # ==========================================================================
    # 4. Terminal Alternatives (EXPIRED, INVALIDATED)
    # ==========================================================================

    def expire_paper_trade(
        self,
        trade_id: int,
        reason: str = "Untriggered reservation expired",
        expiration_time: Optional[datetime] = None,
        session: Optional[object] = None,
    ) -> Optional[TradeJournalItem]:
        """
        Transition an untriggered PENDING paper trade to EXPIRED.
        Releases the Capital Guardian reservation without recording a trading loss.
        """
        trade = self._journal_repo.get_trade(trade_id, session=session)
        if not trade or trade.status != "PENDING":
            return None

        now = expiration_time or datetime.now(timezone.utc)
        update_payload = TradeJournalUpdate(
            status="EXPIRED",
            result="EXPIRED",
            closeDate=now,
            reasonForExit=reason,
            lessonLearned="Patience preserved capital: untriggered paper reservation expired.",
            executionMode=ExecutionMode.PAPER.value,
        )
        return self._journal_repo.update_trade(trade_id, update_payload, session=session)

    def invalidate_paper_trade(
        self,
        trade_id: int,
        reason: str = "Setup invalidated prior to fill",
        invalidation_time: Optional[datetime] = None,
        session: Optional[object] = None,
    ) -> Optional[TradeJournalItem]:
        """
        Transition an untriggered PENDING paper trade to INVALIDATED.
        Releases the Capital Guardian reservation without recording a trading loss.
        """
        trade = self._journal_repo.get_trade(trade_id, session=session)
        if not trade or trade.status != "PENDING":
            return None

        now = invalidation_time or datetime.now(timezone.utc)
        update_payload = TradeJournalUpdate(
            status="INVALIDATED",
            result="INVALIDATED",
            closeDate=now,
            reasonForExit=reason,
            lessonLearned="Market conditions invalidated thesis before fill: capital preserved.",
            executionMode=ExecutionMode.PAPER.value,
        )
        return self._journal_repo.update_trade(trade_id, update_payload, session=session)

    # ==========================================================================
    # 5. Market Quote Processing
    # ==========================================================================

    def process_quote(
        self,
        quote: MarketQuote,
        session: Optional[object] = None,
    ) -> List[TradeJournalItem]:
        """
        Process a market quote across all active PAPER trades for the quote's symbol.
        1. Fills any PENDING paper trades whose entry conditions are met.
        2. Evaluates SL/TP for all OPEN paper trades.
        """
        all_trades = self._journal_repo.list_trades(session=session)
        symbol = (quote.symbol or "").replace("/", "").replace("_", "").upper()
        resolved_trades = []

        paper_trades = [
            t for t in all_trades
            if (t.symbol or "").replace("/", "").replace("_", "").upper() == symbol
            and (getattr(t, "executionMode", None) or parse_execution_mode(t.notes)) == ExecutionMode.PAPER.value
            and (t.status or "").upper() in ("PENDING", "OPEN")
            and t.closeDate is None
        ]

        current_price = getattr(quote, "lastPrice", None)
        bid = getattr(getattr(quote, "bidAsk", None), "bid", None)
        ask = getattr(getattr(quote, "bidAsk", None), "ask", None)
        obs_time = getattr(quote, "timestamp", None) or datetime.now(timezone.utc)

        for trade in paper_trades:
            if trade.status == "PENDING":
                # Simulated trigger check: if market price crosses intended entry
                direction = (trade.direction or "").upper()
                entry = float(trade.entryPrice) if trade.entryPrice is not None else None
                should_fill = False
                if entry is not None:
                    if direction == "BUY":
                        has_crossed = False
                        if current_price is not None and current_price <= entry:
                            has_crossed = True
                        elif ask is not None and ask <= entry:
                            has_crossed = True
                        should_fill = has_crossed
                    elif direction == "SELL":
                        has_crossed = False
                        if current_price is not None and current_price >= entry:
                            has_crossed = True
                        elif bid is not None and bid >= entry:
                            has_crossed = True
                        should_fill = has_crossed
                    else:
                        should_fill = True
                else:
                    should_fill = True

                if should_fill:
                    filled = self.simulate_fill(
                        trade_id=trade.id,
                        quote=quote,
                        fill_time=obs_time,
                        session=session,
                    )
                    if filled:
                        resolved_trades.append(filled)
            elif trade.status == "OPEN":
                evaluated = self.evaluate_paper_trade(
                    trade_id=trade.id,
                    current_price=current_price,
                    bid=bid,
                    ask=ask,
                    observation_time=obs_time,
                    session=session,
                )
                if evaluated:
                    resolved_trades.append(evaluated)

        return resolved_trades


paper_trading_engine = PaperTradingEngine()
