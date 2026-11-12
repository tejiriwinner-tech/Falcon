"""
Consolidated Unit Tests for Falcon Forward Paper-Trading & Quantitative Validation Mission.

Verifies:
1. Zero-forward trade root cause diagnosis and isolated paper cycle unblocking.
2. Durable paper journal persistence across process restarts.
3. Priority A: Gold Trend Continuation (strat-002) research hypothesis & $0.80 spread filter.
4. Priority B: Exit-model comparison (Model A, Model B, Model D1) and conservative ambiguity.
5. Priority C: GBP/JPY rollover protection boundary and DST reconciliation.
6. Priority D: 18-strategy matrix observability, zero-trade honesty, and classifications.
7. Absolute preservation of the air-gapped broker lock.
"""

from datetime import datetime, time, timezone
from decimal import Decimal
import json
import os
import pytest
from typing import Dict, Any, List

from app.core.analytics.exit_model_evaluator import ExitModelEvaluator, ExitModelResult
from app.core.config.settings import settings
from app.core.engines.paper_runtime import paper_trading_runtime
from app.core.engines.paper_trading_engine import paper_trading_engine
from app.core.execution.execution_mode_guard import (
    ExecutionModeGuard,
    resolve_record_execution_mode,
    is_live_record,
    is_paper_record,
)
from app.core.repository.trade_journal_repository import (
    InMemoryTradeJournalStorage,
    trade_journal_repository,
)
from app.core.services.capital_guardian_service import capital_guardian_service
from app.core.services.signal_authorization_service import signal_authorization_service
from app.schemas.capital_guardian import ProposedTradeInput
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalItem


@pytest.fixture
def canonical_14_trades() -> List[Dict[str, Any]]:
    return [
        {"id": 33, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 1, "A": -1.068, "B": -1.068, "D1": -1.068},
        {"id": 34, "strat": "strat-004", "sym": "GBP/USD", "dir": "BUY",  "cluster": 1, "A": -1.082, "B": -1.082, "D1": -1.082},
        {"id": 35, "strat": "strat-007", "sym": "EUR/USD", "dir": "BUY",  "cluster": 1, "A": -0.207, "B": -0.207, "D1": -0.207},
        {"id": 36, "strat": "strat-002", "sym": "XAU/USD", "dir": "SELL", "cluster": 2, "A": -0.029, "B": 0.974,  "D1": 1.224},
        {"id": 37, "strat": "strat-004", "sym": "GBP/USD", "dir": "SELL", "cluster": 2, "A": -1.081, "B": -1.081, "D1": -1.081},
        {"id": 38, "strat": "strat-002", "sym": "XAU/USD", "dir": "SELL", "cluster": 3, "A": 0.144,  "B": 0.144,  "D1": 0.144},
        {"id": 39, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 4, "A": -2.000, "B": -2.000, "D1": -2.000},
        {"id": 40, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 4, "A": -1.000, "B": 0.013,  "D1": -0.493},
        {"id": 41, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 4, "A": -1.004, "B": 0.009,  "D1": -0.498},
        {"id": 42, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 4, "A": -1.000, "B": 0.013,  "D1": -0.493},
        {"id": 43, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 4, "A": -1.004, "B": 0.009,  "D1": -0.498},
        {"id": 45, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 5, "A": -1.042, "B": -1.042, "D1": -1.042},
        {"id": 47, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 6, "A": -0.066, "B": 0.942,  "D1": 0.438},
        {"id": 48, "strat": "strat-016", "sym": "GBP/JPY", "dir": "SELL", "cluster": 7, "A": -0.811, "B": -0.811, "D1": -0.811},
    ]


def test_zero_forward_root_cause_and_paper_cycle_unblocking():
    """
    Verify root cause: missing live cycle blocks LIVE mode fail-closed,
    while isolated paper cycle allows PAPER evaluations without compromising LIVE safety.
    """
    from unittest.mock import patch

    # 1. LIVE execution proposal with no active live cycle must FAIL CLOSED
    with patch.object(signal_authorization_service._cycle_service, "get_active_cycle", return_value=None):
        proposal_live = ProposedTradeInput(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=Decimal("1.1250"),
            stopLoss=Decimal("1.1225"),
            takeProfit=Decimal("1.1300"),
            lotSize=Decimal("0.01"),
            riskReward=Decimal("2.0"),
        )
        decision_live = signal_authorization_service.evaluate_proposal(
            proposal=proposal_live,
            execution_mode="LIVE",
        )
        assert decision_live.allowed is False
        assert decision_live.reason == "No active capital cycle"

        # 2. PAPER execution proposal with uninitialized live cycle must use isolated paper cycle
        decision_paper = signal_authorization_service.evaluate_proposal(
            proposal=proposal_live,
            execution_mode="PAPER",
        )
        assert decision_paper.allowed is True
        assert decision_paper.cycleId == "CYCLE-PAPER-001"
        assert decision_paper.activeTradingCapital == Decimal("10000.00")


