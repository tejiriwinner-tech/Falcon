"""SQLAlchemy models backing the Falcon mission repository."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


JSONType = JSONB().with_variant(JSON(), "sqlite")


class MissionRecord(Base):
    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONType, nullable=False)


class MissionArtifactRecord(Base):
    __tablename__ = "mission_artifacts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONType, nullable=False)


Index(
    "ix_mission_artifacts_mission_id_type",
    MissionArtifactRecord.mission_id,
    MissionArtifactRecord.artifact_type,
)


class RepositoryMetaRecord(Base):
    __tablename__ = "repository_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_mission_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
