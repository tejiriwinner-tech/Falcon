import copy
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from app.schemas.mission_report import MissionReport
from app.schemas.market_state import MarketState
from app.schemas.signal_candidate import SignalCandidate
from app.schemas.validation_result import ValidationResult
from app.schemas.risk_assessment import RiskAssessment
from app.schemas.execution_readiness import ExecutionReadiness
from app.schemas.decision_artifact import DecisionArtifact
from app.schemas.repository_statistics import RepositoryStatistics


class MissionRepository:
    """Singleton MissionRepository for persistent long-term memory.

    Rules:
      - Read-only after a mission completes.
      - Never modify stored objects.
      - Always deep-copy before storage.
    """

    _instance: Optional["MissionRepository"] = None

    def __new__(cls) -> "MissionRepository":
        if cls._instance is None:
            cls._instance = super(MissionRepository, cls).__new__(cls)
            cls._instance._init_storage()
        return cls._instance

    def _init_storage(self) -> None:
        self.started_at: datetime = datetime.now(timezone.utc)
        self.last_mission_at: Optional[datetime] = None

        self._missions: Dict[str, MissionReport] = {}
        self._market_states: Dict[str, MarketState] = {}
        self._candidates: Dict[str, List[SignalCandidate]] = {}
        self._validations: Dict[str, List[ValidationResult]] = {}
        self._risk_assessments: Dict[str, List[RiskAssessment]] = {}
        self._execution_readiness: Dict[str, List[ExecutionReadiness]] = {}
        self._decisions: Dict[str, List[DecisionArtifact]] = {}

    def save_mission(self, mission: MissionReport) -> None:
        mission_copy = copy.deepcopy(mission)
        self._missions[mission_copy.id] = mission_copy
        self.last_mission_at = datetime.now(timezone.utc)

    def get_mission(self, mission_id: str) -> Optional[MissionReport]:
        mission = self._missions.get(mission_id)
        return copy.deepcopy(mission) if mission else None

    def get_all_missions(self) -> List[MissionReport]:
        return [copy.deepcopy(m) for m in self._missions.values()]

    def save_market_state(self, mission_id: str, market_state: MarketState) -> None:
        self._market_states[mission_id] = copy.deepcopy(market_state)

    def save_candidates(self, mission_id: str, candidates: List[SignalCandidate]) -> None:
        self._candidates[mission_id] = copy.deepcopy(candidates)

    def save_validations(self, mission_id: str, validations: List[ValidationResult]) -> None:
        self._validations[mission_id] = copy.deepcopy(validations)

    def save_risk_assessments(self, mission_id: str, assessments: List[RiskAssessment]) -> None:
        self._risk_assessments[mission_id] = copy.deepcopy(assessments)

    def save_execution_readiness(self, mission_id: str, readiness_items: List[ExecutionReadiness]) -> None:
        self._execution_readiness[mission_id] = copy.deepcopy(readiness_items)

    def save_decisions(self, mission_id: str, decisions: List[DecisionArtifact]) -> None:
        self._decisions[mission_id] = copy.deepcopy(decisions)

    def get_mission_artifacts(self, mission_id: str) -> Dict[str, Any]:
        """Returns all immutable artifacts associated with a mission."""
        return {
            "missionId": mission_id,
            "marketState": copy.deepcopy(self._market_states.get(mission_id)),
            "candidates": copy.deepcopy(self._candidates.get(mission_id, [])),
            "validations": copy.deepcopy(self._validations.get(mission_id, [])),
            "riskAssessments": copy.deepcopy(self._risk_assessments.get(mission_id, [])),
            "executionReadiness": copy.deepcopy(self._execution_readiness.get(mission_id, [])),
            "decisions": copy.deepcopy(self._decisions.get(mission_id, [])),
        }

    def get_statistics(self) -> RepositoryStatistics:
        total_market_states = len(self._market_states)
        total_candidates = sum(len(c) for c in self._candidates.values())
        total_validations = sum(len(v) for v in self._validations.values())
        total_risk_assessments = sum(len(r) for r in self._risk_assessments.values())
        total_execution_readiness = sum(len(e) for e in self._execution_readiness.values())
        total_decisions = sum(len(d) for d in self._decisions.values())

        # Health is 100% if operational
        repository_health = 100.0

        return RepositoryStatistics(
            totalMissions=len(self._missions),
            totalMarketStates=total_market_states,
            totalCandidates=total_candidates,
            totalValidations=total_validations,
            totalRiskAssessments=total_risk_assessments,
            totalExecutionReadiness=total_execution_readiness,
            totalDecisions=total_decisions,
            repositoryHealth=repository_health,
            startedAt=self.started_at,
            lastMissionAt=self.last_mission_at,
        )

    def clear_repository(self) -> None:
        """Clear all stored data (for testing purposes only)."""
        self._init_storage()


# Export singleton instance
mission_repository = MissionRepository()