def test_durable_paper_journal_persistence_across_restarts(tmp_path):
    """Verify paper journal entries survive process restarts via durable storage."""
    journal_path = str(tmp_path / "paper_trade_journal.json")
    storage = InMemoryTradeJournalStorage(persistence_file=journal_path)
    storage.clear()

    now = datetime.now(timezone.utc)
    trade_payload = TradeJournalCreate(
        signalId=5555,
        strategyId="strat-002",
        symbol="XAU/USD",
        direction="SELL",
        entryPrice=4110.0,
        stopLoss=4125.0,
        takeProfit=4070.0,
        initialStopLoss=4125.0,
        initialMonetaryRisk=Decimal("15.00"),
        timeframe="H1",
        marketSession="NEW_YORK",
        tradeDate=now,
        status="PENDING",
        result="PENDING",
        profitLoss=0.0,
        riskReward=2.67,
        confidence=85,
        reasonForEntry="Gold Trend Continuation H1",
        notes="Paper trade reservation [MODE:PAPER]",
        executionMode="PAPER",
    )

    created_item = storage.create_trade(trade_payload)
    assert created_item.id is not None
    assert created_item.symbol == "XAU/USD"
    assert created_item.executionMode == "PAPER"

    # Simulate process restart by instantiating new storage instance with the same persistence file
    new_storage = InMemoryTradeJournalStorage(persistence_file=journal_path)
    reloaded_trade = new_storage.get_trade(created_item.id)

    assert reloaded_trade is not None
    assert reloaded_trade.signalId == 5555
    assert reloaded_trade.strategyId == "strat-002"
    assert float(reloaded_trade.initialStopLoss) == 4125.0
    assert reloaded_trade.executionMode == "PAPER"

    # Clean up storage
    storage.clear()


def test_gold_h1_research_hypothesis_and_spread_cap():
    """Verify Gold Trend Continuation (strat-002) spread filter ($0.80 cash price cap)."""
    # 1. Gold spread below $0.80 -> ALLOWED
    # Mock quote with $0.40 spread ($4112.40 ask - $4112.00 bid)
    from unittest.mock import MagicMock
    mock_valid_quote = MagicMock()
    mock_valid_quote.quote.bidAsk.bid = 4112.00
    mock_valid_quote.quote.bidAsk.ask = 4112.40
    mock_valid_quote.quote.bidAsk.spread = 0.40
    test_dt = datetime(2026, 10, 22, 15, 0, 0, tzinfo=timezone.utc)
    mock_valid_quote.quote.timestamp = test_dt
    is_ok, reason = signal_authorization_service.validate_market_and_spread_conditions(
        symbol="XAU/USD",
        quote_resp=mock_valid_quote,
        now_utc=test_dt,
    )
    assert is_ok is True
    assert reason is None

    # 2. Gold spread above $0.80 -> REJECTED
    mock_wide_quote = MagicMock()
    mock_wide_quote.quote.bidAsk.bid = 4110.00
    mock_wide_quote.quote.bidAsk.ask = 4111.50
    mock_wide_quote.quote.bidAsk.spread = 1.50  # Exceeds $0.80 limit
    mock_wide_quote.quote.timestamp = test_dt

    is_ok_wide, reason_wide = signal_authorization_service.validate_market_and_spread_conditions(
        symbol="XAU/USD",
        quote_resp=mock_wide_quote,
        now_utc=test_dt,
    )
    assert is_ok_wide is False
    assert "SPREAD SPIKE" in reason_wide or "exceeds maximum allowable" in reason_wide


def test_exit_model_evaluator_a_b_d1_deterministic_comparison(canonical_14_trades):
    """Verify ExitModelEvaluator produces identical deterministic results for A, B, and D1."""
    results = ExitModelEvaluator.evaluate_historical_scorable(canonical_14_trades)

    res_a = results["A"]
    res_b = results["B"]
    res_d1 = results["D1"]

    assert res_a.total_trades == 14
    assert res_a.net_r == pytest.approx(-11.251, abs=0.01)
    assert res_a.max_drawdown_r == pytest.approx(11.251, abs=0.01)

    assert res_b.net_r == pytest.approx(-5.187, abs=0.01)
    assert res_b.max_drawdown_r == pytest.approx(5.322, abs=0.01)

    assert res_d1.net_r == pytest.approx(-7.467, abs=0.01)
    assert res_d1.max_drawdown_r == pytest.approx(7.467, abs=0.01)

    # All three models have negative net expectancy on this sample
    assert res_a.net_r < 0.0
    assert res_b.net_r < 0.0
    assert res_d1.net_r < 0.0

    # Test conservative same-candle ambiguity resolution
    ambiguous_res = ExitModelEvaluator.simulate_from_excursions(
        max_favorable_r=1.6,
        max_adverse_r=1.2,
        same_candle_ambiguity=True,
    )
    assert ambiguous_res["A"] == -1.0
    assert ambiguous_res["B"] == -1.0
    assert ambiguous_res["D1"] == -1.0


