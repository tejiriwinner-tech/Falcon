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

        signals: List[SignalItem] = []
        seen_strategies = set()
        for mission in reversed(missions):
            try:
                artifacts = mission_repository.get_mission_artifacts(mission.id)
                candidates: List[SignalCandidate] = artifacts.get("candidates", [])
                decisions: List[DecisionArtifact] = artifacts.get("decisions", [])
                by_candidate = {d.candidateId: d for d in decisions}

                for index, candidate in enumerate(candidates):
                    dec = by_candidate.get(candidate.id)
                    is_active = dec and dec.status == DecisionStatus.APPROVED
                    strat_key = (candidate.symbol, candidate.strategyId)

                    # Always retain approved ACTIVE signals; for pending setups, keep only the latest per strategy
                    if is_active or strat_key not in seen_strategies:
                        seen_strategies.add(strat_key)
                        signals.append(
                            self._to_signal(
                                candidate,
                                dec,
                                self._signal_id(mission.id, index),
                                now,
                            )
                        )
            except Exception:
                continue  # Skip missions with artifact errors

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

        if decision is not None:
            status = _DECISION_TO_SIGNAL_STATUS.get(decision.status, decision.status.value)
            analysis = decision.recommendationDetails.description
        else:
            status = candidate.status.value
            analysis = candidate.reasons[0].description if candidate.reasons else ""

        return SignalItem(
            id=signal_id,
            symbol=candidate.symbol,
            action=candidate.direction.value,
            entry=candidate.entryPrice,
            takeProfit=candidate.takeProfit,
            stopLoss=candidate.stopLoss,
            confidence=candidate.confidence,
            timeframe=strategy.bestTimeframe if strategy else "",
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
