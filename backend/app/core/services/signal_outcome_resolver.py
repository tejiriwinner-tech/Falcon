"""
Falcon Signal Outcome Resolver and Feedback Engine.

Monitors active signals against live market price action from ProviderManager,
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
        Immediately journals newly generated signals as OPEN trades,
        resolves setups hitting SL/TP to CLOSED, diagnoses root causes, and logs to trade journal.
        """
        now = datetime.now(timezone.utc)
        existing_trades = trade_journal_repository.list_trades()
        existing_trades_by_sig_id: Dict[int, TradeJournalItem] = {
            t.signalId: t for t in existing_trades if t.signalId is not None
        }

        candidates_to_check = []

        # 1. From recent signals projection
        try:
            signal_resp = signal_service.build_signals(mission_limit=25)
            for sig in signal_resp.signals:
                candidates_to_check.append({
                    "signalId": sig.id,
                    "symbol": sig.symbol,
                    "direction": sig.action.upper(),
                    "entry": sig.entry,
                    "stopLoss": sig.stopLoss,
                    "takeProfit": sig.takeProfit,
                    "confidence": sig.confidence,
                    "timeframe": sig.timeframe,
                    "strategyId": sig.strategyId,
                    "strategyName": sig.strategyName,
                    "marketSession": "London / New York",
                    "timestamp": sig.timestamp,
                })
        except Exception as e:
            logger.warning(f"Could not fetch signals from signal_service: {e}")

        # 2. From mission repository
        try:
            all_missions = mission_repository.get_all_missions()
            recent_missions = all_missions[-25:] if len(all_missions) > 25 else all_missions
            for mission in recent_missions:
                artifacts = mission_repository.get_mission_artifacts(mission.id)
                candidates = artifacts.get("candidates", [])
                market_state = artifacts.get("marketState")
                session_name = market_state.session if market_state else "London"
                for idx, cand in enumerate(candidates):
                    sig_id = mission.id * 100 + idx
                    candidates_to_check.append({
                        "signalId": sig_id,
                        "symbol": cand.symbol,
                        "direction": cand.direction.upper() if hasattr(cand, "direction") else cand.action.upper(),
                        "entry": cand.entryPrice if hasattr(cand, "entryPrice") else getattr(cand, "entry", 0.0),
                        "stopLoss": cand.stopLoss,
                        "takeProfit": cand.takeProfit,
                        "confidence": getattr(cand, "confidence", 80),
                        "timeframe": getattr(cand, "timeframe", "H1"),
                        "strategyId": cand.strategyId,
                        "strategyName": cand.strategyName,
                        "marketSession": session_name,
                        "timestamp": mission.startedAt,
                    })
        except Exception as e:
            logger.warning(f"Could not fetch candidates from mission_repository: {e}")

        # Deduplicate candidates by signalId
        unique_candidates = {}
        for c in candidates_to_check:
            if c["signalId"] not in unique_candidates:
                unique_candidates[c["signalId"]] = c

        total_checked = len(unique_candidates)
        resolved_count = 0
        wins_count = 0
        losses_count = 0
        open_count = 0
        new_outcomes: List[SignalOutcomeItem] = []

        for sig_id, cand in unique_candidates.items():
            symbol = cand["symbol"]
            direction = cand["direction"]
            entry = cand["entry"]
            stop_loss = cand["stopLoss"]
            take_profit = cand["takeProfit"]

            risk_dist = abs(entry - stop_loss)
            reward_dist = abs(take_profit - entry)
            risk_reward = round(reward_dist / risk_dist, 2) if risk_dist > 0 else 1.0

            # STEP 1: If signal is not yet in Trade Journal, register it immediately as OPEN
            existing_trade = existing_trades_by_sig_id.get(sig_id)
            if existing_trade is None:
                trade_create = TradeJournalCreate(
                    signalId=sig_id,
                    strategyId=cand["strategyId"],
                    symbol=symbol,
                    direction=direction,
                    entryPrice=entry,
                    exitPrice=None,
                    stopLoss=stop_loss,
                    takeProfit=take_profit,
                    timeframe=cand["timeframe"],
                    marketSession=cand["marketSession"],
                    tradeDate=cand["timestamp"],
                    closeDate=None,
                    status="OPEN",
                    result="OPEN",
                    profitLoss=0.0,
                    riskReward=risk_reward,
                    confidence=cand["confidence"],
                    reasonForEntry=f"Signal #{sig_id} initiated by {cand['strategyName']}",
                    reasonForExit=None,
                    lessonLearned=None,
                    notes=f"Active signal monitored by Falcon ({cand['strategyName']})",
                )
                try:
                    existing_trade = trade_journal_repository.create_trade(trade_create)
                    existing_trades_by_sig_id[sig_id] = existing_trade
                    logger.info(f"Journaled newly emitted signal #{sig_id} ({symbol} {direction}) as OPEN")
                except Exception as ex:
                    logger.error(f"Failed to record OPEN trade for signal #{sig_id}: {ex}")

            # STEP 2: If trade is already CLOSED, skip
            if existing_trade and existing_trade.status.upper() == "CLOSED":
                continue

            # STEP 3: Check live quote for boundary breaches (SL or TP)
            quote_resp = provider_manager.get_market_quote(symbol)
            if not quote_resp or not quote_resp.quote:
                open_count += 1
                continue

            quote = quote_resp.quote
            current_price = quote.lastPrice
            spread = quote.bidAsk.spread

            result: Optional[str] = None
            exit_price = current_price

            # Evaluate boundary hits
            if direction == "BUY":
                if current_price <= stop_loss:
                    result = "LOSS"
                    exit_price = stop_loss
                elif current_price >= take_profit:
                    result = "WIN"
                    exit_price = take_profit
            elif direction == "SELL":
                if current_price >= stop_loss:
                    result = "LOSS"
                    exit_price = stop_loss
                elif current_price <= take_profit:
                    result = "WIN"
                    exit_price = take_profit

            # Handle optional simulation trigger
            if result is None and force_simulate:
                if sig_id % 2 == 0:
                    result = "WIN"
                    exit_price = take_profit
                else:
                    result = "LOSS"
                    exit_price = stop_loss

            if result is None:
                open_count += 1
                continue

            # STEP 4: Automated Root-Cause Post-Mortem Diagnostic
            if result == "LOSS":
                losses_count += 1
                is_spread_spike = (
                    ("XAU" in symbol and spread >= 0.35)
                    or ("EUR" in symbol and spread >= 0.0003)
                    or ("GBP" in symbol and spread >= 0.00035)
                    or spread > 2.5
                )
                is_off_peak = cand["marketSession"].lower() in ["asian", "tokyo", "sydney", "off-peak"]

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

            # STEP 5: Calculate PnL and update Trade Journal to CLOSED
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
                confidence=cand["confidence"],
                reasonForExit=reason_exit,
                lessonLearned=lesson,
                notes=f"Auto-resolved by Falcon Outcome Resolver ({cand['strategyName']})",
            )

            try:
                if existing_trade:
                    trade_journal_repository.update_trade(existing_trade.id, trade_update)
                else:
                    trade_create = TradeJournalCreate(
                        signalId=sig_id,
                        strategyId=cand["strategyId"],
                        symbol=symbol,
                        direction=direction,
                        entryPrice=entry,
                        exitPrice=exit_price,
                        stopLoss=stop_loss,
                        takeProfit=take_profit,
                        timeframe=cand["timeframe"],
                        marketSession=cand["marketSession"],
                        tradeDate=cand["timestamp"],
                        closeDate=now,
                        status="CLOSED",
                        result=result,
                        profitLoss=pnl,
                        riskReward=risk_reward,
                        confidence=cand["confidence"],
                        reasonForEntry=f"Signal #{sig_id} initiated by {cand['strategyName']}",
                        reasonForExit=reason_exit,
                        lessonLearned=lesson,
                        notes=f"Auto-resolved by Falcon Outcome Resolver ({cand['strategyName']})",
                    )
                    trade_journal_repository.create_trade(trade_create)

                resolved_count += 1

                outcome_item = SignalOutcomeItem(
                    signalId=sig_id,
                    symbol=symbol,
                    direction=direction,
                    strategyId=cand["strategyId"],
                    strategyName=cand["strategyName"],
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
                self._resolved_cache[sig_id] = outcome_item
                new_outcomes.append(outcome_item)
                logger.info(f"Successfully closed signal #{sig_id} ({symbol} {direction}) -> {result} ({pnl:+0.2f})")
            except Exception as e:
                logger.error(f"Failed to update trade journal entry for signal #{sig_id}: {e}")

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
