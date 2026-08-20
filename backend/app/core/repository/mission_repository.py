from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from app.core.database.session import database_enabled
from app.core.repository.storage import (
    CANDIDATE,
    DECISION,
    EXECUTION_READINESS,
    MARKET_STATE,
    RISK_ASSESSMENT,
    VALIDATION,
    DatabaseMissionStorage,
    InMemoryMissionStorage,
)
from app.schemas.decision_artifact import DecisionArtifact
from app.schemas.execution_readiness import ExecutionReadiness
from app.schemas.market_state import MarketState
from app.schemas.mission_report import MissionReport
from app.schemas.repository_statistics import RepositoryStatistics
from app.schemas.risk_assessment import RiskAssessment
from app.schemas.signal_candidate import SignalCandidate
from app.schemas.validation_result import ValidationResult

Storage = Union[InMemoryMissionStorage, DatabaseMissionStorage]


class MissionRepository:
    """Singleton MissionRepository for persistent long-term memory.

    Rules:
      - Read-only after a mission completes.
      - Never modify stored objects.
      - Always copy before storage.

    Artifacts are persisted in Postgres when ``DATABASE_URL`` is configured,
    and kept in process memory otherwise.
    """

    _instance: Optional["MissionRepository"] = None

    def __new__(cls) -> "MissionRepository":
        if cls._instance is None:
            cls._instance = super(MissionRepository, cls).__new__(cls)
            cls._instance._init_storage()
        return cls._instance

    def _init_storage(self) -> None:
        self._storage: Storage = (
            DatabaseMissionStorage() if database_enabled() else InMemoryMissionStorage()
        )

    @property
    def persistent(self) -> bool:
        return isinstance(self._storage, DatabaseMissionStorage)

    @property
    def started_at(self) -> datetime:
        return self._storage.started_at

    @property
    def last_mission_at(self) -> Optional[datetime]:
        return self._storage.last_mission_at

    def save_mission(self, mission: MissionReport) -> None:
        self._storage.save_mission(mission)

    def get_mission(self, mission_id: str) -> Optional[MissionReport]:
        return self._storage.get_mission(mission_id)

    def get_all_missions(self) -> List[MissionReport]:
        return self._storage.get_all_missions()

    def get_latest_mission(self) -> Optional[MissionReport]:
        return self._storage.get_latest_mission()

    def count_missions(self) -> int:
        return self._storage.count_missions()

    def next_mission_number(self) -> int:
        """Atomically allocates the next mission number."""
        return self._storage.next_mission_number()

    def save_market_state(self, mission_id: str, market_state: MarketState) -> None:
        self._storage.save_artifacts(mission_id, MARKET_STATE, [market_state])

    def save_candidates(self, mission_id: str, candidates: List[SignalCandidate]) -> None:
        self._storage.save_artifacts(mission_id, CANDIDATE, candidates)

    def save_validations(self, mission_id: str, validations: List[ValidationResult]) -> None:
        self._storage.save_artifacts(mission_id, VALIDATION, validations)

    def save_risk_assessments(self, mission_id: str, assessments: List[RiskAssessment]) -> None:
        self._storage.save_artifacts(mission_id, RISK_ASSESSMENT, assessments)

    def save_execution_readiness(
        self, mission_id: str, readiness_items: List[ExecutionReadiness]
    ) -> None:
        self._storage.save_artifacts(mission_id, EXECUTION_READINESS, readiness_items)

    def save_decisions(self, mission_id: str, decisions: List[DecisionArtifact]) -> None:
        self._storage.save_artifacts(mission_id, DECISION, decisions)

    def get_mission_artifacts(self, mission_id: str) -> Dict[str, Any]:
        """Returns all immutable artifacts associated with a mission."""
        market_states = self._storage.get_artifacts(mission_id, MARKET_STATE)
        return {
            "missionId": mission_id,
            "marketState": market_states[0] if market_states else None,
            "candidates": self._storage.get_artifacts(mission_id, CANDIDATE),
            "validations": self._storage.get_artifacts(mission_id, VALIDATION),
            "riskAssessments": self._storage.get_artifacts(mission_id, RISK_ASSESSMENT),
            "executionReadiness": self._storage.get_artifacts(mission_id, EXECUTION_READINESS),
            "decisions": self._storage.get_artifacts(mission_id, DECISION),
        }

    def get_statistics(self) -> RepositoryStatistics:
        counts = self._storage.count_artifacts()

        return RepositoryStatistics(
            totalMissions=self._storage.count_missions(),
            totalMarketStates=counts.get(MARKET_STATE, 0),
            totalCandidates=counts.get(CANDIDATE, 0),
            totalValidations=counts.get(VALIDATION, 0),
            totalRiskAssessments=counts.get(RISK_ASSESSMENT, 0),
            totalExecutionReadiness=counts.get(EXECUTION_READINESS, 0),
            totalDecisions=counts.get(DECISION, 0),
            repositoryHealth=100.0,
            startedAt=self.started_at,
            lastMissionAt=self.last_mission_at,
        )

    def clear_repository(self) -> None:
        """Clear all stored data (for testing purposes only)."""
        self._storage.clear()


# Export singleton instance
mission_repository = MissionRepository()
