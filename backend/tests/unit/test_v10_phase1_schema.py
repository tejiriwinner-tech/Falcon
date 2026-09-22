"""
Unit test suite for Falcon V10 Phase 1: Performance Journal Schema Preparation.

Verifies:
1. Backward compatibility: Records with None for all 12 V10 fields load cleanly.
2. V10 persistence: All 12 fields can be populated, saved, and read back.
3. Pydantic schemas: Legacy payloads, full V10 payloads, and partial updates validate.
4. Repository mappings: Both InMemoryTradeJournalStorage and DatabaseTradeJournalStorage
   correctly handle create, read, and partial update operations for V10 fields.
5. Migration integrity: Upgrade/downgrade verification on an isolated test database.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from alembic.config import Config
from alembic import command

from app.core.database.models import Base, TradeJournalRecord
from app.core.repository.trade_journal_repository import (
    InMemoryTradeJournalStorage,
    DatabaseTradeJournalStorage,
    _COLUMNS,
    _to_item,
)
from app.schemas.trade_journal import (
    TradeJournalCreate,
    TradeJournalItem,
    TradeJournalUpdate,
)


V10_FIELDS = [
    "fillTime",
    "fillPrice",
    "realizedRMultiple",
    "peakPrice",
    "troughPrice",
    "mfeR",
    "maeR",
    "strategyVersion",
    "adaptiveRuleVersion",
    "adaptiveStopMultiplier",
    "spreadAtEntry",
    "atrAtEntry",
]

V10_COLUMNS = [
    "fill_time",
    "fill_price",
    "realized_r_multiple",
    "peak_price",
    "trough_price",
    "mfe_r",
    "mae_r",
    "strategy_version",
    "adaptive_rule_version",
    "adaptive_stop_multiplier",
    "spread_at_entry",
    "atr_at_entry",
]


# ==============================================================================
# A. Backward Compatibility
# ==============================================================================

def test_backward_compatibility_null_v10_fields():
    """Verify a TradeJournalRecord with all 12 V10 fields as None converts to TradeJournalItem."""
    now = datetime.now(timezone.utc)
    rec = TradeJournalRecord(
        id=1001,
        signal_id=501,
        strategy_id="strat-001",
        symbol="EUR/USD",
        direction="BUY",
        entry_price=1.1500,
        exit_price=1.1550,
        stop_loss=1.1480,
        take_profit=1.1550,
        timeframe="M15",
        market_session="London",
        trade_date=now,
        close_date=now,
        status="CLOSED",
        result="WIN",
        profit_loss=50.0,
        risk_reward=2.5,
        confidence=85,
        reason_for_entry="Legacy entry",
        reason_for_exit="TP hit",
        lesson_learned="Good execution",
        notes="Legacy note",
        created_at=now,
        updated_at=now,
        # All V10 columns remain unset / None
    )

    item = _to_item(rec)
    assert item.id == 1001
    assert item.symbol == "EUR/USD"
    for field in V10_FIELDS:
        assert getattr(item, field) is None, f"Expected {field} to be None"


# ==============================================================================
# B. V10 Persistence on SQLAlchemy Model
# ==============================================================================

def test_v10_fields_sqlalchemy_persistence():
    """Verify all 12 V10 fields persist and read back from an isolated SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        rec = TradeJournalRecord(
            id=1002,
            signal_id=502,
            strategy_id="strat-002",
            symbol="XAU/USD",
            direction="SELL",
            entry_price=4350.0,
            exit_price=4330.0,
            stop_loss=4360.0,
            take_profit=4330.0,
            timeframe="H1",
            market_session="New York",
            trade_date=now,
            close_date=now,
            status="CLOSED",
            result="WIN",
            profit_loss=200.0,
            risk_reward=2.0,
            confidence=90,
            reason_for_entry="V10 entry",
            reason_for_exit="TP hit",
            lesson_learned="Patience rewarded",
            notes="V10 populated",
            created_at=now,
            updated_at=now,
            # Populate all 12 V10 fields
            fill_time=now,
            fill_price=4350.25,
            realized_r_multiple=2.0,
            peak_price=4355.0,
            trough_price=4328.0,
            mfe_r=2.2,
            mae_r=0.5,
            strategy_version="2.3",
            adaptive_rule_version="1.0.0",
            adaptive_stop_multiplier=1.35,
            spread_at_entry=0.35,
            atr_at_entry=12.5,
        )
        session.add(rec)
        session.commit()

    with SessionLocal() as session:
        loaded = session.get(TradeJournalRecord, 1002)
        assert loaded is not None
        # SQLite stores datetimes without timezone; compare timestamps or attach UTC
        loaded_fill = loaded.fill_time if loaded.fill_time.tzinfo else loaded.fill_time.replace(tzinfo=timezone.utc)
        assert loaded_fill == now
        assert loaded.fill_price == 4350.25
        assert loaded.realized_r_multiple == 2.0
        assert loaded.peak_price == 4355.0
        assert loaded.trough_price == 4328.0
        assert loaded.mfe_r == 2.2
        assert loaded.mae_r == 0.5
        assert loaded.strategy_version == "2.3"
        assert loaded.adaptive_rule_version == "1.0.0"
        assert loaded.adaptive_stop_multiplier == 1.35
        assert loaded.spread_at_entry == 0.35
        assert loaded.atr_at_entry == 12.5

        item = _to_item(loaded)
        item_fill = item.fillTime if item.fillTime.tzinfo else item.fillTime.replace(tzinfo=timezone.utc)
        assert item_fill == now
        assert item.fillPrice == 4350.25
        assert item.realizedRMultiple == 2.0
        assert item.peakPrice == 4355.0
        assert item.troughPrice == 4328.0
        assert item.mfeR == 2.2
        assert item.maeR == 0.5
        assert item.strategyVersion == "2.3"
        assert item.adaptiveRuleVersion == "1.0.0"
        assert item.adaptiveStopMultiplier == 1.35
        assert item.spreadAtEntry == 0.35
        assert item.atrAtEntry == 12.5


