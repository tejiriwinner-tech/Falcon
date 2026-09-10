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
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from app.core.providers import provider_manager
from app.core.repository.mission_repository import mission_repository
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.services.signal_service import signal_service
from app.schemas.signal_outcome import SignalOutcomeItem, SignalResolutionSummary
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalItem, TradeJournalUpdate

logger = logging.getLogger("falcon.signal_outcome_resolver")


class SignalOutcomeResolver:
    """Automated signal tracking, boundary breach detection, and post-mortem learning."""

    def __init__(self):
        self._resolved_cache: Dict[int, SignalOutcomeItem] = {}

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

    def resolve_signals(self, force_simulate: bool = False) -> SignalResolutionSummary:
        """
        Scan active signals and mission candidates against real-time quotes.
        Immediately purges any dummy non-trades, monitors ALL open trades in the database,
        detects SL/TP breaches, diagnoses root causes, and updates trade journal and intelligence.
        """
        now = datetime.now(timezone.utc)

        # Step 0: Purge any invalid dummy non-trades (e.g. WAIT with entry=0)
        try:
            trade_journal_repository.purge_invalid_trades()
        except Exception as ex:
            logger.warning(f"Error purging invalid trades: {ex}")

        # Step 1: Ingest any newly emitted signals from signal_service
        all_stored_trades = trade_journal_repository.list_trades()
        existing_sig_ids: Set[int] = {
            t.signalId for t in all_stored_trades if t.signalId is not None
        }

        try:
            signal_resp = signal_service.build_signals(mission_limit=10)
            for sig in signal_resp.signals:
                action = sig.action.upper()
                if action not in ("BUY", "SELL"):
                    continue
                if sig.entry <= 0 or sig.stopLoss <= 0 or sig.takeProfit <= 0:
                    continue

                if sig.id not in existing_sig_ids:
                    risk_dist = abs(sig.entry - sig.stopLoss)
                    reward_dist = abs(sig.takeProfit - sig.entry)
                    rr = round(reward_dist / risk_dist, 2) if risk_dist > 0 else 1.0

                    trade_create = TradeJournalCreate(
                        signalId=sig.id,
                        strategyId=sig.strategyId,
                        symbol=sig.symbol,
                        direction=action,
                        entryPrice=sig.entry,
                        exitPrice=None,
                        stopLoss=sig.stopLoss,
                        takeProfit=sig.takeProfit,
                        timeframe=sig.timeframe,
                        marketSession="London / New York",
                        tradeDate=sig.timestamp,
                        closeDate=None,
                        status="OPEN",
                        result="OPEN",
                        profitLoss=0.0,
                        riskReward=rr,
                        confidence=sig.confidence,
                        reasonForEntry=f"Signal #{sig.id} initiated by {sig.strategyName}",
                        notes=f"Active signal monitored by Falcon ({sig.strategyName})",
                    )
                    created = trade_journal_repository.create_trade(trade_create)
                    existing_sig_ids.add(sig.id)
                    all_stored_trades.append(created)
                    logger.info(f"Ingested new signal #{sig.id} ({sig.symbol} {action}) as OPEN")
        except Exception as e:
            logger.warning(f"Error ingesting new signals: {e}")

        # Step 2: Query ALL currently OPEN trades from the database
        all_stored_trades = trade_journal_repository.list_trades()
        open_trades = [
            t for t in all_stored_trades
            if t.status.upper() == "OPEN" and t.direction.upper() in ("BUY", "SELL") and t.entryPrice > 0
        ]

        total_checked = len(open_trades)
        resolved_count = 0
        wins_count = 0
        losses_count = 0
        open_count = 0
        new_outcomes: List[SignalOutcomeItem] = []

        # Step 3: Evaluate every open trade against current market quotes
        for trade in open_trades:
            symbol = trade.symbol
            direction = trade.direction.upper()
            entry = trade.entryPrice
            stop_loss = trade.stopLoss
            take_profit = trade.takeProfit

            quote_resp = provider_manager.get_market_quote(symbol)
            if not quote_resp or not quote_resp.quote:
                open_count += 1
                continue

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
                continue

            # Step 4: Automated Root-Cause Post-Mortem Diagnostic
            if result == "LOSS":
                losses_count += 1
                is_spread_spike = (
                    ("XAU" in symbol and spread >= 0.35)
                    or ("EUR" in symbol and spread >= 0.0003)
                    or ("GBP" in symbol and spread >= 0.00035)
                    or spread > 2.5
                )
                is_off_peak = trade.marketSession.lower() in ["asian", "tokyo", "sydney", "off-peak"]

                if is_spread_spike:
                    reason_exit = f"Stop Loss hit at {exit_price:.4f}. Spread widened to {spread:.4f} during volatility surge."
                    lesson = "Spread expansion triggered premature stop-out. Widen structural volatility buffers during session transitions."
                elif is_off_peak:
                    reason_exit = f"Stop Loss hit at {exit_price:.4f}. Off-peak session liquidity drought caused momentum stall."
                    lesson = "Filter out aggressive breakouts outside London/New York peak overlap hours."
                else:
                    reason_exit = f"Stop Loss hit at {exit_price:.4f}. Institutional counter-trend order flow broke key structural level."
                    lesson = "Breakout failed to sustain volume; preserve capital and require multi-timeframe trend confirmation."
            else:
                wins_count += 1
                reason_exit = f"Take Profit target reached cleanly at {exit_price:.4f}."
                lesson = "Optimal alignment between institutional trend, momentum, and session liquidity."

            # Step 5: Calculate PnL and update Trade Journal to CLOSED
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

            trade_update = TradeJournalUpdate(
                exitPrice=exit_price,
                closeDate=now,
                status="CLOSED",
                result=result,
                profitLoss=pnl,
                riskReward=risk_reward,
                confidence=trade.confidence,
                reasonForExit=reason_exit,
                lessonLearned=lesson,
                notes=f"Auto-resolved by Falcon Outcome Resolver ({trade.notes or 'Falcon'})",
            )

            try:
                trade_journal_repository.update_trade(trade.id, trade_update)
                resolved_count += 1

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