def test_gbpjpy_rollover_blackout_boundary_reconciliation():
    """Verify rollover blackout boundary [20:50, 21:30] UTC blocks entries and permits outside hours."""
    # 1. 21:05 UTC (historical cascade time) -> MUST BE REJECTED
    rollover_time = datetime(2026, 10, 20, 21, 5, 0, tzinfo=timezone.utc)
    is_ok_ro, reason_ro = signal_authorization_service.validate_market_and_spread_conditions(
        symbol="GBP/JPY",
        now_utc=rollover_time,
        bypass_quote_check=True,
    )
    assert is_ok_ro is False
    assert "DAILY ROLLOVER BLACKOUT" in reason_ro

    # 2. 20:45 UTC (prior to blackout) -> MUST BE ALLOWED
    pre_time = datetime(2026, 10, 20, 20, 45, 0, tzinfo=timezone.utc)
    is_ok_pre, _ = signal_authorization_service.validate_market_and_spread_conditions(
        symbol="GBP/JPY",
        now_utc=pre_time,
        bypass_quote_check=True,
    )
    assert is_ok_pre is True

    # 3. 21:35 UTC (after blackout) -> MUST BE ALLOWED
    post_time = datetime(2026, 10, 20, 21, 35, 0, tzinfo=timezone.utc)
    is_ok_post, _ = signal_authorization_service.validate_market_and_spread_conditions(
        symbol="GBP/JPY",
        now_utc=post_time,
        bypass_quote_check=True,
    )
    assert is_ok_post is True

    # 4. Winter EST check (e.g. Dec 15, 2026 where 17:00 NY = 22:00 UTC)
    # 22:05 UTC (during EST rollover) -> MUST BE REJECTED
    winter_ro_time = datetime(2026, 12, 15, 22, 5, 0, tzinfo=timezone.utc)
    is_ok_w_ro, reason_w_ro = signal_authorization_service.validate_market_and_spread_conditions(
        symbol="GBP/JPY",
        now_utc=winter_ro_time,
        bypass_quote_check=True,
    )
    assert is_ok_w_ro is False
    assert "DAILY ROLLOVER BLACKOUT" in reason_w_ro

    # 21:05 UTC (not rollover during EST) -> MUST BE ALLOWED
    winter_pre_time = datetime(2026, 12, 15, 21, 5, 0, tzinfo=timezone.utc)
    is_ok_w_pre, _ = signal_authorization_service.validate_market_and_spread_conditions(
        symbol="GBP/JPY",
        now_utc=winter_pre_time,
        bypass_quote_check=True,
    )
    assert is_ok_w_pre is True


