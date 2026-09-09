"""
Falcon Signal Service
Builds the /signals feed from stored mission artifacts (signal candidates and
their decisions). No signal is invented here: an empty repository yields an
empty feed.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.engines.strategy_engine import StrategyEngine
from app.core.repository.mission_repository import mission_repository
from app.schemas.decision_artifact import DecisionArtifact, DecisionStatus
from app.schemas.signal import SignalItem, SignalListResponse
from app.schemas.signal_candidate import SignalCandidate

_DECISION_TO_SIGNAL_STATUS: Dict[DecisionStatus, str] = {
    DecisionStatus.APPROVED: "ACTIVE",
    DecisionStatus.MONITORING: "MONITORING",
    DecisionStatus.PENDING: "PENDING",
    DecisionStatus.REJECTED: "REJECTED",
}


class SignalService:
    """Projects stored pipeline artifacts into the signal contract."""

    def __init__(self) -> None:
        self._strategy_engine = StrategyEngine()

    def build_signals(self, mission_limit: int = 5) -> SignalListResponse:
        now = datetime.now(timezone.utc)
        
        # Fast path: Return empty signals if no missions exist
        all_missions = mission_repository.get_all_missions()
        if not all_missions:
            return SignalListResponse(
                signals=[],
                lastUpdated=now,
                dataAgeSeconds=0,
            )
        
        missions = all_missions[-mission_limit:]

        # Gather all candidates with their associated decisions from recent missions
        candidate_pool: List[dict] = []
        for mission in reversed(missions):
            try:
                artifacts = mission_repository.get_mission_artifacts(mission.id)
                candidates: List[SignalCandidate] = artifacts.get("candidates", [])
                decisions: List[DecisionArtifact] = artifacts.get("decisions", [])
                by_candidate = {d.candidateId: d for d in decisions}

                for index, candidate in enumerate(candidates):
                    dec = by_candidate.get(candidate.id)
                    is_approved = dec is not None and dec.status == DecisionStatus.APPROVED
                    
                    # Calculate composite conviction score
                    # Approved setups get high priority (+100); then rank by confidence & execution readiness
                    readiness = getattr(candidate, "readinessScore", 50.0) or 50.0
                    confidence = float(candidate.confidence)
                    conviction_score = (100.0 if is_approved else 0.0) + (confidence * 0.5) + (readiness * 0.5)

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

        # Deduplicate strictly by Symbol (at most 1 setup per asset to eliminate conflicting duplicate signals)
        seen_symbols = set()
        curated_pool: List[dict] = []
        for item in candidate_pool:
            symbol = item["candidate"].symbol
            if symbol not in seen_symbols:
                seen_symbols.add(symbol)
                curated_pool.append(item)

        # Limit to the TOP 1 to 3 elite setups only
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
            else "London / New York"
        )
        timeframe = strategy.bestTimeframe if strategy else "H1"

        is_approved = decision is not None and decision.status == DecisionStatus.APPROVED
        is_ready = getattr(candidate, "readinessScore", 0) >= 80

        if is_approved and is_ready:
            status = "ACTIVE"
            trend_str = f"trend '{candidate.marketSnapshot.trend}'" if candidate.marketSnapshot else "trend"
            spread_str = f"spread {candidate.marketSnapshot.spread:.2f} pips" if candidate.marketSnapshot else "spread"
            analysis = (
                f"✅ CLEARED FOR EXECUTION: Strategy '{candidate.strategyName}' aligned across {trend_str}, "
                f"{spread_str}, and liquidity. Optimal entry window: Current {preferred_session} session. "
                f"SL placed with structural volatility buffer."
            )
        else:
            status = "WAITING"
            decision_rec = (
                decision.recommendationDetails.recommendation.value
                if decision and hasattr(decision, "recommendationDetails")
                else "WAIT"
            )
            # Pull exact dynamic reasons evaluated by the pipeline
            reason_details = ""
            if decision and hasattr(decision, "recommendationDetails") and decision.recommendationDetails.description:
                reason_details = decision.recommendationDetails.description
            elif candidate.reasons:
                failed_reasons = [r.description for r in candidate.reasons if not r.passed]
                if failed_reasons:
                    reason_details = failed_reasons[0].replace("\n", " ")
            
            if not reason_details:
                reason_details = "Awaiting execution readiness score >= 80% and session volume confirmation."

            current_session = candidate.marketSnapshot.session if candidate.marketSnapshot and candidate.marketSnapshot.session else "Active"
            spread_val = f"Live Spread: {candidate.marketSnapshot.spread:.2f} pips." if candidate.marketSnapshot and candidate.marketSnapshot.spread else ""

            analysis = (
                f"⏳ DO NOT ENTER YET (Captain Decision: {decision_rec}). Setup is monitoring on WATCHLIST. "
                f"Reason: {reason_details} "
                f"Target Window: {preferred_session} (Current: {current_session}). {spread_val} "
                f"Do not place on MT5 until status is ACTIVE."
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
        )

    @staticmethod
    def _signal_id(mission_id: str, index: int) -> int:
        digits = "".join(char for char in mission_id if char.isdigit())
        mission_number = int(digits) if digits else 0
        return mission_number * 100 + index + 1

    get_signals = build_signals


signal_service = SignalService()
