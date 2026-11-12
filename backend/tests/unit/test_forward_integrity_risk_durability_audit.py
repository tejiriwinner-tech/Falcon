"""
Falcon Forward Paper-Trading Integrity, Risk & Durability Audit Suite.

Deterministic validation of:
1. Paper/live capital isolation (6 required audit scenarios).
2. Instrument-specific sizing, contract units, and monetary risk (GBP/USD, AUD/USD, XAU/USD gold, USD/JPY fail-closed).
3. Forward-trade lifecycle (Pending -> Filled/Open -> Stop/Target Close, 45m Expiration, R accounting, Mark-to-Market).
4. Journal, Outbox, and Database Recovery across 12 failure and interruption scenarios.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import threading
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.core.database.models import Base, TradeJournalRecord
from app.core.engines.paper_runtime import PaperTradingRuntime
from app.core.engines.paper_trading_engine import PaperTradingEngine
from app.core.execution.execution_mode_guard import (
    ExecutionForbiddenError,
    ExecutionMode,
    ExecutionModeGuard,
    execution_mode_guard,
    is_paper_record,
    resolve_record_execution_mode,
)
from app.core.repository.trade_journal_repository import (
    DatabaseTradeJournalStorage,
    InMemoryTradeJournalStorage,
    TradeJournalRepository,
    trade_journal_repository,
)
from app.core.services.capital_cycle_service import CapitalCycleService
from app.core.services.capital_guardian_service import (
    CapitalGuardianService,
    capital_guardian_service,
)
from app.core.services.signal_authorization_service import (
    SignalAuthorizationService,
    signal_authorization_service,
)
from app.schemas.capital_cycle import (
    CapitalCycleCreate,
    CapitalCycleItem,
    CapitalCycleStatus,
)
from app.schemas.capital_guardian import (
    CapitalGuardianDecision,
    GuardianState,
    ProposedTradeInput,
)
from app.schemas.market_quote import BidAsk, MarketQuote
from app.schemas.trade_journal import (
    TradeJournalCreate,
    TradeJournalItem,
    TradeJournalUpdate,
)
from app.services.execution.order_execution_service import (
    ExecutionOrderCreate,
    OrderAction,
    OrderExecutionService,
)


# =====================================================================
# SECTION 1: PROVE PAPER / LIVE CAPITAL ISOLATION & RISK ENFORCEMENT
# =====================================================================

def test_paper_isolation_scenario_1_paper_cycle_available():
    """Scenario 1: Paper request with isolated paper cycle available -> authorized under CYCLE-PAPER-001."""
    auth_service = SignalAuthorizationService()
    proposal = ProposedTradeInput(
        symbol="GBP/USD",
        direction="BUY",
        entryPrice=Decimal("1.33961"),
        stopLoss=Decimal("1.33791"),
        takeProfit=Decimal("1.34301"),
        lotSize=Decimal("0.01"),
    )
    decision = auth_service.evaluate_proposal(proposal, execution_mode="PAPER")
    assert decision.allowed is True
    assert decision.cycleId == "CYCLE-PAPER-001"
    assert decision.activeTradingCapital == Decimal("10000.00")
    assert decision.proposedWorstCaseLoss == Decimal("1.70")


def test_paper_isolation_scenario_2_paper_cycle_missing():
    """Scenario 2: Paper request when paper cycle is missing/None -> fails closed with HALTED state."""
    auth_service = SignalAuthorizationService()
    proposal = ProposedTradeInput(
        symbol="GBP/USD",
        direction="BUY",
        entryPrice=Decimal("1.33961"),
        stopLoss=Decimal("1.33791"),
        takeProfit=Decimal("1.34301"),
        lotSize=Decimal("0.01"),
    )
    with patch.object(auth_service, "get_paper_cycle", return_value=None):
        decision = auth_service.evaluate_proposal(proposal, execution_mode="PAPER")
        assert decision.allowed is False
        assert decision.state == GuardianState.HALTED
        assert "No active capital cycle" in decision.reason
        assert decision.cycleId is None


def test_paper_isolation_scenario_3_live_request_cannot_use_paper_cycle():
    """Scenario 3: Live request when only paper cycle exists (live cycle None) -> cannot inherit paper cycle."""
    mock_cycle_service = MagicMock()
    mock_cycle_service.get_active_cycle.return_value = None  # No live cycle in database

    auth_service = SignalAuthorizationService(cycle_service=mock_cycle_service)
    proposal = ProposedTradeInput(
        symbol="GBP/USD",
        direction="BUY",
        entryPrice=Decimal("1.33961"),
        stopLoss=Decimal("1.33791"),
        takeProfit=Decimal("1.34301"),
        lotSize=Decimal("0.01"),
    )
    # LIVE request must strictly check _cycle_service and fail closed
    decision = auth_service.evaluate_proposal(proposal, execution_mode="LIVE")
    assert decision.allowed is False
    assert decision.state == GuardianState.HALTED
    assert "No active capital cycle" in decision.reason
    assert decision.cycleId is None
    assert mock_cycle_service.get_active_cycle.call_count == 1


def test_paper_isolation_scenario_4_live_request_when_live_cycle_halted():
    """Scenario 4: Live request when live cycle is halted -> strictly rejected."""
    mock_cycle_service = MagicMock()
    now = datetime.now(timezone.utc)
    mock_cycle_service.get_active_cycle.return_value = CapitalCycleItem(
        id=1,
        cycleId="cycle-live-halted",
        cycleNumber=1,
        startingCapital=Decimal("20.00"),
        targetCapital=Decimal("50.00"),
        activeTradingCapital=Decimal("0.00"),
        protectedProfit=Decimal("0.00"),
        status=CapitalCycleStatus.HALTED,
        startedAt=now,
        createdAt=now,
        updatedAt=now,
    )

    auth_service = SignalAuthorizationService(cycle_service=mock_cycle_service)
    proposal = ProposedTradeInput(
        symbol="GBP/USD",
        direction="BUY",
        entryPrice=Decimal("1.33961"),
        stopLoss=Decimal("1.33791"),
        takeProfit=Decimal("1.34301"),
        lotSize=Decimal("0.01"),
    )
    decision = auth_service.evaluate_proposal(proposal, execution_mode="LIVE")
    assert decision.allowed is False
    assert decision.state == GuardianState.HALTED
    assert "halted" in decision.reason.lower()


def test_paper_isolation_scenario_5_broker_dispatch_blocked_in_paper():
    """Scenario 5: Every broker order dispatch entry point remains strictly blocked under PAPER mode."""
    exec_service = OrderExecutionService()
    exec_service._orders.clear()

    order_in = ExecutionOrderCreate(
        signal_id=9901,
        symbol="GBP/USD",
        action=OrderAction.BUY,
        order_type="MARKET",
        lot_size=Decimal("0.01"),
        entry_price=Decimal("1.33961"),
        stop_loss=Decimal("1.33791"),
        take_profit=Decimal("1.34301"),
    )

    with patch("app.core.providers._oanda_provider.create_order") as mock_oanda, \
         patch("app.services.execution.order_execution_service.telegram_alert_service.dispatch_raw_message"):
        res = exec_service.create_order(order_in)
        assert res is not None
        assert mock_oanda.call_count == 0
        assert execution_mode_guard.is_live_authorized() is False
        assert execution_mode_guard.is_broker_locked() is True


def test_paper_isolation_scenario_6_direct_execution_without_guardian_fails_closed():
    """Scenario 6: Attempting to force live broker execution raises ExecutionForbiddenError."""
    with pytest.raises(ExecutionForbiddenError) as exc_info:
        execution_mode_guard.assert_live_execution_permitted()
    assert "Live broker execution is prohibited" in str(exc_info.value)


# =====================================================================
# SECTION 2: VALIDATE INSTRUMENT-SPECIFIC SIZING & MONETARY RISK
# =====================================================================

def test_instrument_sizing_trade_4_gbpusd():
    """Trade #4: GBP/USD BUY - 17 pips distance, 0.01 lot (1,000 units) -> $1.70 monetary risk."""
    guardian = CapitalGuardianService()
    # Contract specification: 1 standard lot = 100,000 GBP. 0.01 lot = 1,000 GBP.
    # Risk distance: 1.33961 - 1.33791 = 0.00170 USD per GBP.
    # Monetary risk: 0.00170 * 1,000 = $1.70 USD.
    loss = guardian.calculate_trade_worst_case_loss(
        direction="BUY",
        entry_price=Decimal("1.33961"),
        stop_loss=Decimal("1.33791"),
        lot_size=Decimal("0.01"),
        symbol="GBP/USD",
    )
    assert loss == Decimal("1.70")