# ==============================================================================
# C. Pydantic Schemas Validation
# ==============================================================================

def test_pydantic_legacy_payload_validates():
    """Verify legacy TradeJournalCreate payload without V10 fields validates."""
    now = datetime.now(timezone.utc)
    payload = TradeJournalCreate(
        symbol="EUR/USD",
        direction="BUY",
        entryPrice=1.1500,
        stopLoss=1.1480,
        takeProfit=1.1550,
        timeframe="M15",
        marketSession="London",
        tradeDate=now,
        reasonForEntry="Legacy signal",
    )
    assert payload.symbol == "EUR/USD"
    for field in V10_FIELDS:
        assert getattr(payload, field) is None


def test_pydantic_full_v10_payload_validates():
    """Verify full TradeJournalCreate payload with all 12 V10 fields validates."""
    now = datetime.now(timezone.utc)
    payload = TradeJournalCreate(
        symbol="GBP/USD",
        direction="SELL",
        entryPrice=1.3350,
        stopLoss=1.3380,
        takeProfit=1.3290,
        timeframe="M15",
        marketSession="London",
        tradeDate=now,
        reasonForEntry="Full V10 signal",
        fillTime=now,
        fillPrice=1.3349,
        realizedRMultiple=2.0,
        peakPrice=1.3360,
        troughPrice=1.3285,
        mfeR=2.17,
        maeR=0.33,
        strategyVersion="2.3",
        adaptiveRuleVersion="1.0.0",
        adaptiveStopMultiplier=1.15,
        spreadAtEntry=0.00015,
        atrAtEntry=0.0025,
    )
    assert payload.fillPrice == 1.3349
    assert payload.strategyVersion == "2.3"
    assert payload.atrAtEntry == 0.0025


def test_pydantic_partial_update_validates():
    """Verify TradeJournalUpdate with selected V10 fields validates."""
    now = datetime.now(timezone.utc)
    update = TradeJournalUpdate(
        fillTime=now,
        fillPrice=1.1502,
        realizedRMultiple=1.5,
    )
    dumped = update.model_dump(exclude_unset=True)
    assert dumped["fillPrice"] == 1.1502
    assert dumped["realizedRMultiple"] == 1.5
    assert "strategyVersion" not in dumped


# ==============================================================================
# D. Repository Mappings & Storage
# ==============================================================================

def test_repository_columns_mapping():
    """Verify all 12 V10 fields are present in _COLUMNS mapping."""
    for field, col in zip(V10_FIELDS, V10_COLUMNS):
        assert field in _COLUMNS, f"Missing {field} in _COLUMNS"
        assert _COLUMNS[field] == col, f"Expected _COLUMNS[{field}] == {col}, got {_COLUMNS[field]}"


