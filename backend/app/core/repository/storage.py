"""Storage backends for the mission repository.

Two interchangeable backends are provided:

* ``InMemoryMissionStorage`` — process-local storage, used when no
  ``DATABASE_URL`` is configured.
* ``DatabaseMissionStorage`` — Postgres (Supabase) storage. Artifacts are
  persisted as JSON documents so the pydantic schemas remain the single
  source of truth.
"""

import copy
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy import cast, delete, func, select, text
from sqlalchemy.dialects.postgresql import BIGINT

from app.core.database.models import (
    MissionArtifactRecord,
    MissionRecord,
    RepositoryMetaRecord,
)
from app.core.database.session import get_session
from app.schemas.decision_artifact import DecisionArtifact
from app.schemas.execution_readiness import ExecutionReadiness
from app.schemas.market_state import MarketState
from app.schemas.mission_report import MissionReport
from app.schemas.risk_assessment import RiskAssessment
from app.schemas.signal_candidate import SignalCandidate
from app.schemas.validation_result import ValidationResult

TModel = TypeVar("TModel", bound=BaseModel)

MARKET_STATE = "MARKET_STATE"
CANDIDATE = "CANDIDATE"
VALIDATION = "VALIDATION"
RISK_ASSESSMENT = "RISK_ASSESSMENT"
EXECUTION_READINESS = "EXECUTION_READINESS"
DECISION = "DECISION"

ARTIFACT_MODELS: Dict[str, Type[BaseModel]] = {
    MARKET_STATE: MarketState,
    CANDIDATE: SignalCandidate,
    VALIDATION: ValidationResult,
    RISK_ASSESSMENT: RiskAssessment,
    EXECUTION_READINESS: ExecutionReadiness,
    DECISION: DecisionArtifact,
}

META_ROW_ID = 1
MISSION_NUMBER_SEQUENCE = "mission_number_seq"


