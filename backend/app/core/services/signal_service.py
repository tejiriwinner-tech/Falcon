from datetime import datetime, timezone, timedelta
from typing import List, Optional

from app.core.repository.mission_repository import mission_repository
from app.core.engines.strategy_engine import StrategyEngine
from app.schemas.decision_artifact import DecisionArtifact, DecisionStatus
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
        
        all_missions = mission_repository.get_all_missions()
        if not all_missions:
            return SignalListResponse(
                signals=[],
                lastUpdated=now,
                dataAgeSeconds=0,
            )
        
        missions = all_missions[-mission_limit:]

        # Gather candidates from recent missions
        candidate_pool: List[dict] = []
        for mission in reversed(missions):
            try:
                artifacts = mission_repository.get_mission_artifacts(mission.id)
                candidates: List[SignalCandidate] = artifacts.get("candidates", [])
                decisions: List[DecisionArtifact] = artifacts.get("decisions", [])
                by_candidate = {d.candidateId: d for d in decisions}

                for index, candidate in enumerate(candidates):
                    # Quality gate: Reject WAIT, REJECTED, and low-confidence candidates
                    if candidate.direction == CandidateDirection.WAIT:
                        continue
                    if candidate.status == CandidateStatus.REJECTED:
                        continue
                    if candidate.confidence < 80:
                        continue

                    dec = by_candidate.get(candidate.id)
                    is_approved = dec is not None and dec.status == DecisionStatus.APPROVED
                    
                    readiness = getattr(candidate, "readinessScore", 50.0) or 50.0
                    confidence = float(candidate.confidence)
                    
                    # Approved setups prioritized; sniper pattern boosts conviction score
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

        if not candidate_pool:
            return SignalListResponse(signals=[], lastUpdated=now, dataAgeSeconds=0)

        # Sort candidate pool by conviction score descending
        candidate_pool.sort(key=lambda x: x["conviction_score"], reverse=True)

        # Deduplicate strictly by Symbol (at most 1 setup per asset)
        seen_symbols = set()
        curated_pool: List[dict] = []
        for item in candidate_pool:
            symbol = item["candidate"].symbol
            if symbol not in seen_symbols:
                seen_symbols.add(symbol)
                curated_pool.append(item)

        # Top 1 to 3 elite sniper setups
        top_setups = curated_pool[:3]

        signals: List[SignalItem] = [
            self._to_signal(
                item["candidate"],
                item["decision"],
                item["signal_id"],
                now,
            )
            for item in top_setups
        ]

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
    ) -> SignalItem:
        strategy = self._strategy_engine.get_strategy_by_id(candidate.strategyId)
        preferred_session = (
            ", ".join(strategy.preferredSessions)
            if strategy and strategy.preferredSessions
            else "London / New York / Asian"
        )
        timeframe = strategy.bestTimeframe if strategy else "M15"

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

        is_approved = decision is not None and decision.status == DecisionStatus.APPROVED
        is_ready = getattr(candidate, "readinessScore", 0) >= 80
        valid_until = candidate.generatedAt + timedelta(minutes=45)

        if is_approved and is_ready:
            status = "ACTIVE"
            analysis = (
                f"🎯 SNIPER SIGNAL ACTIVE [{setup_pattern}]: "
                f"{trigger_rule}. "
                f"Entry: {candidate.entryPrice} | SL: {candidate.stopLoss} | "
                f"TP: {candidate.takeProfit} (1:{candidate.riskReward:.1f} R:R). "
                f"Active Window: {preferred_session}. Valid until {valid_until.strftime('%H:%M UTC')}."
            )
        else:
            status = "WAITING"
            decision_rec = (
                decision.recommendationDetails.recommendation.value
                if decision and hasattr(decision, "recommendationDetails")
                else "WAIT"
            )
            reason_details = ""
            if decision and hasattr(decision, "recommendationDetails") and decision.recommendationDetails.description:
                reason_details = decision.recommendationDetails.description
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
            dataAgeSeconds=candidate.marketDataAgeSeconds,
            triggerCondition=trigger_rule,
            validUntil=valid_until,
            setupPattern=setup_pattern,
            riskReward=candidate.riskReward,
        )

    @staticmethod
    def _signal_id(mission_id: str, index: int) -> int:
        digits = "".join(char for char in mission_id if char.isdigit())
        mission_number = int(digits) if digits else 0
        return mission_number * 100 + index + 1

    get_signals = build_signals


signal_service = SignalService()