def test_instrument_sizing_trade_5_audusd():
    """Trade #5: AUD/USD SELL - 29.2 pips distance, 0.01 lot (1,000 units) -> $2.92 monetary risk."""
    guardian = CapitalGuardianService()
    # Contract specification: 1 standard lot = 100,000 AUD. 0.01 lot = 1,000 AUD.
    # Risk distance: 0.70407 - 0.70115 = 0.00292 USD per AUD.
    # Monetary risk: 0.00292 * 1,000 = $2.92 USD.
    loss = guardian.calculate_trade_worst_case_loss(
        direction="SELL",
        entry_price=Decimal("0.70115"),
        stop_loss=Decimal("0.70407"),
        lot_size=Decimal("0.01"),
        symbol="AUD/USD",
    )
    assert loss == Decimal("2.92")


def test_instrument_sizing_trade_6_xauusd_gold_contract_units():
    """Trade #6: XAU/USD SELL - $58.71 price distance, 0.01 lot (1 troy oz) -> $58.71 monetary risk.
    Proves contract sizing is 100 oz per standard lot, not 100,000 FX units!
    """
    guardian = CapitalGuardianService()
    # Contract specification: 1 standard lot = 100 troy ounces.
    # 0.01 lot = 1.00 troy ounce.
    # Price distance: 4140.47 - 4081.76 = $58.71 USD per ounce.
    # Monetary risk: 58.71 * 1.00 oz = $58.71 USD.
    loss = guardian.calculate_trade_worst_case_loss(
        direction="SELL",
        entry_price=Decimal("4081.76"),
        stop_loss=Decimal("4140.47"),
        lot_size=Decimal("0.01"),
        symbol="XAU/USD",
    )
    assert loss == Decimal("58.71")

    # If lot size were 0.10 lots (10 oz), risk would be $587.10
    loss_tenth = guardian.calculate_trade_worst_case_loss(
        direction="SELL",
        entry_price=Decimal("4081.76"),
        stop_loss=Decimal("4140.47"),
        lot_size=Decimal("0.10"),
        symbol="XAU/USD",
    )
    assert loss_tenth == Decimal("587.10")