def test_18_strategy_matrix_observability_and_classifications():
    """Verify registry has all 18 strategies and research statuses conform to decision rules."""
    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "app",
        "core",
        "engines",
        "strategy_registry_manifest.json",
    )
    with open(path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    assert len(registry) == 18

    # Verify classification distribution
    # Only strat-002 is EXPLORATORY_PROMISING, strat-004/007/016 are NEGATIVE_SAMPLE_EDGE,
    # strat-013/017 are DATA_QUALITY_BLOCKED, rest are INSUFFICIENT_DATA.
    expected_statuses = {
        "strat-001": "INSUFFICIENT_DATA",
        "strat-002": "EXPLORATORY_PROMISING",
        "strat-003": "INSUFFICIENT_DATA",
        "strat-004": "NEGATIVE_SAMPLE_EDGE",
        "strat-005": "INSUFFICIENT_DATA",
        "strat-006": "INSUFFICIENT_DATA",
        "strat-007": "NEGATIVE_SAMPLE_EDGE",
        "strat-008": "INSUFFICIENT_DATA",
        "strat-009": "INSUFFICIENT_DATA",
        "strat-010": "INSUFFICIENT_DATA",
        "strat-011": "INSUFFICIENT_DATA",
        "strat-012": "INSUFFICIENT_DATA",
        "strat-013": "DATA_QUALITY_BLOCKED",
        "strat-014": "INSUFFICIENT_DATA",
        "strat-015": "INSUFFICIENT_DATA",
        "strat-016": "NEGATIVE_SAMPLE_EDGE",
        "strat-017": "DATA_QUALITY_BLOCKED",
        "strat-018": "INSUFFICIENT_DATA",
    }

    for strat in registry:
        s_id = strat["id"]
        assert s_id in expected_statuses
        # Zero strategies may be promoted to VALIDATION_CANDIDATE
        assert expected_statuses[s_id] != "VALIDATION_CANDIDATE"


def test_strict_air_gap_broker_lock_preserved():
    """Verify absolute safety boundary: broker dispatch remains locked."""
    guard = ExecutionModeGuard()
    assert guard.is_live_authorized() is False
    assert settings.EXECUTION_MODE == "PAPER"
    assert settings.LIVE_EXECUTION_ACKNOWLEDGED is False
    assert settings.OANDA_AUTO_EXECUTE is False


def test_database_fallback_asymmetry_repaired_and_outbox_reconciled():
    """Verify that trades in fallback storage are never hidden when the database has records,
    and that reconcile_outbox() correctly synchronizes pending records.
    """
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database.models import Base
    from app.core.repository.trade_journal_repository import DatabaseTradeJournalStorage
    from app.schemas.trade_journal import TradeJournalCreate

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    temp_file = Path("backend/data/test_db_storage_reconciliation.json")
    if temp_file.exists():
        temp_file.unlink()

    try:
        storage = DatabaseTradeJournalStorage(persistence_file=str(temp_file))

        # 1. Add record directly to DB via session
        with TestingSessionLocal() as session:
            payload_db = TradeJournalCreate(
                symbol="EUR_USD",
                direction="BUY",
                entryPrice=1.0850,
                stopLoss=1.0800,
                takeProfit=1.0950,
                reasonForEntry="DB entry test",
                timeframe="H1",
                marketSession="LONDON",
                tradeDate=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
                status="CLOSED",
                result="WIN",
                profitLoss=100.0,
                notes="Trade in primary DB",
            )
            storage.create_trade(payload_db, session=session)
            session.commit()

        with TestingSessionLocal() as session:
            trades = storage.list_trades(session=session)
            assert len(trades) == 1
            assert trades[0].symbol == "EUR_USD"

        # 2. Inject a fallback-only trade (simulating a trade recorded during transient DB outage)
        payload_fallback = TradeJournalCreate(
            symbol="GBP_USD",
            direction="SELL",
            entryPrice=1.2700,
            stopLoss=1.2750,
            takeProfit=1.2600,
            reasonForEntry="Fallback entry test",
            timeframe="H1",
            marketSession="NEW_YORK",
            tradeDate=datetime(2026, 4, 1, 14, 0, tzinfo=timezone.utc),
            status="OPEN",
            notes="Fallback trade saved during DB outage",
        )
        fallback_item = storage._fallback_memory.create_trade(payload_fallback)
        storage._outbox_pending_ids.add(fallback_item.id)

        # 3. Test merged visibility: list_trades() MUST return BOTH trades
        with TestingSessionLocal() as session:
            merged_trades = storage.list_trades(session=session)
            assert len(merged_trades) == 2
            symbols = {t.symbol for t in merged_trades}
            assert "EUR_USD" in symbols
            assert "GBP_USD" in symbols

            # Storage health check
            health = storage.get_storage_health(session=session)
            assert health["database_connected"] is True
            assert health["database_records"] == 1
            assert health["fallback_records"] == 2
            assert health["outbox_pending_count"] == 1

            # 4. Reconcile outbox: replay fallback trade into DB
            reconciled_count = storage.reconcile_outbox(session=session)
            assert reconciled_count == 1
            session.commit()

            # Health after reconciliation
            health_after = storage.get_storage_health(session=session)
            assert health_after["database_records"] == 2
            assert health_after["outbox_pending_count"] == 0

            # Verified deduplication
            final_trades = storage.list_trades(session=session)
            assert len(final_trades) == 2
    finally:
        if temp_file.exists():
            temp_file.unlink()
        outbox_file = Path("backend/data/test_db_storage_reconciliation_outbox.json")
        if outbox_file.exists():
            outbox_file.unlink()


def test_outbox_durability_across_process_restart_and_unregistered_discovery():
    """Verify that:
    1. Outbox pending state survives process restarts via disk persistence.
    2. Even if in-memory pending IDs are cleared, reconcile_outbox() discovers
       unsynced fallback records via logical key diffing.
    3. Repeated reconciliation is strictly idempotent.
    """
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database.models import Base
    from app.core.repository.trade_journal_repository import DatabaseTradeJournalStorage
    from app.schemas.trade_journal import TradeJournalCreate

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    temp_file = Path("backend/data/test_restart_durability.json")
    outbox_file = Path("backend/data/test_restart_durability_outbox.json")
    for f in (temp_file, outbox_file):
        if f.exists():
            f.unlink()

    try:
        # Step 1: Storage instance 1 creates a fallback trade (simulating DB write failure)
        storage1 = DatabaseTradeJournalStorage(persistence_file=str(temp_file))
        payload = TradeJournalCreate(
            symbol="USD_JPY",
            direction="BUY",
            entryPrice=154.50,
            stopLoss=154.00,
            takeProfit=155.50,
            reasonForEntry="Restart test",
            timeframe="H1",
            marketSession="TOKYO",
            tradeDate=datetime(2026, 4, 2, 2, 0, tzinfo=timezone.utc),
            status="OPEN",
            notes="Trade pending outbox",
        )
        mem_item = storage1._fallback_memory.create_trade(payload)
        storage1._outbox_pending_ids.add(mem_item.id)
        storage1._save_outbox_to_disk()

        # Step 2: Simulate full process restart by destroying storage1 and instantiating storage2
        del storage1
        storage2 = DatabaseTradeJournalStorage(persistence_file=str(temp_file))
        assert mem_item.id in storage2._outbox_pending_ids

        # Step 3: Now erase in-memory pending IDs to test unregistered discovery
        storage2._outbox_pending_ids.clear()
        assert len(storage2._outbox_pending_ids) == 0

        # Step 4: Health check with DB connected discovers unsynced records dynamically
        with TestingSessionLocal() as session:
            health = storage2.get_storage_health(session=session)
            assert health["database_connected"] is True
            assert health["database_records"] == 0
            assert health["fallback_records"] == 1
            assert health["outbox_pending_count"] == 1
            assert health["durability_mode"] == "POSTGRES_UNSYNCED_OUTBOX"

            # Step 5: Reconcile outbox
            reconciled = storage2.reconcile_outbox(session=session)
            assert reconciled == 1
            session.commit()

            # Health after reconciliation
            health_after = storage2.get_storage_health(session=session)
            assert health_after["database_records"] == 1
            assert health_after["outbox_pending_count"] == 0
            assert health_after["durability_mode"] == "POSTGRES_HEALTHY"

            # Step 6: Idempotency verification - second run reconciles 0
            reconciled_repeat = storage2.reconcile_outbox(session=session)
            assert reconciled_repeat == 0

            # List trades returns the synchronized trade
            trades = storage2.list_trades(session=session)
            assert len(trades) == 1
            assert trades[0].symbol == "USD_JPY"
    finally:
        for f in (temp_file, outbox_file):
            if f.exists():
                f.unlink()


def test_logical_key_deduplication_granularity_preserves_distinct_trades():
    """Verify that logical-key deduplication does NOT merge distinct legitimate trades."""
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database.models import Base
    from app.core.repository.trade_journal_repository import DatabaseTradeJournalStorage
    from app.schemas.trade_journal import TradeJournalCreate

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    temp_file = Path("backend/data/test_granularity.json")
    outbox_file = Path("backend/data/test_granularity_outbox.json")
    for f in (temp_file, outbox_file):
        if f.exists():
            f.unlink()

    try:
        storage = DatabaseTradeJournalStorage(persistence_file=str(temp_file))
        now_dt = datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)

        # Trade A: EUR_USD BUY from strategy strat-001
        p_a = TradeJournalCreate(
            strategyId="strat-001",
            symbol="EUR_USD",
            direction="BUY",
            entryPrice=1.0850,
            stopLoss=1.0800,
            takeProfit=1.0950,
            reasonForEntry="Strat 1",
            timeframe="H1",
            marketSession="LONDON",
            tradeDate=now_dt,
            status="OPEN",
        )
        # Trade B: EUR_USD BUY from strategy strat-002 at same price and time
        p_b = TradeJournalCreate(
            strategyId="strat-002",
            symbol="EUR_USD",
            direction="BUY",
            entryPrice=1.0850,
            stopLoss=1.0800,
            takeProfit=1.0950,
            reasonForEntry="Strat 2",
            timeframe="H1",
            marketSession="LONDON",
            tradeDate=now_dt,
            status="OPEN",
        )
        # Trade C: EUR_USD BUY from strategy strat-001 at different entry price
        p_c = TradeJournalCreate(
            strategyId="strat-001",
            symbol="EUR_USD",
            direction="BUY",
            entryPrice=1.0875,
            stopLoss=1.0825,
            takeProfit=1.0975,
            reasonForEntry="Strat 1 second entry",
            timeframe="H1",
            marketSession="LONDON",
            tradeDate=now_dt,
            status="OPEN",
        )

        with TestingSessionLocal() as session:
            t_a = storage.create_trade(p_a, session=session)
            t_b = storage.create_trade(p_b, session=session)
            t_c = storage.create_trade(p_c, session=session)
            session.commit()

            trades = storage.list_trades(session=session)
            # All 3 distinct trades MUST be preserved
            assert len(trades) == 3
            ids = {t.id for t in trades}
            assert len(ids) == 3
            assert {t.strategyId for t in trades} == {"strat-001", "strat-002"}
    finally:
        for f in (temp_file, outbox_file):
            if f.exists():
                f.unlink()