class InMemoryMissionStorage:
    """Process-local storage. Data is lost when the process restarts."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._number_lock = threading.Lock()
        self._mission_number = 0
        self._started_at: datetime = datetime.now(timezone.utc)
        self._last_mission_at: Optional[datetime] = None
        self._missions: Dict[str, MissionReport] = {}
        self._artifacts: Dict[str, Dict[str, List[BaseModel]]] = {}

    @property
    def started_at(self) -> datetime:
        return self._started_at

    @property
    def last_mission_at(self) -> Optional[datetime]:
        return self._last_mission_at

    def save_mission(self, mission: MissionReport) -> None:
        self._missions[mission.id] = copy.deepcopy(mission)
        self._last_mission_at = datetime.now(timezone.utc)

    def save_artifacts(
        self, mission_id: str, artifact_type: str, artifacts: Sequence[BaseModel]
    ) -> None:
        self._artifacts.setdefault(mission_id, {})[artifact_type] = [
            copy.deepcopy(artifact) for artifact in artifacts
        ]

    def get_mission(self, mission_id: str) -> Optional[MissionReport]:
        mission = self._missions.get(mission_id)
        return copy.deepcopy(mission) if mission else None

    def get_all_missions(self) -> List[MissionReport]:
        return [copy.deepcopy(mission) for mission in self._missions.values()]

    def get_latest_mission(self) -> Optional[MissionReport]:
        if not self._missions:
            return None
        return copy.deepcopy(next(reversed(self._missions.values())))

    def get_artifacts(self, mission_id: str, artifact_type: str) -> List[BaseModel]:
        stored = self._artifacts.get(mission_id, {}).get(artifact_type, [])
        return [copy.deepcopy(artifact) for artifact in stored]

    def count_missions(self) -> int:
        return len(self._missions)

    def next_mission_number(self) -> int:
        with self._number_lock:
            self._mission_number = max(self._mission_number, len(self._missions)) + 1
            return self._mission_number

    def count_artifacts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {artifact_type: 0 for artifact_type in ARTIFACT_MODELS}
        for by_type in self._artifacts.values():
            for artifact_type, artifacts in by_type.items():
                counts[artifact_type] = counts.get(artifact_type, 0) + len(artifacts)
        return counts

    def clear(self) -> None:
        self.reset()


class DatabaseMissionStorage:
    """Postgres-backed storage used when ``DATABASE_URL`` is configured."""

    def save_mission(self, mission: MissionReport) -> None:
        now = datetime.now(timezone.utc)
        payload = _dump(mission)
        with get_session() as session, session.begin():
            record = session.get(MissionRecord, mission.id)
            if record is None:
                session.add(
                    MissionRecord(
                        id=mission.id,
                        status=_mission_status(mission),
                        stored_at=now,
                        payload=payload,
                    )
                )
            else:
                record.status = _mission_status(mission)
                record.stored_at = now
                record.payload = payload
            meta = _get_or_create_meta(session, now)
            meta.last_mission_at = now

    def save_artifacts(
        self, mission_id: str, artifact_type: str, artifacts: Sequence[BaseModel]
    ) -> None:
        now = datetime.now(timezone.utc)
        with get_session() as session, session.begin():
            session.execute(
                delete(MissionArtifactRecord).where(
                    MissionArtifactRecord.mission_id == mission_id,
                    MissionArtifactRecord.artifact_type == artifact_type,
                )
            )
            session.add_all(
                [
                    MissionArtifactRecord(
                        mission_id=mission_id,
                        artifact_type=artifact_type,
                        position=position,
                        stored_at=now,
                        payload=_dump(artifact),
                    )
                    for position, artifact in enumerate(artifacts)
                ]
            )

    def get_mission(self, mission_id: str) -> Optional[MissionReport]:
        with get_session() as session:
            record = session.get(MissionRecord, mission_id)
            return MissionReport.model_validate(record.payload) if record else None

    def get_all_missions(self) -> List[MissionReport]:
        with get_session() as session:
            records = session.scalars(
                select(MissionRecord).order_by(MissionRecord.stored_at)
            ).all()
            return [MissionReport.model_validate(record.payload) for record in records]

    def get_latest_mission(self) -> Optional[MissionReport]:
        with get_session() as session:
            record = session.scalars(
                select(MissionRecord).order_by(MissionRecord.stored_at.desc()).limit(1)
            ).first()
            return MissionReport.model_validate(record.payload) if record else None

    def get_artifacts(self, mission_id: str, artifact_type: str) -> List[BaseModel]:
        model = ARTIFACT_MODELS[artifact_type]
        with get_session() as session:
            records = session.scalars(
                select(MissionArtifactRecord)
                .where(
                    MissionArtifactRecord.mission_id == mission_id,
                    MissionArtifactRecord.artifact_type == artifact_type,
                )
                .order_by(MissionArtifactRecord.position)
            ).all()
            return [model.model_validate(record.payload) for record in records]

    def count_missions(self) -> int:
        with get_session() as session:
            return int(session.scalar(select(func.count()).select_from(MissionRecord)) or 0)

    def next_mission_number(self) -> int:
        """Allocates a mission number atomically so concurrent runs stay unique."""
        with get_session() as session, session.begin():
            _ensure_mission_sequence(session)
            return int(
                session.scalar(text(f"SELECT nextval('{MISSION_NUMBER_SEQUENCE}')"))
            )

    def count_artifacts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {artifact_type: 0 for artifact_type in ARTIFACT_MODELS}
        with get_session() as session:
            rows = session.execute(
                select(
                    MissionArtifactRecord.artifact_type,
                    func.count(MissionArtifactRecord.id),
                ).group_by(MissionArtifactRecord.artifact_type)
            ).all()
        for artifact_type, count in rows:
            counts[artifact_type] = int(count)
        return counts

    @property
    def started_at(self) -> datetime:
        return self._meta()[0]

    @property
    def last_mission_at(self) -> Optional[datetime]:
        return self._meta()[1]

    def clear(self) -> None:
        with get_session() as session, session.begin():
            session.execute(delete(MissionArtifactRecord))
            session.execute(delete(MissionRecord))
            meta = _get_or_create_meta(session, datetime.now(timezone.utc))
            meta.last_mission_at = None
            _ensure_mission_sequence(session)
            session.execute(
                text(f"SELECT setval('{MISSION_NUMBER_SEQUENCE}', 1, false)")
            )

    def _meta(self) -> tuple[datetime, Optional[datetime]]:
        with get_session() as session, session.begin():
            meta = _get_or_create_meta(session, datetime.now(timezone.utc))
            return meta.started_at, meta.last_mission_at


def _ensure_mission_sequence(session: Any) -> None:
    """Creates the mission number sequence for databases predating migration 0002."""
    session.execute(
        text(f"CREATE SEQUENCE IF NOT EXISTS {MISSION_NUMBER_SEQUENCE} AS BIGINT START 1")
    )
    highest = session.scalar(
        select(
            func.max(
                cast(func.substring(MissionRecord.id, "mission-([0-9]+)$"), BIGINT)
            )
        ).where(MissionRecord.id.op("~")("^mission-[0-9]+$"))
    )
    current = session.scalar(
        text(f"SELECT last_value, is_called FROM {MISSION_NUMBER_SEQUENCE}")
    )
    if highest is not None and int(highest) >= int(current or 0):
        session.execute(
            text(f"SELECT setval('{MISSION_NUMBER_SEQUENCE}', :value, true)"),
            {"value": int(highest)},
        )


def _get_or_create_meta(session: Any, now: datetime) -> RepositoryMetaRecord:
    meta = session.get(RepositoryMetaRecord, META_ROW_ID)
    if meta is None:
        meta = RepositoryMetaRecord(id=META_ROW_ID, started_at=now, last_mission_at=None)
        session.add(meta)
        session.flush()
    return meta


def _mission_status(mission: MissionReport) -> Optional[str]:
    status = getattr(mission, "status", None)
    return getattr(status, "value", status)


def _dump(model: BaseModel) -> Dict[str, Any]:
    return model.model_dump(mode="json")