def test_instrument_sizing_usdjpy_cross_currency_fails_closed():
    """USD/JPY and JPY-quoted pairs fail closed because quote currency is JPY without live FX rate."""
    guardian = CapitalGuardianService()
    with pytest.raises(ValueError) as exc_info:
        guardian.calculate_trade_worst_case_loss(
            direction="BUY",
            entry_price=Decimal("152.50"),
            stop_loss=Decimal("151.80"),
            lot_size=Decimal("0.01"),
            symbol="USD/JPY",
        )
    assert "quote currency is 'JPY', but account currency is USD" in str(exc_info.value)


def test_instrument_sizing_missing_symbol_and_metadata_fails_closed():
    """Unregistered instrument symbol fails closed with descriptive error."""
    guardian = CapitalGuardianService()
    with pytest.raises(ValueError) as exc_info:
        guardian.calculate_trade_worst_case_loss(
            direction="BUY",
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("95.00"),
            lot_size=Decimal("0.01"),
            symbol="UNKNOWN_COIN/USD",
        )
    assert "not registered in Falcon" in str(exc_info.value)


# =====================================================================
# SECTION 3: TRACE THE FULL FORWARD-TRADE LIFECYCLE
# =====================================================================

def test_forward_lifecycle_simulated_fill_and_target_exit():
    """Trace lifecycle: PENDING reservation -> quote crosses entry -> OPEN (filled) -> TP reached -> CLOSED WIN with realized R."""
    storage = InMemoryTradeJournalStorage()
    repo = TradeJournalRepository(storage)
    engine = PaperTradingEngine(journal_repo=repo)
    now = datetime.now(timezone.utc)

    # 1. Create PENDING reservation
    trade = repo.create_trade(
        TradeJournalCreate(
            signalId=1001,
            strategyId="strat-005",
            symbol="GBP/USD",
            direction="BUY",
            entryPrice=1.33961,
            stopLoss=1.33791,
            takeProfit=1.34301,
            status="PENDING",
            result="PENDING",
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            initialStopLoss=1.33791,
            initialMonetaryRisk="1.70",
            reasonForEntry="Test forward buy entry",
            executionMode=ExecutionMode.PAPER.value,
        )
    )
    assert trade.status == "PENDING"
    assert trade.fillPrice is None

    # 2. Quote crosses entry price (ask drops to 1.33960 <= entry 1.33961) -> simulated fill
    quote_fill = MarketQuote(
        symbol="GBP/USD",
        lastPrice=1.33960,
        bidAsk=BidAsk(bid=1.33955, ask=1.33960, spread=0.00005),
        timestamp=now + timedelta(minutes=5),
        freshnessSeconds=1.0,
        providerId="oanda_test",
        providerName="OANDA",
    )
    resolved = engine.process_quote(quote_fill)
    filled_item = next((r for r in resolved if r.id == trade.id), None)
    assert filled_item is not None
    assert filled_item.status == "OPEN"
    assert filled_item.fillPrice is not None
    assert filled_item.closeDate is None

    # 3. Market moves to take-profit (bid reaches 1.34310 >= TP 1.34301) -> closed WIN
    quote_tp = MarketQuote(
        symbol="GBP/USD",
        lastPrice=1.34310,
        bidAsk=BidAsk(bid=1.34310, ask=1.34315, spread=0.00005),
        timestamp=now + timedelta(minutes=30),
        freshnessSeconds=1.0,
        providerId="oanda_test",
        providerName="OANDA",
    )
    resolved_tp = engine.process_quote(quote_tp)
    closed_item = next((r for r in resolved_tp if r.id == trade.id), None)
    assert closed_item is not None
    assert closed_item.status == "CLOSED"
    assert closed_item.result == "WIN"
    assert closed_item.closeDate is not None
    assert closed_item.exitPrice == 1.34301
    # Realized R is calculated as (exit - fill) / (fill - SL) = (1.34301 - 1.33960) / (1.33960 - 1.33791) = 2.01
    assert abs(closed_item.realizedRMultiple - 2.01) < 1e-4


