"""SQLAlchemy models backing the Falcon mission repository."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
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

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    signal_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    strategy_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
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

    # Execution (V10)
    fill_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Realized performance (V10)
    realized_r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)

    # MFE / MAE tracking (V10)
    peak_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    trough_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    mfe_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae_r: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Strategy versioning (V10)
    strategy_version: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Adaptive-rule versioning (V10)
    adaptive_rule_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    adaptive_stop_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Market conditions at entry (V10)
    spread_at_entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr_at_entry: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Authoritative initial risk established at entry (V10 Phase 5A.1)
    initial_stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    initial_monetary_risk: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)


Index("ix_trade_journal_trade_date", TradeJournalRecord.trade_date)


class RepositoryMetaRecord(Base):
    __tablename__ = "repository_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_mission_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PriceBarRecord(Base):
    __tablename__ = "price_history"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "timeframe",
            "bar_time",
            name="uq_price_history_symbol_timeframe_bar_time",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("ix_price_history_symbol_timeframe", PriceBarRecord.symbol, PriceBarRecord.timeframe)


class EconomicEventRecord(Base):
    __tablename__ = "economic_events"
    __table_args__ = (
        UniqueConstraint(
            "event_time",
            "currency",
            "title",
            name="uq_economic_events_time_currency_title",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    impact: Mapped[str] = mapped_column(String(16), nullable=False)
    forecast: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actual: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("ix_economic_events_event_time", EconomicEventRecord.event_time)


class CapitalCycleRecord(Base):
    __tablename__ = "capital_cycles"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    cycle_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    cycle_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    starting_capital: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    target_capital: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    active_trading_capital: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    protected_profit: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_capital: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    realized_profit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    next_cycle_allocation: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("ix_capital_cycles_status", CapitalCycleRecord.status)
Index("ix_capital_cycles_cycle_number", CapitalCycleRecord.cycle_number)
Index(
    "uq_capital_cycles_active",
    CapitalCycleRecord.status,
    unique=True,
    postgresql_where=(CapitalCycleRecord.status == "ACTIVE"),
    sqlite_where=(CapitalCycleRecord.status == "ACTIVE"),
)


class SignalSignatureRecord(Base):
    __tablename__ = "signal_signatures"

    signature: Mapped[str] = mapped_column(String(128), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("ix_signal_signatures_symbol", SignalSignatureRecord.symbol)
Index("ix_signal_signatures_status", SignalSignatureRecord.status)


class StrategyStatusRecord(Base):
    __tablename__ = "strategy_status_overrides"

    strategy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

