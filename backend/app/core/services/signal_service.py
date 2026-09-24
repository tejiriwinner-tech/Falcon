import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

logger = logging.getLogger("falcon.signal_service")

from app.core.repository.mission_repository import mission_repository
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.engines.strategy_engine import StrategyEngine
from app.core.services.signal_authorization_service import signal_authorization_service
from app.schemas.decision_artifact import DecisionArtifact, DecisionStatus
from app.schemas.execution_order import ExecutionSettings
from app.schemas.signal_candidate import SignalCandidate, CandidateStatus, CandidateDirection
from app.schemas.signal import SignalItem, SignalListResponse


class SignalService:
    """
    Curates, ranks, and serves high-conviction sniper trading signals.
    Enforces quality over quantity:
    - Filters out low confidence (< 80%) and unconfirmed setups.
    - Attaches precise sniper entry rules, invalidation levels, and timeframes.
    - Decoupled across assets and active market sessions.
    """

    def __init__(self) -> None:
        self._strategy_engine = StrategyEngine()

    def build_signals(self, mission_limit: int = 5) -> SignalListResponse:
        now = datetime.now(timezone.utc)
        signals: List[SignalItem] = []
        seen_signatures = set()

        # Step 1: Query TradeJournal for recently RESOLVED trades (WON, LOST, BREAKEVEN)
        # These are authoritative completed trade outcomes.
        try:
            closed_trades = [
                t for t in trade_journal_repository.list_trades()
                if t.status.upper() in ("CLOSED", "EXPIRED", "INVALIDATED")
                and t.result.upper() in ("WIN", "WON", "LOSS", "LOST", "BREAKEVEN", "BE", "EXPIRED", "INVALIDATED")
            ]
            closed_trades.sort(key=lambda t: t.closeDate or t.tradeDate, reverse=True)
            for ct in closed_trades[:5]:
                sig_key = (
                    ct.symbol,
                    ct.direction.upper(),
                    round(ct.entryPrice, 4),
                    round(ct.stopLoss, 4),
                    round(ct.takeProfit, 4),
                )
                if sig_key in seen_signatures:
                    continue
                seen_signatures.add(sig_key)

                res_str = ct.result.upper()
                if res_str in ("WIN", "WON"):
                    outcome_status = "WON"
                    analysis_msg = (
                        f"🏆 TARGET ACHIEVED [WON]: Take Profit hit cleanly at "
                        f"{ct.exitPrice or ct.takeProfit:.4f} (+{ct.profitLoss:+.1f} pts). "
                        f"R:R 1:{ct.riskReward:.1f} secured."
                    )
                elif res_str in ("BREAKEVEN", "BE"):
                    outcome_status = "BREAKEVEN"
                    analysis_msg = (
                        f"🛡️ CAPITAL DEFENDED [BREAKEVEN]: Market reached +1.0R excursion, "
                        f"stop shifted to entry ({ct.entryPrice:.4f}); exited with zero loss."
                    )
                elif res_str in ("EXPIRED", "INVALIDATED") or ct.status.upper() == "EXPIRED":
                    outcome_status = "EXPIRED"
                    analysis_msg = (
                        f"⏳ UNTRIGGERED SETUP [EXPIRED]: Market moved away without reaching "
                        f"entry ({ct.entryPrice:.4f}). Order auto-canceled cleanly without risk."
                    )
                else:
                    outcome_status = "LOST"
                    analysis_msg = (
                        f"🛑 STOPPED OUT [LOST]: Invalidation boundary hit at "
                        f"{ct.exitPrice or ct.stopLoss:.4f} (-{abs(ct.profitLoss):.1f} pts). "
                        f"Capital defended."
                    )

                dec = 2 if "XAU" in ct.symbol or ct.entryPrice > 100 else 4
                risk_d = abs(ct.entryPrice - ct.stopLoss)
                be_trig = ct.entryPrice + risk_d if ct.direction.upper() == "BUY" else ct.entryPrice - risk_d

                resolved_signal = SignalItem(
                    id=ct.signalId or ct.id,
                    symbol=ct.symbol,
                    action=ct.direction.upper(),
                    entry=ct.entryPrice,
                    takeProfit=ct.takeProfit,
                    stopLoss=ct.stopLoss,
                    confidence=ct.confidence or 80,
                    timeframe=ct.timeframe or "M15",
                    status=outcome_status,
                    analysis=analysis_msg,
                    timestamp=ct.tradeDate,
                    strategyId=ct.strategyId or "falcon-opt",
                    strategyName=ct.notes or "Falcon Strategy",
                    strategyVersion="4.2",
                    dataAgeSeconds=0,
                    triggerCondition="Trade Completed",
                    validUntil=ct.closeDate,
                    setupPattern=ct.notes or "Sniper Setup",
                    riskReward=ct.riskReward,
                    isPinned=False,
                    breakevenTrigger=round(be_trig, dec),
                    breakevenPrice=round(ct.entryPrice, dec),
                    isBreakeven=res_str in ("BREAKEVEN", "BE"),
                )
                signals.append(resolved_signal)
        except Exception as ex:
            logger.debug(f"Could not load resolved trades: {ex}")

        # Step 2: Ingest candidate setups from recent missions
        all_missions = mission_repository.get_all_missions()
        if all_missions:
            missions = all_missions[-mission_limit:]
            candidate_pool: List[dict] = []
            for mission in reversed(missions):
                try:
                    artifacts = mission_repository.get_mission_artifacts(mission.id)
                    candidates: List[SignalCandidate] = artifacts.get("candidates", [])
                    decisions: List[DecisionArtifact] = artifacts.get("decisions", [])
                    by_candidate = {d.candidateId: d for d in decisions}

                    for index, candidate in enumerate(candidates):
                        if candidate.direction == CandidateDirection.WAIT:
                            continue
                        if candidate.status == CandidateStatus.REJECTED:
                            continue
                        if candidate.confidence < 80:
                            continue

                        # Omit candidates older than 6 hours to eliminate ancient stale clutter
                        if candidate.generatedAt and (now - candidate.generatedAt).total_seconds() > 6 * 3600:
                            continue

                        dec = by_candidate.get(candidate.id)
                        is_approved = dec is not None and dec.status == DecisionStatus.APPROVED
                        readiness = getattr(candidate, "readinessScore", 50.0) or 50.0
                        confidence = float(candidate.confidence)

                        has_sniper = any(r.title.startswith("Sniper Setup:") for r in getattr(candidate, "reasons", []))
                        sniper_boost = 25.0 if has_sniper else 0.0
                        conviction_score = (100.0 if is_approved else 0.0) + sniper_boost + (confidence * 0.5) + (readiness * 0.5)

                        candidate_pool.append({
                            "candidate": candidate,
                            "decision": dec,
                            "signal_id": self._signal_id(mission.id, index),
                            "conviction_score": conviction_score,
                            "is_approved": is_approved,
                            "mission_id": mission.id,
                        })
                except Exception:
                    continue

            # Sort candidate pool by conviction score descending
            candidate_pool.sort(key=lambda x: x["conviction_score"], reverse=True)

            seen_symbols = set()
            curated_active: List[dict] = []
            curated_watchlist: List[dict] = []

            for item in candidate_pool:
                cand = item["candidate"]
                symbol = cand.symbol
                direction_str = cand.direction.value if hasattr(cand.direction, "value") else str(cand.direction)
                sig_key = (
                    symbol,
                    direction_str,
                    round(cand.entryPrice, 4),
                    round(cand.stopLoss, 4),
                    round(cand.takeProfit, 4),
                )
                # Skip if already closed in TradeJournal or duplicate in this batch
                if sig_key in seen_signatures:
                    continue
                seen_signatures.add(sig_key)

                # Check expiration: valid for 45 minutes
                valid_until = cand.generatedAt + timedelta(minutes=45)
                is_expired = now > valid_until
                is_approved = item["is_approved"]
                is_ready = getattr(cand, "readinessScore", 0) >= 80

                if is_approved and is_ready and not is_expired:
                    lot_size = ExecutionSettings().default_lot_size

                    decision = signal_authorization_service.evaluate_candidate(
                        candidate=cand,
                        signal_id=item["signal_id"],
                        lot_size=lot_size,
                    )
                    if decision.allowed:
                        if symbol not in seen_symbols:
                            seen_symbols.add(symbol)
                            item["is_guardian_authorized"] = True
                            item["lot_size"] = lot_size
                            curated_active.append(item)
                    else:
                        # Hard safety gate: rejected by Capital Guardian!
                        item["is_guardian_authorized"] = False
                        item["guardian_reason"] = decision.reason
                        if len(curated_watchlist) < 3:
                            curated_watchlist.append(item)
                elif not is_expired:
                    item["is_guardian_authorized"] = False
                    # Valid pending setup on watchlist
                    if len(curated_watchlist) < 3:
                        curated_watchlist.append(item)

            # Convert top active setups (max 3)
            active_items = [
                self._to_signal(
                    item["candidate"],
                    item["decision"],
                    item["signal_id"],
                    now,
                    is_active=True,
                    lot_size=item.get("lot_size"),
                )
                for item in curated_active[:3]
            ]

            # Convert top watchlist setups (max 3)
            watchlist_items = [
                self._to_signal(
                    item["candidate"],
                    item["decision"],
                    item["signal_id"],
                    now,
                    is_active=False,
                    guardian_reason=item.get("guardian_reason"),
                )
                for item in curated_watchlist[:3]
            ]

            # Assemble response: Active first, then Watchlist, then Resolved outcomes
            signals = active_items + watchlist_items + signals

        return SignalListResponse(
            signals=signals,
            lastUpdated=now,
            dataAgeSeconds=min(
                (signal.dataAgeSeconds for signal in signals), default=0
            ),
        )

    def _to_signal(
        self,
        candidate: SignalCandidate,
        decision: Optional[DecisionArtifact],
        signal_id: int,
        now: datetime,
        is_active: bool = False,
        lot_size: Optional[float] = None,
        guardian_reason: Optional[str] = None,
    ) -> SignalItem:
        strategy = self._strategy_engine.get_strategy_by_id(candidate.strategyId)
        preferred_session = (
            ", ".join(strategy.preferredSessions)
            if strategy and strategy.preferredSessions
            else "London / New York / Asian"
        )
        timeframe = strategy.bestTimeframe if strategy else "1h"

        # Check for sniper pattern
        pattern_reason = next(
            (r for r in getattr(candidate, "reasons", []) if r.title.startswith("Sniper Setup:")),
            None
        )
        if pattern_reason:
            setup_pattern = pattern_reason.title.replace("Sniper Setup: ", "").strip()
            trigger_rule = pattern_reason.description
        else:
            setup_pattern = candidate.strategyName
            trigger_rule = f"Enter on confirmed {candidate.direction.value} candle close. Invalidation at {candidate.stopLoss}."

        valid_until = candidate.generatedAt + timedelta(minutes=45)
        is_expired = now > valid_until

        # Calculate Breakeven targets (1:1 Risk-Reward threshold for risk-free protection)
        risk_dist = abs(candidate.entryPrice - candidate.stopLoss)
        dec = 2 if "XAU" in candidate.symbol or candidate.entryPrice > 100 else 4
        direction_val = candidate.direction.value.upper()
        if direction_val == "BUY":
            be_trigger = round(candidate.entryPrice + risk_dist, dec)
        else:
            be_trigger = round(candidate.entryPrice - risk_dist, dec)
        be_price = round(candidate.entryPrice, dec)

        # Determine if live market has already achieved Breakeven
        is_breakeven = False
        current_px = None
        try:
            from app.core.providers import provider_manager
            q = provider_manager.get_market_quote(candidate.symbol)
            if q and q.quote:
                current_px = q.quote.lastPrice
        except Exception:
            pass

        if current_px is not None and current_px > 0:
            if direction_val == "BUY" and current_px >= be_trigger:
                is_breakeven = True
            elif direction_val == "SELL" and current_px <= be_trigger:
                is_breakeven = True

        be_rule = f"BE Rule: Shift SL to Entry ({be_price}) at {be_trigger} (+1.0R risk-free)."

        if is_active and not is_expired:
            status = "ACTIVE"
            be_status_text = " [🛡️ BREAKEVEN LOCKED]" if is_breakeven else ""
            analysis = (
                f"🎯 SNIPER SIGNAL ACTIVE [{setup_pattern}]{be_status_text}: "
                f"{trigger_rule}. "
                f"Entry: {candidate.entryPrice} | SL: {candidate.stopLoss} | "
                f"TP: {candidate.takeProfit} (1:{candidate.riskReward:.1f} R:R). "
                f"{be_rule} "
                f"Active Window: {preferred_session}. Valid until {valid_until.strftime('%H:%M UTC')}."
            )
            # Note: Signal generation is informational and manual execution guidance only.
            # Normal signal generation never auto-dispatches execution orders.
        elif is_expired:
            status = "EXPIRED"
            analysis = (
                f"⌛ EXPIRED [{setup_pattern}]: Entry window expired at {valid_until.strftime('%H:%M UTC')}. "
                f"Setup is outside optimal session window."
            )
        else:
            status = "WAITING"
            rec_details = getattr(decision, "recommendationDetails", None) if decision else None
            if rec_details and getattr(rec_details, "recommendation", None):
                decision_rec = getattr(rec_details.recommendation, "value", str(rec_details.recommendation))
            elif decision and getattr(decision, "recommendation", None):
                decision_rec = getattr(decision.recommendation, "value", str(decision.recommendation))
            else:
                decision_rec = "WAIT"

            reason_details = ""
            if guardian_reason:
                reason_details = f"Capital Guardian: {guardian_reason}"
            elif rec_details and getattr(rec_details, "description", None):
                reason_details = rec_details.description
            elif candidate.reasons:
                failed_reasons = [r.description for r in candidate.reasons if not r.passed]
                if failed_reasons:
                    reason_details = failed_reasons[0].replace("\n", " ")
            
            if not reason_details:
                reason_details = f"Awaiting confirmed candle close trigger and execution readiness >= 80%."

            spread_val = f"Live Spread: {candidate.marketSnapshot.spread:.2f} pips." if candidate.marketSnapshot and candidate.marketSnapshot.spread else ""

            analysis = (
                f"⏳ WATCHLIST HUNTING [{setup_pattern}] (Status: {decision_rec}): "
                f"{trigger_rule} "
                f"Pending condition: {reason_details} {spread_val} "
                f"{be_rule} "
                f"Do not enter MT5 order until status turns ACTIVE."
            )

        return SignalItem(
            id=signal_id,
            symbol=candidate.symbol,
            action=candidate.direction.value,
            entry=candidate.entryPrice,
            takeProfit=candidate.takeProfit,
            stopLoss=candidate.stopLoss,
            confidence=candidate.confidence,
            timeframe=timeframe,
            status=status,
            analysis=analysis,
            timestamp=candidate.generatedAt,
            strategyId=candidate.strategyId,
            strategyName=candidate.strategyName,
            strategyVersion=candidate.strategyVersion,
            adaptiveRuleVersion=getattr(candidate, "adaptiveRuleVersion", None),
            adaptiveStopMultiplier=getattr(candidate, "adaptiveStopMultiplier", None),
            researchContext=getattr(candidate, "researchContext", None),
            dataAgeSeconds=candidate.marketDataAgeSeconds,
            triggerCondition=trigger_rule,
            validUntil=valid_until,
            setupPattern=setup_pattern,
            riskReward=candidate.riskReward,
            isPinned=False,
            breakevenTrigger=be_trigger,
            breakevenPrice=be_price,
            isBreakeven=is_breakeven,
        )

    @staticmethod
    def _signal_id(mission_id: str, index: int) -> int:
        digits = "".join(char for char in mission_id if char.isdigit())
        mission_number = int(digits) if digits else 0
        return mission_number * 100 + index + 1

    get_signals = build_signals


signal_service = SignalService()