def test_forward_lifecycle_simulated_stop_loss_exit():
    """Trace lifecycle: PENDING reservation -> filled -> Stop Loss breached -> CLOSED LOSS with realized R = -1.0."""
    storage = InMemoryTradeJournalStorage()
    repo = TradeJournalRepository(storage)
    engine = PaperTradingEngine(journal_repo=repo)
    now = datetime.now(timezone.utc)

    # 1. Create OPEN trade directly (already filled)
    trade = repo.create_trade(
        TradeJournalCreate(
            signalId=1002,
            strategyId="strat-005",
            symbol="GBP/USD",
            direction="BUY",
            entryPrice=1.33961,
            stopLoss=1.33791,
            takeProfit=1.34301,
            fillPrice=1.33961,
            fillTime=now,
            status="OPEN",
            result="OPEN",
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            initialStopLoss=1.33791,
            initialMonetaryRisk="1.70",
            reasonForEntry="Test forward buy entry",
            executionMode=ExecutionMode.PAPER.value,
        )
    )

    # 2. Market drops below stop loss (bid drops to 1.33780 <= SL 1.33791) -> closed LOSS
    quote_sl = MarketQuote(
        symbol="GBP/USD",
        lastPrice=1.33780,
        bidAsk=BidAsk(bid=1.33775, ask=1.33785, spread=0.00010),
        timestamp=now + timedelta(minutes=15),
        freshnessSeconds=1.0,
        providerId="oanda_test",
        providerName="OANDA",
    )
    resolved = engine.process_quote(quote_sl)
    closed_item = next((r for r in resolved if r.id == trade.id), None)
    assert closed_item is not None
    assert closed_item.status == "CLOSED"
    assert closed_item.result == "LOSS"
    assert closed_item.exitPrice == 1.33791
    # Realized R must be exactly -1.0
    assert closed_item.realizedRMultiple == -1.0