def test_in_memory_storage_v10_lifecycle():
    """Verify InMemoryTradeJournalStorage handles create, read, and partial update of V10 fields."""
    storage = InMemoryTradeJournalStorage()
    now = datetime.now(timezone.utc)

    # 1. Create with V10 fields
    created = storage.create_trade(
        TradeJournalCreate(
            symbol="EUR/USD",
            direction="BUY",
            entryPrice=1.1500,
            stopLoss=1.1480,
            takeProfit=1.1540,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="InMemory test",
            strategyVersion="2.3",
            adaptiveRuleVersion="1.0.0",
            adaptiveStopMultiplier=1.15,
        )
    )
    assert created.strategyVersion == "2.3"
    assert created.fillTime is None

    # 2. Partial update with fill details
    updated = storage.update_trade(
        created.id,
        TradeJournalUpdate(
            fillTime=now,
            fillPrice=1.1501,
            status="OPEN",
        ),
    )
    assert updated is not None
    assert updated.fillTime == now
    assert updated.fillPrice == 1.1501
    assert updated.strategyVersion == "2.3"  # Preserved

    # 3. Partial update with exit MFE/MAE
    closed = storage.update_trade(
        created.id,
        TradeJournalUpdate(
            status="CLOSED",
            result="WIN",
            exitPrice=1.1540,
            realizedRMultiple=2.0,
            mfeR=2.2,
            maeR=0.2,
        ),
    )
    assert closed is not None
    assert closed.realizedRMultiple == 2.0
    assert closed.mfeR == 2.2
    assert closed.maeR == 0.2
    assert closed.fillPrice == 1.1501  # Preserved


