"""SQLAlchemy models backing the Falcon mission repository."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, Index, Text
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


class TradeJournalRecord(Base):
    __tablename__ = "trade_journal"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    signal_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit: Mapped[float] = mapped_column(Float, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    market_session: Mapped[str] = mapped_column(String(32), nullable=False)
    trade_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    profit_loss: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_reward: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason_for_entry: Mapped[str] = mapped_column(Text, nullable=False)
    reason_for_exit: Mapped[str | None] = mapped_column(Text, nullable=True)
    lesson_learned: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("ix_trade_journal_trade_date", TradeJournalRecord.trade_date)


class RepositoryMetaRecord(Base):
    __tablename__ = "repository_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_mission_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