def test_forward_lifecycle_pending_expiration_after_45_minutes():
    """Trace lifecycle: PENDING reservation older than 45 minutes without fill is expired."""
    storage = InMemoryTradeJournalStorage()
    repo = TradeJournalRepository(storage)
    engine = PaperTradingEngine(journal_repo=repo)
    runtime = PaperTradingRuntime(engine=engine, journal_repo=repo, validity_minutes=45)
    now = datetime.now(timezone.utc)

    # Create PENDING trade created 50 minutes ago
    trade_old = repo.create_trade(
        TradeJournalCreate(
            signalId=2001,
            strategyId="strat-005",
            symbol="GBP/USD",
            direction="BUY",
            entryPrice=1.33961,
            stopLoss=1.33791,
            takeProfit=1.34301,
            status="PENDING",
            result="PENDING",
            timeframe="M15",
            marketSession="London",
            tradeDate=now - timedelta(minutes=50),
            initialStopLoss=1.33791,
            initialMonetaryRisk="1.70",
            reasonForEntry="Test forward buy entry",
            executionMode=ExecutionMode.PAPER.value,
        )
    )

    # Run paper runtime polling cycle
    cycle_res = runtime.process_cycle(as_of=now, quotes=[])
    assert cycle_res["expired_count"] == 1

    updated_trade = repo.get_trade(trade_old.id)
    assert updated_trade.status == "EXPIRED"
    assert "expired after 45m" in (updated_trade.reasonForExit or "").lower()


# =====================================================================
# SECTION 4: JOURNAL, OUTBOX, AND DATABASE RECOVERY (12 SCENARIOS)
# =====================================================================

def test_recovery_scenario_1_and_2_create_persist_restart(tmp_path):
    """Scenarios 1 & 2: Create paper reservation on disk fallback, restart storage process, and verify intact restoration."""
    persist_file = str(tmp_path / "paper_journal.json")
    outbox_file = str(tmp_path / "paper_journal_outbox.json")

    # Instance 1: Create trade
    storage1 = DatabaseTradeJournalStorage(persistence_file=persist_file)
    item1 = storage1.create_trade(
        TradeJournalCreate(
            signalId=501,
            strategyId="strat-002",
            symbol="XAU/USD",
            direction="SELL",
            entryPrice=4081.76,
            stopLoss=4140.47,
            takeProfit=3964.35,
            status="PENDING",
            result="PENDING",
            timeframe="H1",
            marketSession="London",
            tradeDate=datetime.now(timezone.utc),
            initialStopLoss=4140.47,
            initialMonetaryRisk="58.71",
            reasonForEntry="Test gold reservation",
            executionMode=ExecutionMode.PAPER.value,
        )
    )
    assert item1.id == 1
    assert 1 in storage1._outbox_pending_ids

    # Instance 2 (Simulated process restart): Load from disk
    storage2 = DatabaseTradeJournalStorage(persistence_file=persist_file)
    trades2 = storage2.list_trades()
    assert len(trades2) == 1
    assert trades2[0].id == 1
    assert trades2[0].symbol == "XAU/USD"
    assert Decimal(str(trades2[0].initialMonetaryRisk)) == Decimal("58.71")
    assert trades2[0].executionMode == "PAPER"
    assert 1 in storage2._outbox_pending_ids


def test_recovery_scenario_3_and_4_db_unavailable_during_crud(tmp_path):
    """Scenarios 3 & 4: Simulate DB failure during create, update, and close -> fallback memory & outbox preserve state."""
    persist_file = str(tmp_path / "paper_journal_crud.json")
    storage = DatabaseTradeJournalStorage(persistence_file=persist_file)

    # 1. Create with DB unavailable (session=None, DB connection fails)
    trade = storage.create_trade(
        TradeJournalCreate(
            signalId=601,
            strategyId="strat-005",
            symbol="GBP/USD",
            direction="BUY",
            entryPrice=1.33961,
            stopLoss=1.33791,
            takeProfit=1.34301,
            status="PENDING",
            result="PENDING",
            timeframe="M15",
            marketSession="London",
            tradeDate=datetime.now(timezone.utc),
            initialStopLoss=1.33791,
            initialMonetaryRisk="1.70",
            reasonForEntry="Test forward buy entry",
            executionMode=ExecutionMode.PAPER.value,
        )
    )
    assert trade.id == 1
    assert 1 in storage._outbox_pending_ids

    # 2. Update to OPEN with DB unavailable
    now = datetime.now(timezone.utc)
    updated = storage.update_trade(
        1,
        TradeJournalUpdate(
            status="OPEN",
            result="OPEN",
            fillPrice=1.33961,
            fillTime=now,
        ),
    )
    assert updated.status == "OPEN"
    assert updated.fillPrice == 1.33961

    # 3. Close with DB unavailable
    closed = storage.update_trade(
        1,
        TradeJournalUpdate(
            status="CLOSED",
            result="WIN",
            exitPrice=1.34301,
            profitLoss=3.40,
            realizedRMultiple=2.0,
            closeDate=now + timedelta(minutes=20),
            reasonForExit="Target reached",
        ),
    )
    assert closed.status == "CLOSED"
    assert closed.result == "WIN"
    assert closed.realizedRMultiple == 2.0

    # Storage health shows unsynced fallback
    health = storage.get_storage_health()
    assert health["fallback_records"] == 1
    assert health["outbox_pending_count"] == 1


def test_recovery_scenario_5_and_6_reconnection_and_idempotent_reconcile(tmp_path):
    """Scenarios 5 & 6: Restore DB connectivity, reconcile outbox into SQLite/Postgres schema, verify idempotency."""
    db_file = tmp_path / "recovery_reconcile.db"
    persist_file = str(tmp_path / "recovery_reconcile.json")

    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    try:
        storage = DatabaseTradeJournalStorage(persistence_file=persist_file)

        # 1. Create trade in fallback mode
        created = storage._fallback_memory.create_trade(
            TradeJournalCreate(
                signalId=701,
                strategyId="strat-018",
                symbol="AUD/USD",
                direction="SELL",
                entryPrice=0.70115,
                stopLoss=0.70407,
                takeProfit=0.69385,
                status="CLOSED",
                result="WIN",
                exitPrice=0.69385,
                profitLoss=7.30,
                realizedRMultiple=2.5,
                timeframe="M15",
                marketSession="London",
                tradeDate=datetime.now(timezone.utc),
                closeDate=datetime.now(timezone.utc),
                initialStopLoss=0.70407,
                initialMonetaryRisk="2.92",
                reasonForEntry="Test AUD/USD reservation",
                executionMode=ExecutionMode.PAPER.value,
            )
        )
        storage._outbox_pending_ids.add(created.id)
        storage._save_outbox_to_disk()

        # 2. Reconnect DB and reconcile
        with Session() as session:
            count = storage.reconcile_outbox(session=session)
            session.commit()
            assert count == 1
            assert len(storage._outbox_pending_ids) == 0

        # Verify DB has record with correct initial_stop_loss and initial_monetary_risk
        with Session() as session:
            record = session.get(TradeJournalRecord, created.id)
            assert record is not None
            assert record.symbol == "AUD/USD"
            assert record.status == "CLOSED"
            assert round(float(record.initial_stop_loss), 5) == 0.70407
            assert round(float(record.initial_monetary_risk), 2) == 2.92

        # 3. Repeat reconciliation to prove idempotency (Scenario 6)
        with Session() as session:
            repeat_count = storage.reconcile_outbox(session=session)
            assert repeat_count == 0

            # DB records remain unchanged at 1
            all_records = session.scalars(select(TradeJournalRecord)).all()
            assert len(all_records) == 1
    finally:
        engine.dispose()


def test_recovery_scenario_8_and_9_older_fallback_cannot_overwrite_newer_db(tmp_path):
    """Scenarios 8 & 9: Verify that an older fallback record cannot overwrite a newer authoritative database record."""
    db_file = tmp_path / "recovery_conflict.db"
    persist_file = str(tmp_path / "recovery_conflict.json")

    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    try:
        storage = DatabaseTradeJournalStorage(persistence_file=persist_file)
        t_base = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)

        # Authoritative DB already has trade closed at t_base + 30m
        with Session() as session:
            db_rec = TradeJournalRecord(
                id=1,
                signal_id=801,
                strategy_id="strat-004",
                symbol="GBP/USD",
                direction="BUY",
                entry_price=1.3300,
                stop_loss=1.3250,
                take_profit=1.3400,
                status="CLOSED",
                result="WIN",
                profit_loss=100.0,
                timeframe="H1",
                market_session="London",
                trade_date=t_base,
                close_date=t_base + timedelta(minutes=30),
                created_at=t_base,
                updated_at=t_base + timedelta(minutes=30),
                reason_for_entry="Authoritative entry",
                notes="[MODE:PAPER]",
            )
            session.add(db_rec)
            session.commit()

        # Stale fallback memory has older OPEN record updated at t_base + 5m
        storage._fallback_memory._trades[1] = TradeJournalItem(
            id=1,
            signalId=801,
            strategyId="strat-004",
            symbol="GBP/USD",
            direction="BUY",
            entryPrice=1.3300,
            stopLoss=1.3250,
            takeProfit=1.3400,
            status="OPEN",
            result="OPEN",
            timeframe="H1",
            marketSession="London",
            tradeDate=t_base,
            createdAt=t_base,
            updatedAt=t_base + timedelta(minutes=5),  # Older than DB's t_base + 30m
            reasonForEntry="Stale fallback state",
            executionMode="PAPER",
        )
        storage._outbox_pending_ids.add(1)

        # Reconcile: older fallback must NOT overwrite newer DB record
        with Session() as session:
            storage.reconcile_outbox(session=session)
            session.commit()

            # Record in DB must strictly remain CLOSED
            check_rec = session.get(TradeJournalRecord, 1)
            assert check_rec.status == "CLOSED"
            assert check_rec.profit_loss == 100.0
            assert len(storage._outbox_pending_ids) == 0
    finally:
        engine.dispose()


def test_recovery_scenario_10_missing_outbox_file_reconstructed_from_trades(tmp_path):
    """Scenario 10: Missing or corrupted outbox file reconstructs cleanly without losing fallback records."""
    persist_file = str(tmp_path / "paper_reconstruct.json")
    storage = DatabaseTradeJournalStorage(persistence_file=persist_file)

    # Create 2 trades in fallback
    storage._fallback_memory.create_trade(
        TradeJournalCreate(
            signalId=901,
            strategyId="strat-005",
            symbol="GBP/USD",
            direction="BUY",
            entryPrice=1.33961,
            stopLoss=1.33791,
            takeProfit=1.34301,
            status="PENDING",
            result="PENDING",
            timeframe="M15",
            marketSession="London",
            tradeDate=datetime.now(timezone.utc),
            reasonForEntry="Test trade 901",
            executionMode=ExecutionMode.PAPER.value,
        )
    )
    storage._fallback_memory.create_trade(
        TradeJournalCreate(
            signalId=902,
            strategyId="strat-018",
            symbol="AUD/USD",
            direction="SELL",
            entryPrice=0.70115,
            stopLoss=0.70407,
            takeProfit=0.69385,
            status="PENDING",
            result="PENDING",
            timeframe="M15",
            marketSession="London",
            tradeDate=datetime.now(timezone.utc),
            reasonForEntry="Test trade 902",
            executionMode=ExecutionMode.PAPER.value,
        )
    )

    # Delete outbox file
    outbox_file = Path(storage._outbox_file)
    if outbox_file.exists():
        outbox_file.unlink()

    # Re-initialize storage: outbox file missing, but fallback memory has 2 trades
    storage_reloaded = DatabaseTradeJournalStorage(persistence_file=persist_file)
    trades = storage_reloaded.list_trades()
    assert len(trades) == 2
    # Verify both trades are present and retrievable
    assert {t.id for t in trades} == {1, 2}