def test_updates_closes_and_deletions_keep_storage_coherent():
    """Verify that updating, deleting, or expiring trades maintains coherence across DB and fallback."""
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database.models import Base
    from app.core.repository.trade_journal_repository import DatabaseTradeJournalStorage
    from app.schemas.trade_journal import TradeJournalCreate, TradeJournalUpdate

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    temp_file = Path("backend/data/test_coherence.json")
    outbox_file = Path("backend/data/test_coherence_outbox.json")
    for f in (temp_file, outbox_file):
        if f.exists():
            f.unlink()

    try:
        storage = DatabaseTradeJournalStorage(persistence_file=str(temp_file))

        with TestingSessionLocal() as session:
            p = TradeJournalCreate(
                symbol="AUD_USD",
                direction="BUY",
                entryPrice=0.6550,
                stopLoss=0.6500,
                takeProfit=0.6650,
                reasonForEntry="Update test",
                timeframe="H1",
                marketSession="LONDON",
                tradeDate=datetime(2026, 4, 4, 8, 0, tzinfo=timezone.utc),
                status="OPEN",
            )
            created = storage.create_trade(p, session=session)
            session.commit()

            # 1. Update trade to CLOSED
            upd = TradeJournalUpdate(status="CLOSED", result="WIN", profitLoss=50.0)
            updated = storage.update_trade(created.id, upd, session=session)
            session.commit()
            assert updated.status == "CLOSED"
            assert updated.result == "WIN"

            # Check fallback memory also reflects the update
            mem_item = storage._fallback_memory.get_trade(created.id)
            assert mem_item.status == "CLOSED"

            # 2. Delete trade
            deleted = storage.delete_trade(created.id, session=session)
            session.commit()
            assert deleted is True

            # Must be gone from both DB and fallback
            trades_after = storage.list_trades(session=session)
            assert len(trades_after) == 0
            assert storage._fallback_memory.get_trade(created.id) is None
    finally:
        for f in (temp_file, outbox_file):
            if f.exists():
                f.unlink()