def test_database_storage_v10_lifecycle_isolated():
    """Verify DatabaseTradeJournalStorage on an isolated SQLite engine handles V10 fields."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    from unittest.mock import patch
    from contextlib import contextmanager

    @contextmanager
    def mock_session():
        with SessionLocal() as s:
            yield s

    with patch("app.core.repository.trade_journal_repository.get_session", mock_session):
        storage = DatabaseTradeJournalStorage()
        now = datetime.now(timezone.utc)

        # 1. Create
        created = storage.create_trade(
            TradeJournalCreate(
                symbol="GBP/USD",
                direction="SELL",
                entryPrice=1.3300,
                stopLoss=1.3330,
                takeProfit=1.3240,
                timeframe="H1",
                marketSession="London",
                tradeDate=now,
                reasonForEntry="DB isolated test",
                strategyVersion="2.3",
                adaptiveStopMultiplier=1.20,
            )
        )
        assert created.id is not None
        assert created.strategyVersion == "2.3"
        assert created.adaptiveStopMultiplier == 1.20

        # 2. Read
        fetched = storage.get_trade(created.id)
        assert fetched is not None
        assert fetched.strategyVersion == "2.3"
        assert fetched.fillPrice is None

        # 3. Partial update
        updated = storage.update_trade(
            created.id,
            TradeJournalUpdate(
                fillTime=now,
                fillPrice=1.3299,
                peakPrice=1.3310,
                troughPrice=1.3235,
                realizedRMultiple=2.03,
                mfeR=2.17,
                maeR=0.33,
            ),
        )
        assert updated is not None
        assert updated.fillPrice == 1.3299
        assert updated.mfeR == 2.17
        assert updated.strategyVersion == "2.3"  # Preserved


# ==============================================================================
# E. Migration Upgrade / Downgrade on Isolated Database
# ==============================================================================

def test_migration_0005_isolated_sqlite():
    """Verify migration 0005 upgrade and downgrade on an isolated SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    
    # Create baseline trade_journal table corresponding to migration 0004
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE trade_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id BIGINT,
                strategy_id VARCHAR(64),
                symbol VARCHAR(32) NOT NULL,
                direction VARCHAR(8) NOT NULL,
                entry_price FLOAT NOT NULL,
                exit_price FLOAT,
                stop_loss FLOAT NOT NULL,
                take_profit FLOAT NOT NULL,
                timeframe VARCHAR(16) NOT NULL,
                market_session VARCHAR(32) NOT NULL,
                trade_date TIMESTAMP NOT NULL,
                close_date TIMESTAMP,
                status VARCHAR(16) NOT NULL,
                result VARCHAR(16) NOT NULL,
                profit_loss FLOAT NOT NULL DEFAULT 0.0,
                risk_reward FLOAT NOT NULL DEFAULT 0.0,
                confidence INTEGER NOT NULL DEFAULT 0,
                reason_for_entry TEXT NOT NULL,
                reason_for_exit TEXT,
                lesson_learned TEXT,
                notes TEXT,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """))
        conn.commit()

    # Verify baseline columns (24 columns)
    insp = inspect(engine)
    baseline_cols = {c["name"] for c in insp.get_columns("trade_journal")}
    for col in V10_COLUMNS:
        assert col not in baseline_cols, f"Column {col} should not exist before migration 0005"

    # Simulate 0005 upgrade via raw DDL (matching migration upgrade())
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE trade_journal ADD COLUMN fill_time TIMESTAMP"))
        conn.execute(text("ALTER TABLE trade_journal ADD COLUMN fill_price FLOAT"))
        conn.execute(text("ALTER TABLE trade_journal ADD COLUMN realized_r_multiple FLOAT"))
        conn.execute(text("ALTER TABLE trade_journal ADD COLUMN peak_price FLOAT"))
        conn.execute(text("ALTER TABLE trade_journal ADD COLUMN trough_price FLOAT"))
        conn.execute(text("ALTER TABLE trade_journal ADD COLUMN mfe_r FLOAT"))
        conn.execute(text("ALTER TABLE trade_journal ADD COLUMN mae_r FLOAT"))
        conn.execute(text("ALTER TABLE trade_journal ADD COLUMN strategy_version VARCHAR(16)"))
        conn.execute(text("ALTER TABLE trade_journal ADD COLUMN adaptive_rule_version VARCHAR(16)"))
        conn.execute(text("ALTER TABLE trade_journal ADD COLUMN adaptive_stop_multiplier FLOAT"))
        conn.execute(text("ALTER TABLE trade_journal ADD COLUMN spread_at_entry FLOAT"))
        conn.execute(text("ALTER TABLE trade_journal ADD COLUMN atr_at_entry FLOAT"))
        conn.commit()

    insp = inspect(engine)
    upgraded_cols = {c["name"] for c in insp.get_columns("trade_journal")}
    for col in V10_COLUMNS:
        assert col in upgraded_cols, f"Column {col} missing after simulated upgrade"

    # Simulate 0005 downgrade via raw DDL
    with engine.connect() as conn:
        for col in reversed(V10_COLUMNS):
            conn.execute(text(f"ALTER TABLE trade_journal DROP COLUMN {col}"))
        conn.commit()

    insp = inspect(engine)
    downgraded_cols = {c["name"] for c in insp.get_columns("trade_journal")}
    for col in V10_COLUMNS:
        assert col not in downgraded_cols, f"Column {col} should be dropped after downgrade"


def test_alembic_programmatic_migration_isolated_db():
    """Verify Alembic upgrade/downgrade/upgrade cycle using actual Alembic command runner on isolated DB."""
    with NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    old_db_url = os.environ.get("DATABASE_URL")
    try:
        sqlite_url = f"sqlite:///{db_path}"
        os.environ["DATABASE_URL"] = sqlite_url

        backend_dir = Path(__file__).resolve().parents[2]
        alembic_ini_path = str(backend_dir / "alembic.ini")
        cfg = Config(alembic_ini_path)
        cfg.set_main_option("sqlalchemy.url", sqlite_url)

        # Baseline: initialize table and alembic_version at 0004
        engine = create_engine(sqlite_url)
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE trade_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id BIGINT,
                    strategy_id VARCHAR(64),
                    symbol VARCHAR(32) NOT NULL,
                    direction VARCHAR(8) NOT NULL,
                    entry_price FLOAT NOT NULL,
                    exit_price FLOAT,
                    stop_loss FLOAT NOT NULL,
                    take_profit FLOAT NOT NULL,
                    timeframe VARCHAR(16) NOT NULL,
                    market_session VARCHAR(32) NOT NULL,
                    trade_date TIMESTAMP NOT NULL,
                    close_date TIMESTAMP,
                    status VARCHAR(16) NOT NULL,
                    result VARCHAR(16) NOT NULL,
                    profit_loss FLOAT NOT NULL DEFAULT 0.0,
                    risk_reward FLOAT NOT NULL DEFAULT 0.0,
                    confidence INTEGER NOT NULL DEFAULT 0,
                    reason_for_entry TEXT NOT NULL,
                    reason_for_exit TEXT,
                    lesson_learned TEXT,
                    notes TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """))
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"))
            conn.execute(text("INSERT INTO alembic_version VALUES ('0004_journal_strategy')"))
            conn.commit()

        # Upgrade to 0005_v10_performance_journal
        command.upgrade(cfg, "0005_v10_performance_journal")
        insp = inspect(engine)
        cols_0005 = {c["name"] for c in insp.get_columns("trade_journal")}
        for c in V10_COLUMNS:
            assert c in cols_0005, f"Column {c} missing after Alembic upgrade"

        with engine.connect() as conn:
            ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert ver == "0005_v10_performance_journal"

        # Downgrade back to 0004_journal_strategy
        command.downgrade(cfg, "0004_journal_strategy")
        insp = inspect(engine)
        cols_downgraded = {c["name"] for c in insp.get_columns("trade_journal")}
        for c in V10_COLUMNS:
            assert c not in cols_downgraded, f"Column {c} still present after downgrade"

        with engine.connect() as conn:
            ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert ver == "0004_journal_strategy"

        # Re-upgrade to 0005_v10_performance_journal
        command.upgrade(cfg, "0005_v10_performance_journal")
        insp = inspect(engine)
        cols_reupgraded = {c["name"] for c in insp.get_columns("trade_journal")}
        for c in V10_COLUMNS:
            assert c in cols_reupgraded, f"Column {c} missing after re-upgrade"

    finally:
        if old_db_url is not None:
            os.environ["DATABASE_URL"] = old_db_url
        else:
            os.environ.pop("DATABASE_URL", None)
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass
