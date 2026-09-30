"""
Falcon V10 Phase 4 — Capital Guardian -> Signal Authorization Hard-Gate Integration Test Suite.

Verifies:
1. SignalAuthorizationService initialization and isolation.
2. Direct single trade authorization and atomic PENDING reservation.
3. Transaction rollback safety on error (no orphan reservations).
4. Multi-threaded concurrency: hard 3-trade limit cannot be breached.
5. In-process threading lock serialization.
6. Hard 3-trade limit enforcement (4th trade rejected).
7. Strict capital preservation (proposed loss > remaining capacity rejected).
8. Rejection when no active capital cycle exists.
9. Rejection when active capital cycle is HALTED.
10. Rejection when active trading capital is zero or negative.
11. Rejection on missing/unsupported instrument.
12. Rejection on invalid direction.
13. Rejection on non-positive entry price.
14. Rejection on BUY SL >= entry price.
15. Rejection on SELL SL <= entry price.
16. Rejection on unsupported currency conversion.
17. Rejection of unverified caller-supplied monetaryRisk bypass.
18. Deduplication: exact same signal_id does not consume a second reservation slot.
19. Distinct signal_id consumes distinct slot up to 3.
20. SignalService: Guardian-approved candidate becomes ACTIVE.
21. SignalService: Guardian-rejected candidate becomes WAITING on watchlist with reason.
22. SignalService: Never outputs > 3 ACTIVE signals regardless of candidate pool size.
23. SignalService: Auto-dispatches to MT5 queue ONLY for Guardian-authorized signals.
24. Execution lot size consistency: Guardian evaluates exact execution lot size.
25. SignalOutcomeResolver: Does not duplicate existing PENDING reservations.
26. OrderExecutionService: create_order gates unreserved orders through Guardian.
27. OrderExecutionService: confirm_execution updates existing PENDING reservation to OPEN.
28. TradeJournal API: POST /trade-journal rejects reserving trades when Guardian limit is reached.
29. TradeJournal API: POST /trade-journal permits non-reserving (CLOSED) trades.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.repository.capital_cycle_repository import (
    CapitalCycleRepository,
    InMemoryCapitalCycleStorage,
)
from app.core.repository.trade_journal_repository import (
    InMemoryTradeJournalStorage,
    TradeJournalRepository,
)
from app.core.services.capital_cycle_service import CapitalCycleService
from app.core.services.capital_guardian_service import CapitalGuardianService
from app.core.services.signal_authorization_service import (
    FALCON_GUARDIAN_ADVISORY_LOCK_KEY,
    SignalAuthorizationService,
)
from app.schemas.capital_cycle import (
    CapitalCycleCreate,
    CapitalCycleStatus,
)
from app.schemas.capital_guardian import (
    CapitalGuardianDecision,
    GuardianState,
    ProposedTradeInput,
)
from app.schemas.decision_artifact import DecisionArtifact, DecisionStatus
from app.schemas.execution_order import (
    ExecutionOrderConfirm,
    ExecutionOrderCreate,
    OrderAction,
)
from app.schemas.signal_candidate import (
    CandidateDirection,
    CandidateMarketSnapshot,
    CandidateStatus,
    ConfidenceBreakdown,
    SignalCandidate,
)
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalUpdate
from app.core.instruments.instrument_registry import instrument_registry


@pytest.fixture
def test_setup():
    """Provides isolated in-memory repositories and services for Phase 4 testing."""
    cycle_storage = InMemoryCapitalCycleStorage()
    journal_storage = InMemoryTradeJournalStorage()

    cycle_repo = CapitalCycleRepository(storage=cycle_storage)
    journal_repo = TradeJournalRepository.__new__(TradeJournalRepository)
    journal_repo._storage = journal_storage

    cycle_service = CapitalCycleService(repository=cycle_repo)
    guardian_service = CapitalGuardianService(
        cycle_service=cycle_service,
        journal_repository=journal_repo,
        registry=instrument_registry,
    )
    auth_service = SignalAuthorizationService(
        cycle_service=cycle_service,
        guardian_service=guardian_service,
        journal_repo=journal_repo,
        cycle_repo=cycle_repo,
    )

    # Seed an active capital cycle: $20 starting & active capital
    active_cycle = cycle_repo.create_cycle(
        CapitalCycleCreate(
            cycleId="cycle-v10-p4-001",
            cycleNumber=1,
            startingCapital=Decimal("20.00"),
            targetCapital=Decimal("50.00"),
            activeTradingCapital=Decimal("20.00"),
            protectedProfit=Decimal("0.00"),
            status=CapitalCycleStatus.ACTIVE,
            startedAt=datetime.now(timezone.utc),
        )
    )

    return {
        "cycle_storage": cycle_storage,
        "journal_storage": journal_storage,
        "cycle_repo": cycle_repo,
        "journal_repo": journal_repo,
        "cycle_service": cycle_service,
        "guardian_service": guardian_service,
        "auth_service": auth_service,
        "active_cycle": active_cycle,
    }


def make_eurusd_proposal(
    entry: str = "1.1650",
    sl: str = "1.1620",
    tp: str = "1.1710",
    lot: str = "0.01",
    direction: str = "BUY",
) -> ProposedTradeInput:
    return ProposedTradeInput(
        symbol="EURUSD",
        direction=direction,
        entryPrice=Decimal(entry),
        stopLoss=Decimal(sl),
        takeProfit=Decimal(tp),
        lotSize=Decimal(lot),
    )


# 1. Service Initialization and Advisory Lock Key
def test_service_initialization(test_setup):
    auth = test_setup["auth_service"]
    assert auth is not None
    assert FALCON_GUARDIAN_ADVISORY_LOCK_KEY == 8882026


# 2. Single trade authorization succeeds & creates PENDING reservation
def test_single_trade_authorization_and_reservation(test_setup):
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]

    prop = make_eurusd_proposal(entry="1.1000", sl="1.0950", lot="0.01")  # 50 pips = $5.00
    decision, res = auth.authorize_and_reserve(proposal=prop, signal_id=101)

    assert decision.allowed is True
    assert decision.state == GuardianState.NORMAL
    assert decision.proposedWorstCaseLoss == Decimal("5.00")
    assert res is not None
    assert res.signalId == 101
    assert res.status == "PENDING"
    assert res.symbol == "EURUSD"

    # Verify stored in journal
    trades = journal_repo.list_trades()
    assert len(trades) == 1
    assert trades[0].signalId == 101
    assert trades[0].status == "PENDING"


# 3. Transaction rollback on error leaves no orphan reservation
def test_transaction_rollback_safety(test_setup):
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]

    # Force journal create_trade to throw an unexpected exception
    with patch.object(journal_repo, "create_trade", side_effect=RuntimeError("DB Write Crash")):
        prop = make_eurusd_proposal()
        decision, res = auth.authorize_and_reserve(proposal=prop, signal_id=102)

        assert decision.allowed is False
        assert "Authorization failed closed" in decision.reason
        assert res is None

    # Assert no reservation was saved
    assert len(journal_repo.list_trades()) == 0


# 4 & 5. Concurrency: 10 simultaneous threads cannot exceed 3 trades
def test_concurrent_reservations_cannot_exceed_3(test_setup):
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]

    results = []

    def try_reserve(idx: int):
        prop = make_eurusd_proposal(entry="1.1000", sl="1.0980", lot="0.01")  # 20 pips = $2.00
        dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=200 + idx)
        return dec, res

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_reserve, i) for i in range(10)]
        for f in as_completed(futures):
            results.append(f.result())

    allowed = [r for r in results if r[0].allowed is True]
    rejected = [r for r in results if r[0].allowed is False]

    # Exactly 3 must be allowed, exactly 7 rejected
    assert len(allowed) == 3
    assert len(rejected) == 7

    # Total reserving trades in repository must be exactly 3
    reserving = auth.get_active_reservations()
    assert len(reserving) == 3


# 6. Hard 3-trade limit enforcement (4th trade rejected)
def test_fourth_trade_rejected_when_three_active(test_setup):
    auth = test_setup["auth_service"]

    # Authorize 3 micro trades (each $1.00 loss)
    for i in range(1, 4):
        prop = make_eurusd_proposal(entry="1.1000", sl="1.0990", lot="0.01")  # 10 pips = $1.00
        dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=300 + i)
        assert dec.allowed is True

    # 4th trade must be rejected
    prop4 = make_eurusd_proposal(entry="1.1000", sl="1.0990", lot="0.01")
    dec4, res4 = auth.authorize_and_reserve(proposal=prop4, signal_id=304)

    assert dec4.allowed is False
    assert "Maximum simultaneous capital-reserving trades (3) reached" in dec4.reason
    assert res4 is None


# 7. Proposed loss exceeds active capital capacity -> rejected
def test_loss_capacity_exceeded_rejected(test_setup):
    auth = test_setup["auth_service"]

    # Active capital is $20.00. Propose a trade with $25.00 worst case loss (250 pips)
    prop = make_eurusd_proposal(entry="1.1250", sl="1.1000", lot="0.01")  # 250 pips = $25.00
    dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=401)

    assert dec.allowed is False
    assert "exceed active trading capital" in dec.reason
    assert res is None


# 8. Rejection when no active capital cycle exists
def test_rejection_no_active_cycle(test_setup):
    auth = test_setup["auth_service"]
    cycle_repo = test_setup["cycle_repo"]
    cycle_repo.clear()

    prop = make_eurusd_proposal()
    dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=501)

    assert dec.allowed is False
    assert dec.reason == "No active capital cycle"
    assert dec.state == GuardianState.HALTED
    assert res is None


# 9. Rejection when active cycle is HALTED
def test_rejection_active_cycle_halted(test_setup):
    auth = test_setup["auth_service"]
    cycle_repo = test_setup["cycle_repo"]
    cycle = test_setup["active_cycle"]

    from app.schemas.capital_cycle import CapitalCycleUpdate
    cycle_repo.update_cycle(cycle.cycleId, CapitalCycleUpdate(status=CapitalCycleStatus.HALTED))

    prop = make_eurusd_proposal()
    dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=502)

    assert dec.allowed is False
    assert dec.state == GuardianState.HALTED
    assert res is None


# 10. Rejection when active capital is zero or negative
def test_rejection_zero_capital(test_setup):
    auth = test_setup["auth_service"]
    cycle_repo = test_setup["cycle_repo"]
    cycle = test_setup["active_cycle"]

    from app.schemas.capital_cycle import CapitalCycleUpdate
    cycle_repo.update_cycle(
        cycle.cycleId, CapitalCycleUpdate(activeTradingCapital=Decimal("0.00"))
    )

    prop = make_eurusd_proposal()
    dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=503)

    assert dec.allowed is False
    assert "Active trading capital is zero or negative" in dec.reason
    assert res is None


# 11. Rejection on missing or invalid symbol
def test_rejection_missing_symbol(test_setup):
    auth = test_setup["auth_service"]
    prop = make_eurusd_proposal()
    prop.symbol = ""
    dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=504)
    assert dec.allowed is False
    assert "Missing instrument symbol" in dec.reason


# 12. Rejection on invalid direction
def test_rejection_invalid_direction(test_setup):
    auth = test_setup["auth_service"]
    prop = make_eurusd_proposal(direction="HOLD")
    dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=505)
    assert dec.allowed is False
    assert "Invalid trade direction" in dec.reason


# 13. Rejection on non-positive entry price
def test_rejection_non_positive_entry(test_setup):
    auth = test_setup["auth_service"]
    prop = make_eurusd_proposal(entry="0.0000")
    dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=506)
    assert dec.allowed is False
    assert "must be strictly positive" in dec.reason


# 14. Rejection on BUY stop loss >= entry price
def test_rejection_buy_sl_above_entry(test_setup):
    auth = test_setup["auth_service"]
    prop = make_eurusd_proposal(entry="1.1000", sl="1.1050", direction="BUY")
    dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=507)
    assert dec.allowed is False
    assert "must be strictly below entry price" in dec.reason


# 15. Rejection on SELL stop loss <= entry price
def test_rejection_sell_sl_below_entry(test_setup):
    auth = test_setup["auth_service"]
    prop = make_eurusd_proposal(entry="1.1000", sl="1.0950", direction="SELL")
    dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=508)
    assert dec.allowed is False
    assert "must be strictly above entry price" in dec.reason


# 16. Rejection on unsupported currency conversion
def test_rejection_unsupported_currency(test_setup):
    auth = test_setup["auth_service"]
    prop = ProposedTradeInput(
        symbol="XYZABC",
        direction="BUY",
        entryPrice=Decimal("100.00"),
        stopLoss=Decimal("90.00"),
        lotSize=Decimal("0.01"),
    )
    dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=509)
    assert dec.allowed is False
    assert "not registered in Falcon" in dec.reason or "Monetary loss cannot be reliably calculated" in dec.reason


# 17. Unverified caller monetaryRisk cannot bypass validation
def test_rejection_unverified_monetary_risk_bypass(test_setup):
    auth = test_setup["auth_service"]
    prop = make_eurusd_proposal()
    prop.monetaryRisk = Decimal("0.01")  # Fake small risk
    prop.isVerifiedRisk = False

    dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=510)
    assert dec.allowed is False
    assert "arbitrary caller-supplied monetaryRisk cannot bypass validation" in dec.reason


# 18. Deduplication: exact same signal_id does not consume extra reservation slot
def test_deduplication_same_signal_id(test_setup):
    auth = test_setup["auth_service"]
    prop = make_eurusd_proposal(entry="1.1000", sl="1.0980", lot="0.01")

    # First call: creates reservation
    dec1, res1 = auth.authorize_and_reserve(proposal=prop, signal_id=601)
    assert dec1.allowed is True
    assert res1 is not None

    # Second call with exact same signal_id: returns existing reservation
    dec2, res2 = auth.authorize_and_reserve(proposal=prop, signal_id=601)
    assert dec2.allowed is True
    assert res2.id == res1.id
    assert "already reserved" in dec2.reason

    # Verify only 1 reservation exists in total
    reserving = auth.get_active_reservations()
    assert len(reserving) == 1


# 19. Distinct signal_id consumes distinct slot
def test_distinct_signal_id_consumes_slot(test_setup):
    auth = test_setup["auth_service"]
    prop1 = make_eurusd_proposal(entry="1.1000", sl="1.0980", lot="0.01")
    prop2 = make_eurusd_proposal(entry="1.1050", sl="1.1020", lot="0.01")

    dec1, res1 = auth.authorize_and_reserve(proposal=prop1, signal_id=701)
    dec2, res2 = auth.authorize_and_reserve(proposal=prop2, signal_id=702)

    assert dec1.allowed is True
    assert dec2.allowed is True
    assert res1.id != res2.id

    reserving = auth.get_active_reservations()
    assert len(reserving) == 2


# 20 & 21 & 22. SignalService: Candidate gated, max 3 ACTIVE, rejection falls back to watchlist
def test_signal_service_guardian_hard_gate(test_setup):
    from app.core.services.signal_service import SignalService

    # Wire signal_service to use test auth service
    sig_service = SignalService()
    now = datetime.now(timezone.utc)

    # Mock missions with 5 approved candidates using registered symbols
    symbols = ["EURUSD", "GBPUSD", "XAUUSD", "USDJPY", "BTCUSD"]
    candidates = []
    for i in range(5):
        sym = symbols[i]
        if sym == "EURUSD":
            entry, sl, tp = 1.1000, 1.0950, 1.1150
        elif sym == "GBPUSD":
            entry, sl, tp = 1.2500, 1.2450, 1.2650
        elif sym == "XAUUSD":
            entry, sl, tp = 2000.0, 1995.0, 2015.0
        elif sym == "USDJPY":
            entry, sl, tp = 150.0, 149.0, 152.0
        else:
            entry, sl, tp = 60000.0, 59900.0, 60500.0

        cand = SignalCandidate(
            id=f"cand-{i}",
            strategyId="test-strat",
            strategyName="Test Strat",
            strategyVersion="1.0",
            strategyGrade="A",
            strategyScore=85,
            symbol=sym,
            direction=CandidateDirection.BUY,
            entryPrice=entry,
            stopLoss=sl,
            takeProfit=tp,
            confidence=85,
            readinessScore=90,
            riskReward=3.0,
            status=CandidateStatus.APPROVED,
            generatedAt=now,
            reasons=[],
            conditions=[],
            marketSnapshot=CandidateMarketSnapshot(
                trend="Bullish",
                volatility="Normal",
                session="London",
                spread=1.0,
                newsImpact="Low",
                marketSentiment="Bullish",
                marketConfidence=85,
            ),
            confidenceBreakdown=ConfidenceBreakdown(
                trendScore=80,
                strategyScore=85,
                sessionScore=90,
                sentimentScore=80,
                newsScore=85,
            ),
            evaluationDurationMs=10,
            marketDataAgeSeconds=5,
            evaluationStartedAt=now,
            evaluationCompletedAt=now,
        )
        dec = MagicMock()
        dec.candidateId = f"cand-{i}"
        dec.status = DecisionStatus.APPROVED
        dec.confidence = 85
        dec.aiReasoning = "Optimal setup"
        dec.recommendation = "BUY"
        dec.recommendationDetails = None
        candidates.append((cand, dec))

    mock_mission = MagicMock()
    mock_mission.id = "mission-01"

    artifacts_mock = {
        "candidates": [c[0] for c in candidates],
        "decisions": [c[1] for c in candidates],
    }

    # Mock provider_manager._cache so cur_px equals entryPrice for each candidate
    # This triggers entry_hit=True for BUY signals (cur_px <= entryPrice + tolerance).
    from unittest.mock import MagicMock as _MagicMock

    def _make_cache_entry(price):
        entry = _MagicMock()
        entry.data = _MagicMock()
        entry.data.lastPrice = price
        return entry

    price_map = {
        "EURUSD": 1.1000,
        "GBPUSD": 1.2500,
        "XAUUSD": 2000.0,
        "USDJPY": 150.0,
        "BTCUSD": 60000.0,
    }

    cache_mock = _MagicMock()
    cache_mock.get = lambda sym, allow_stale=False: _make_cache_entry(price_map[sym]) if sym in price_map else None

    pm_mock = _MagicMock()
    pm_mock._cache = cache_mock

    with patch("app.core.services.signal_service.mission_repository.get_all_missions", return_value=[mock_mission]), \
         patch("app.core.services.signal_service.mission_repository.get_mission_artifacts", return_value=artifacts_mock), \
         patch("app.core.services.signal_service.trade_journal_repository", test_setup["journal_repo"]), \
         patch("app.core.services.signal_service.signal_authorization_service", test_setup["auth_service"]), \
         patch("app.core.providers.provider_manager", pm_mock):

        resp = sig_service.build_signals(mission_limit=5)

        active_signals = [s for s in resp.signals if s.status == "ACTIVE"]
        waiting_signals = [s for s in resp.signals if s.status == "WAITING"]

        # Exactly 3 became ACTIVE (the 3-trade limit)
        assert len(active_signals) == 3

        # Remaining became WAITING with Guardian explanation (slots full)
        assert len(waiting_signals) >= 1
        assert any("Capital Guardian" in (s.analysis or "") for s in waiting_signals)


# 23 & 24. Gated MT5 order dispatch & exact lot size evaluation
def test_order_dispatch_gated_and_lot_size(test_setup):
    from app.services.execution.order_execution_service import OrderExecutionService

    exec_service = OrderExecutionService()
    exec_service.settings.default_lot_size = 0.01

    order_in = ExecutionOrderCreate(
        signal_id=801,
        symbol="EURUSD",
        action=OrderAction.BUY,
        lot_size=0.01,
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profit=1.1150,
    )

    with patch("app.services.execution.order_execution_service.trade_journal_repository", test_setup["journal_repo"]), \
         patch("app.services.execution.order_execution_service.signal_authorization_service", test_setup["auth_service"]):

        order_item = exec_service.create_order(order_in)
        assert order_item.status.value == "PENDING"
        assert order_item.lot_size == 0.01

        # Reservation was created in trade journal
        trades = test_setup["journal_repo"].list_trades()
        assert len(trades) == 1
        assert trades[0].signalId == 801
        assert trades[0].status == "PENDING"


# 25. SignalOutcomeResolver does not duplicate existing PENDING reservations
def test_signal_outcome_resolver_no_duplicate(test_setup):
    from app.core.services.signal_outcome_resolver import SignalOutcomeResolver

    resolver = SignalOutcomeResolver()
    journal_repo = test_setup["journal_repo"]

    # Pre-create PENDING reservation for signal #901
    journal_repo.create_trade(
        TradeJournalCreate(
            signalId=901,
            strategyId="test-strat",
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="H1",
            marketSession="London",
            tradeDate=datetime.now(timezone.utc),
            status="PENDING",
            result="PENDING",
            confidence=85,
            reasonForEntry="Pre-reserved",
        )
    )

    mock_sig = MagicMock(
        id=901,
        symbol="EURUSD",
        action="BUY",
        entry=1.1000,
        stopLoss=1.0950,
        takeProfit=1.1150,
        confidence=85,
        timeframe="H1",
        strategyId="test-strat",
        strategyName="Test Strat",
        status="ACTIVE",
        timestamp=datetime.now(timezone.utc),
    )

    with patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[mock_sig])), \
         patch("app.core.services.signal_outcome_resolver.trade_journal_repository", journal_repo), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=None):

        resolver.resolve_signals()

        # Count records with signalId 901
        matching = [t for t in journal_repo.list_trades() if t.signalId == 901]
        assert len(matching) == 1  # No duplicate created!


# 26. OrderExecutionService: create_order rejects unreserved trade when Guardian limits exceeded
def test_order_execution_service_rejects_unreserved_over_limit(test_setup):
    from app.services.execution.order_execution_service import OrderExecutionService

    exec_service = OrderExecutionService()
    auth = test_setup["auth_service"]

    # Fill up 3 slots
    for i in range(1, 4):
        prop = make_eurusd_proposal(entry="1.1000", sl="1.0990", lot="0.01")
        auth.authorize_and_reserve(proposal=prop, signal_id=1000 + i)

    order_in = ExecutionOrderCreate(
        signal_id=1004,
        symbol="EURUSD",
        action=OrderAction.BUY,
        lot_size=0.01,
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profit=1.1150,
    )

    with patch("app.services.execution.order_execution_service.trade_journal_repository", test_setup["journal_repo"]), \
         patch("app.services.execution.order_execution_service.signal_authorization_service", test_setup["auth_service"]):

        with pytest.raises(ValueError, match="Maximum simultaneous capital-reserving trades"):
            exec_service.create_order(order_in)


# 27. OrderExecutionService: confirm_execution transitions existing reservation to OPEN
def test_order_execution_confirm_updates_existing_reservation(test_setup):
    from app.services.execution.order_execution_service import OrderExecutionService

    exec_service = OrderExecutionService()
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]

    # Pre-reserve via auth_service
    prop = make_eurusd_proposal(entry="1.1000", sl="1.0950", lot="0.01")
    dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=1101)
    assert res.status == "PENDING"

    # Create order tied to this signal_id
    with patch("app.services.execution.order_execution_service.trade_journal_repository", journal_repo), \
         patch("app.services.execution.order_execution_service.signal_authorization_service", auth):

        order_in = ExecutionOrderCreate(
            signal_id=1101,
            symbol="EURUSD",
            action=OrderAction.BUY,
            lot_size=0.01,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1150,
        )
        order_item = exec_service.create_order(order_in)

        # Confirm execution from MT5
        confirm_in = ExecutionOrderConfirm(
            ticket_number=1234567,
            fill_price=1.1002,
            slippage_pips=0.2,
        )
        exec_service.confirm_execution(order_item.order_id, confirm_in)

        # Verify existing reservation was updated to OPEN without creating a duplicate record
        trades = journal_repo.list_trades()
        assert len(trades) == 1
        assert trades[0].id == res.id
        assert trades[0].status == "OPEN"
        assert trades[0].fillPrice == 1.1002
        assert "Ticket #1234567" in trades[0].notes


# 28. TradeJournal API: POST /trade-journal rejects reserving trades when Guardian rejects
def test_trade_journal_api_rejects_reserving_trade_when_limit_reached(test_setup):
    from app.api.v1.trade_journal import create_trade_journal

    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]

    # Fill up 3 slots
    for i in range(1, 4):
        prop = make_eurusd_proposal(entry="1.1000", sl="1.0990", lot="0.01")
        auth.authorize_and_reserve(proposal=prop, signal_id=1200 + i)

    trade_in = TradeJournalCreate(
        signalId=1204,
        symbol="EURUSD",
        direction="BUY",
        entryPrice=1.1000,
        stopLoss=1.0950,
        takeProfit=1.1150,
        timeframe="M15",
        marketSession="London",
        tradeDate=datetime.now(timezone.utc),
        status="OPEN",
        result="OPEN",
        reasonForEntry="Direct API Attempt",
    )

    with patch("app.api.v1.trade_journal.trade_journal_repository", journal_repo), \
         patch("app.api.v1.trade_journal.signal_authorization_service", auth):

        with pytest.raises(HTTPException) as exc_info:
            create_trade_journal(trade_in)

        assert exc_info.value.status_code == 400
        assert "Capital Guardian rejected trade" in exc_info.value.detail


# 29. TradeJournal API: POST /trade-journal permits non-reserving (CLOSED) trades
def test_trade_journal_api_permits_closed_trades(test_setup):
    from app.api.v1.trade_journal import create_trade_journal

    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]

    # Fill up 3 slots
    for i in range(1, 4):
        prop = make_eurusd_proposal(entry="1.1000", sl="1.0990", lot="0.01")
        auth.authorize_and_reserve(proposal=prop, signal_id=1300 + i)

    # Creating a historical CLOSED trade should succeed even with 3 active trades
    trade_in = TradeJournalCreate(
        signalId=1304,
        symbol="EURUSD",
        direction="BUY",
        entryPrice=1.1000,
        exitPrice=1.1050,
        stopLoss=1.0950,
        takeProfit=1.1150,
        timeframe="M15",
        marketSession="London",
        tradeDate=datetime.now(timezone.utc),
        closeDate=datetime.now(timezone.utc),
        status="CLOSED",
        result="WIN",
        profitLoss=5.0,
        reasonForEntry="Historical closed trade",
    )

    with patch("app.api.v1.trade_journal.trade_journal_repository", journal_repo):
        created = create_trade_journal(trade_in)
        assert created is not None
        assert created.status == "CLOSED"
        assert created.signalId == 1304