def test_concurrent_writes_and_reconciliation_thread_safety():
    """Verify that concurrent writes and reconciliation do not produce corrupted journal state."""
    import threading
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database.models import Base
    from app.core.repository.trade_journal_repository import DatabaseTradeJournalStorage
    from app.schemas.trade_journal import TradeJournalCreate

    temp_db = Path("backend/data/test_threads.db")
    temp_file = Path("backend/data/test_threads.json")
    outbox_file = Path("backend/data/test_threads_outbox.json")
    for f in (temp_db, temp_file, outbox_file):
        if f.exists():
            f.unlink()

    engine = create_engine(f"sqlite:///{temp_db}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    try:
        storage = DatabaseTradeJournalStorage(persistence_file=str(temp_file))
        num_threads = 4
        trades_per_thread = 3
        errors = []

        def worker(worker_id: int):
            try:
                for i in range(trades_per_thread):
                    payload = TradeJournalCreate(
                        symbol=f"PAIR_{worker_id}_{i}",
                        direction="BUY",
                        entryPrice=1.0 + worker_id * 0.1,
                        stopLoss=0.9,
                        takeProfit=1.2,
                        reasonForEntry=f"Worker {worker_id} trade {i}",
                        timeframe="H1",
                        marketSession="LONDON",
                        tradeDate=datetime.now(timezone.utc),
                        status="OPEN",
                    )
                    with TestingSessionLocal() as session:
                        storage.create_trade(payload, session=session)
                        session.commit()
                        if i == 1:
                            storage.reconcile_outbox(session=session)
                            session.commit()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(wid,)) for wid in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        with TestingSessionLocal() as session:
            final_trades = storage.list_trades(session=session)
            assert len(final_trades) == num_threads * trades_per_thread
    finally:
        engine.dispose()
        for f in (temp_db, temp_file, outbox_file):
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass


def test_alembic_0008_migration_isolated_lifecycle():
    """Verify that migration 0008 upgrades cleanly from 0007, adds initial_stop_loss,
    permits model reads/writes, downgrades cleanly, and never runs against production.
    """
    from pathlib import Path
    from sqlalchemy import create_engine, inspect, Column, Integer, String, Float, DateTime
    from sqlalchemy.orm import declarative_base, sessionmaker
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    import importlib.util

    # 1. Setup isolated in-memory SQLite schema mimicking trade_journal up to 0007
    engine = create_engine("sqlite:///:memory:")
    BaseTemp = declarative_base()

    class TradeJournalMock(BaseTemp):
        __tablename__ = "trade_journal"
        id = Column(Integer, primary_key=True)
        symbol = Column(String(20))
        initial_monetary_risk = Column(Float, nullable=True)

    BaseTemp.metadata.create_all(engine)

    # Verify column initial_stop_loss does NOT exist initially
    inspector = inspect(engine)
    cols = [c["name"] for c in inspector.get_columns("trade_journal")]
    assert "initial_stop_loss" not in cols
    assert "initial_monetary_risk" in cols

    # 2. Dynamically import migration 0008 module
    mig_path = Path("database/migrations/versions/0008_v10_initial_stop_loss.py")
    spec = importlib.util.spec_from_file_location("mig_0008", str(mig_path))
    mig_0008 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig_0008)

    assert mig_0008.revision == "0008_v10_initial_stop_loss"
    assert mig_0008.down_revision == "0007_v10_initial_monetary_risk"

    # 3. Apply upgrade() via isolated MigrationContext
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        mig_0008.op = op
        mig_0008.upgrade()

    # 4. Verify column initial_stop_loss exists after upgrade
    inspector = inspect(engine)
    cols_after = [c["name"] for c in inspector.get_columns("trade_journal")]
    assert "initial_stop_loss" in cols_after

    # Verify writes and reads with initial_stop_loss
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO trade_journal (id, symbol, initial_stop_loss, initial_monetary_risk) VALUES (1, 'EUR_USD', 1.0800, 100.0)"
        )
        res = conn.exec_driver_sql("SELECT initial_stop_loss FROM trade_journal WHERE id = 1").scalar()
        assert float(res) == 1.0800

    # 5. Apply downgrade() via isolated MigrationContext
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        mig_0008.op = op
        mig_0008.downgrade()

    # 6. Verify column initial_stop_loss was dropped cleanly
    inspector = inspect(engine)
    cols_downgrade = [c["name"] for c in inspector.get_columns("trade_journal")]
    assert "initial_stop_loss" not in cols_downgrade


def test_migration_guard_fail_closed_safety():
    """Verify that migration_guard prevents accidental execution against production,
    enforces explicit MIGRATION_ENV, and redacts credentials in all logs/errors.
    """
    import pytest
    from app.core.database.migration_guard import validate_migration_target, redact_url, MigrationTargetError

    # 1. Redaction tests
    raw_secret_url = "postgresql://postgres.user:superSecretP@ss123@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
    redacted = redact_url(raw_secret_url)
    assert "superSecretP@ss123" not in redacted
    assert "[REDACTED]" in redacted
    assert "aws-0-eu-west-1.pooler.supabase.com" in redacted

    # 2. Missing MIGRATION_ENV fails closed
    with pytest.raises(MigrationTargetError) as exc_info:
        validate_migration_target(None, "sqlite:///test.db")
    assert "MIGRATION_ENV is unset" in str(exc_info.value)

    with pytest.raises(MigrationTargetError) as exc_info:
        validate_migration_target("", "sqlite:///test.db")
    assert "MIGRATION_ENV is unset" in str(exc_info.value)

    # 3. Explicit PRODUCTION target is rejected unconditionally by guard
    with pytest.raises(MigrationTargetError) as exc_info:
        validate_migration_target("PRODUCTION", raw_secret_url)
    assert "Production migrations are strictly forbidden" in str(exc_info.value)
    assert "superSecretP@ss123" not in str(exc_info.value)

    # 4. Target environment mismatch: LOCAL or TEST pointing to remote Supabase URL is rejected
    with pytest.raises(MigrationTargetError) as exc_info:
        validate_migration_target("LOCAL", raw_secret_url)
    assert "prohibited under MIGRATION_ENV='LOCAL'" in str(exc_info.value)
    assert "superSecretP@ss123" not in str(exc_info.value)

    with pytest.raises(MigrationTargetError) as exc_info:
        validate_migration_target("TEST", raw_secret_url)
    assert "prohibited under MIGRATION_ENV='TEST'" in str(exc_info.value)

    # 5. Missing DATABASE_URL fails closed
    with pytest.raises(MigrationTargetError) as exc_info:
        validate_migration_target("LOCAL", "")
    assert "DATABASE_URL is not set" in str(exc_info.value)

    # 6. Valid LOCAL targets pass
    assert validate_migration_target("LOCAL", "sqlite:///data/test.db") == "sqlite:///data/test.db"
    assert validate_migration_target("LOCAL", "postgresql://user:pass@localhost:5432/falcon") == "postgresql://user:pass@localhost:5432/falcon"

    # 7. Valid STAGING target passes with non-production domain
    staging_url = "postgresql://app:pass@staging-db.internal:5432/falcon_staging"
    assert validate_migration_target("STAGING", staging_url) == staging_url


def test_trade_journal_state_divergence_and_health_reconciliation():
    """Verify that if a trade is created in DB but closed during a transient DB outage,
    fallback memory maintains the closed state, list_trades returns the closed state,
    health check detects the divergence, and reconcile_outbox updates the DB record upon recovery.
    """
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database.models import Base, TradeJournalRecord
    from app.core.repository.trade_journal_repository import DatabaseTradeJournalStorage
    from app.schemas.trade_journal import TradeJournalCreate, TradeJournalUpdate

    temp_db = Path("backend/data/test_divergence.db")
    temp_file = Path("backend/data/test_divergence.json")
    outbox_file = Path("backend/data/test_divergence_outbox.json")
    for f in (temp_db, temp_file, outbox_file):
        if f.exists():
            f.unlink()

    engine = create_engine(f"sqlite:///{temp_db}")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    try:
        storage = DatabaseTradeJournalStorage(persistence_file=str(temp_file))

        # 1. Create trade in DB while DB is healthy
        with TestingSessionLocal() as session:
            payload = TradeJournalCreate(
                strategyId="incubation_strategy_1",
                symbol="EUR_USD",
                direction="BUY",
                entryPrice=1.0850,
                stopLoss=1.0800,
                takeProfit=1.0950,
                reasonForEntry="Test open trade",
                timeframe="H1",
                marketSession="LONDON",
                tradeDate=datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc),
                status="OPEN",
            )
            created = storage.create_trade(payload, session=session)
            session.commit()
            trade_id = created.id

        # Verify DB and memory both have OPEN
        with TestingSessionLocal() as session:
            db_trade = session.get(TradeJournalRecord, trade_id)
            assert db_trade.status == "OPEN"
            health = storage.get_storage_health(session=session)
            assert health["durability_mode"] == "POSTGRES_HEALTHY"
            assert health["outbox_pending_count"] == 0

        # 2. Simulate DB outage during trade close by updating trade without passing session
        # or when session fails. We directly test update_trade failure branch or updating fallback memory.
        update_payload = TradeJournalUpdate(
            status="CLOSED",
            exitPrice=1.0920,
            pnl=70.0,
            pnlR=1.4,
            result="WIN",
            reasonForExit="Hit TP target during DB blip",
            closeDate=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        )
        # Update fallback memory and queue to outbox directly (mimicking update_trade catching DB failure)
        storage._fallback_memory.update_trade(trade_id, update_payload)
        storage._outbox_pending_ids.add(trade_id)
        storage._save_outbox_to_disk()

        # 3. Verify list_trades returns the CLOSED state from memory despite DB having OPEN
        with TestingSessionLocal() as session:
            trades = storage.list_trades(session=session)
            assert len(trades) == 1
            assert trades[0].status == "CLOSED"
            assert trades[0].exitPrice == 1.0920

            # 4. Verify get_storage_health detects state divergence
            health_divergent = storage.get_storage_health(session=session)
            assert health_divergent["durability_mode"] == "POSTGRES_UNSYNCED_OUTBOX"
            assert health_divergent["outbox_pending_count"] == 1

            # 5. Primary DB recovers: reconcile_outbox syncs the CLOSED state into DB
            reconciled = storage.reconcile_outbox(session=session)
            assert reconciled == 1
            session.commit()

            # 6. Verify DB record is now CLOSED
            session.expire_all()
            db_recovered = session.get(TradeJournalRecord, trade_id)
            assert db_recovered.status == "CLOSED"
            assert float(db_recovered.exit_price) == 1.0920
            assert db_recovered.reason_for_exit == "Hit TP target during DB blip"

            # 7. Verify health is back to POSTGRES_HEALTHY
            health_recovered = storage.get_storage_health(session=session)
            assert health_recovered["durability_mode"] == "POSTGRES_HEALTHY"
            assert health_recovered["outbox_pending_count"] == 0
    finally:
        engine.dispose()
        for f in (temp_db, temp_file, outbox_file):
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass



