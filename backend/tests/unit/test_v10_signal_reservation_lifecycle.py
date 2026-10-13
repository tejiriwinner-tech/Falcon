"""
Falcon V10 — Signal Reservation Lifecycle Defect Repair Test Suite

Comprehensive verification of:
1. Candidate authorization creates exactly 1 PENDING reservation.
2. Outcome resolver does NOT create duplicate OPEN rows for emitted signals.
3. Single signal_id has at most 1 active reservation.
4. PENDING reservation expires after 45 minutes (EXPIRED status, result=EXPIRED, closeDate set).
5. PENDING reservation remains active under 45 minutes.
6. PENDING reservation invalidated if market price breaches Stop Loss prior to entry.
7. Genuine execution (fillPrice populated or ticket #) is NEVER expired by 45m timeout.
8. Genuine execution remains OPEN until SL/TP boundary breach.
9. Capacity recovery: expiring or invalidating PENDING reservations frees Guardian capacity.
10. Guardian invariant: exactly 3 active trades blocks 4th candidate.
11. Strict inequality preserved: 2 active trades allows 3rd trade.
12. Equality rejection: active_count == 3 strictly rejects.
13. Duplicate signal_id reservation rejected idempotently by authorization.
14. PAPER mode isolation: paper reservations do not affect LIVE capital.
15. LIVE mode isolation: live reservations do not affect PAPER capital.
16. Signal Quality experiment remains non-blocking read-only evaluation.
17. Signal Quality monitoring remains non-blocking telemetry.
18. Broker safety: zero auto-execution, assert_no_broker_automation strictly raises.
19. Concurrency safety: 10 concurrent threads attempting reservation for same signal_id produces exactly 1 reservation.
20. Exact reproduction of historical defect (2 signals -> 4 reserving rows -> Guardian starvation).
21. Capacity recovery after defect resolution (4 reserving rows -> 0, allowing new candidate).
22. Authoritative classification of legacy records (classify_record forensic checks).
23. Preservation of UNKNOWN legacy records without mutation.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch
import pytest

from app.core.config.settings import settings
from app.core.execution.execution_mode_guard import ExecutionModeGuard, assert_no_broker_automation
from app.core.instruments.instrument_registry import instrument_registry
from app.core.providers.provider_manager import MarketQuoteResponse
from app.core.repository.capital_cycle_repository import (
    CapitalCycleRepository,
    InMemoryCapitalCycleStorage,
)
from app.core.repository.trade_journal_repository import (
    InMemoryTradeJournalStorage,
    TradeJournalRepository,
    trade_journal_repository,
)
from app.core.services.capital_cycle_service import CapitalCycleService
from app.core.services.capital_guardian_service import CapitalGuardianService
from app.core.services.signal_authorization_service import (
    FALCON_GUARDIAN_ADVISORY_LOCK_KEY,
    SignalAuthorizationService,
)
from app.core.services.signal_outcome_resolver import (
    LifecycleClassification,
    SignalOutcomeResolver,
    classify_record,
)
from app.core.analytics.signal_quality_experiment_service import signal_quality_experiment_service
from app.core.analytics.signal_quality_monitoring_service import signal_quality_monitoring_service
from app.schemas.capital_cycle import CapitalCycleCreate, CapitalCycleStatus
from app.schemas.capital_guardian import GuardianState, ProposedTradeInput
from app.schemas.market_quote import BidAsk, MarketQuote, MarketStatus, QuoteStatus
from app.schemas.signal_candidate import (
    CandidateCondition,
    CandidateDirection,
    CandidateMarketSnapshot,
    CandidateReason,
    CandidateStatus,
    ConfidenceBreakdown,
    SignalCandidate,
)
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalItem, TradeJournalUpdate


# -----------------------------------------------------------------------------
# Test Fixtures & Helpers
# -----------------------------------------------------------------------------

def make_mock_quote(symbol: str, price: float, spread: float = 0.0002) -> MarketQuoteResponse:
    return MarketQuoteResponse(
        quote=MarketQuote(
            symbol=symbol,
            bidAsk=BidAsk(bid=price, ask=price + spread, spread=spread),
            lastPrice=price,
            timestamp=datetime.now(timezone.utc),
            providerId="test_provider",
            providerName="Test Provider",
            quoteStatus=QuoteStatus.LIVE,
            marketStatus=MarketStatus.OPEN,
        )
    )


def make_eurusd_proposal(
    entry: str = "1.1000",
    sl: str = "1.0950",
    tp: str = "1.1100",
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


def make_trade_create(
    symbol: str = "EURUSD",
    direction: str = "BUY",
    entry_price: float = 1.1000,
    stop_loss: float = 1.0950,
    take_profit: float = 1.1100,
    lot_size: float = 0.01,
    status: str = "PENDING",
    signal_id: Optional[int] = None,
    trade_date: Optional[datetime] = None,
    fill_price: Optional[float] = None,
    fill_time: Optional[datetime] = None,
    notes: Optional[str] = "Auto-reserved from signal candidate",
    reason_for_entry: str = "Capital Guardian authorized reservation",
    execution_mode: Optional[str] = "LIVE",
) -> TradeJournalCreate:
    now = datetime.now(timezone.utc)
    return TradeJournalCreate(
        symbol=symbol,
        direction=direction,
        entryPrice=entry_price,
        stopLoss=stop_loss,
        takeProfit=take_profit,
        lotSize=lot_size,
        timeframe="H1",
        marketSession="London",
        status=status,
        result="OPEN" if status in ("OPEN", "PENDING") else status,
        signalId=signal_id,
        tradeDate=trade_date or now,
        fillPrice=fill_price,
        fillTime=fill_time,
        notes=notes,
        reasonForEntry=reason_for_entry,
        executionMode=execution_mode,
    )


def make_trade_item(
    id: int,
    symbol: str = "EURUSD",
    direction: str = "BUY",
    entry_price: float = 1.1650,
    stop_loss: float = 1.1620,
    take_profit: float = 1.1710,
    lot_size: float = 0.01,
    status: str = "PENDING",
    signal_id: Optional[int] = None,
    trade_date: Optional[datetime] = None,
    fill_price: Optional[float] = None,
    fill_time: Optional[datetime] = None,
    notes: Optional[str] = "Auto-reserved from signal candidate",
    reason_for_entry: str = "Capital Guardian authorized reservation",
    execution_mode: Optional[str] = "LIVE",
) -> TradeJournalItem:
    now = trade_date or datetime.now(timezone.utc)
    return TradeJournalItem(
        id=id,
        symbol=symbol,
        direction=direction,
        entryPrice=entry_price,
        stopLoss=stop_loss,
        takeProfit=take_profit,
        lotSize=lot_size,
        timeframe="H1",
        marketSession="London",
        status=status,
        result="OPEN" if status in ("OPEN", "PENDING") else status,
        signalId=signal_id,
        tradeDate=now,
        createdAt=now,
        updatedAt=now,
        fillPrice=fill_price,
        fillTime=fill_time,
        notes=notes,
        reasonForEntry=reason_for_entry,
        executionMode=execution_mode,
    )


def make_candidate(
    candidate_id: str = "cand-001",
    symbol: str = "EURUSD",
    direction: CandidateDirection = CandidateDirection.BUY,
    entry: float = 1.1000,
    sl: float = 1.0950,
    tp: float = 1.1100,
) -> SignalCandidate:
    now = datetime.now(timezone.utc)
    return SignalCandidate(
        id=candidate_id,
        symbol=symbol,
        strategyId="london_momentum",
        strategyName="London Momentum",
        strategyVersion="1.0.0",
        strategyGrade="A",
        strategyScore=85,
        direction=direction,
        confidence=80,
        readinessScore=85,
        entryPrice=entry,
        stopLoss=sl,
        takeProfit=tp,
        riskReward=2.0,
        status=CandidateStatus.APPROVED,
        generatedAt=now,
        reasons=[CandidateReason(title="Trend", description="Bullish trend", passed=True)],
        conditions=[CandidateCondition(title="Spread", description="Spread OK", passed=True)],
        marketSnapshot=CandidateMarketSnapshot(
            trend="Bullish",
            volatility="Moderate",
            session="London",
            spread=1.2,
            newsImpact="Low",
            marketSentiment="Bullish",
            marketConfidence=85,
            atr=0.0015,
        ),
        confidenceBreakdown=ConfidenceBreakdown(
            trendScore=85,
            strategyScore=80,
            sessionScore=85,
            sentimentScore=80,
            newsScore=90,
        ),
        evaluationDurationMs=15,
        marketDataAgeSeconds=5,
        evaluationStartedAt=now,
        evaluationCompletedAt=now,
    )


@pytest.fixture
def test_setup():
    """Provides isolated in-memory repositories and services for testing."""
    cycle_storage = InMemoryCapitalCycleStorage()
    journal_storage = InMemoryTradeJournalStorage()

    cycle_repo = CapitalCycleRepository(storage=cycle_storage)
    journal_repo = TradeJournalRepository(storage=journal_storage)

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
            cycleId="cycle-v10-lifecycle-001",
            cycleNumber=1,
            startingCapital=Decimal("20.00"),
            targetCapital=Decimal("50.00"),
            activeTradingCapital=Decimal("20.00"),
            protectedProfit=Decimal("0.00"),
            status=CapitalCycleStatus.ACTIVE,
            startedAt=datetime.now(timezone.utc) - timedelta(days=7),
        )
    )

    # Global trade_journal_repository redirection
    orig_storage = trade_journal_repository._storage
    trade_journal_repository._storage = journal_storage
    trade_journal_repository._invalidate_cache()

    yield {
        "cycle_storage": cycle_storage,
        "journal_storage": journal_storage,
        "cycle_repo": cycle_repo,
        "journal_repo": journal_repo,
        "cycle_service": cycle_service,
        "guardian_service": guardian_service,
        "auth_service": auth_service,
        "active_cycle": active_cycle,
    }

    trade_journal_repository._storage = orig_storage
    trade_journal_repository._invalidate_cache()


# -----------------------------------------------------------------------------
# 1. Authorize Candidate Creates 1 PENDING Reservation
# -----------------------------------------------------------------------------
def test_authorize_candidate_creates_one_pending_reservation(test_setup):
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]

    prop = make_eurusd_proposal(entry="1.1000", sl="1.0950", lot="0.01")  # $5 risk <= $20 capital
    decision, res = auth.authorize_and_reserve(proposal=prop, signal_id=101)

    assert decision.allowed is True
    assert decision.state == GuardianState.NORMAL
    assert res is not None
    assert res.signalId == 101
    assert res.status == "PENDING"
    assert res.symbol == "EURUSD"

    trades = journal_repo.list_trades()
    assert len(trades) == 1
    assert trades[0].signalId == 101
    assert trades[0].status == "PENDING"


# -----------------------------------------------------------------------------
# 2. Outcome Resolver Does NOT Create Duplicate OPEN Row
# -----------------------------------------------------------------------------
def test_outcome_resolver_does_not_create_duplicate_open_row(test_setup):
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]

    # Step 1: Authorize candidate -> creates PENDING reservation
    prop = make_eurusd_proposal(entry="1.1000", sl="1.0950", lot="0.01")
    auth.authorize_and_reserve(proposal=prop, signal_id=102)

    assert len(journal_repo.list_trades()) == 1

    # Mock signal_service.build_signals returning this active signal
    mock_sig = MagicMock(
        id=102,
        symbol="EURUSD",
        action="BUY",
        entry=1.1000,
        stopLoss=1.0950,
        takeProfit=1.1100,
        timeframe="H1",
        strategyId="london_momentum",
        strategyName="London Momentum",
        timestamp=datetime.now(timezone.utc),
    )

    resolver = SignalOutcomeResolver()
    with patch("app.core.services.signal_outcome_resolver.database_enabled", return_value=False), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[mock_sig])), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=make_mock_quote("EURUSD", 1.1000)):
        
        summary = resolver.resolve_signals()

    trades = journal_repo.list_trades()
    # Verified: NO second row created! Still exactly 1 row, and still PENDING.
    assert len(trades) == 1
    assert trades[0].signalId == 102
    assert trades[0].status == "PENDING"


# -----------------------------------------------------------------------------
# 3. Single signal_id Has At Most 1 Active Reservation (Idempotency)
# -----------------------------------------------------------------------------
def test_single_signal_id_at_most_one_active_reservation(test_setup):
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]

    prop = make_eurusd_proposal(entry="1.1000", sl="1.0950", lot="0.01")
    dec1, res1 = auth.authorize_and_reserve(proposal=prop, signal_id=103)
    assert dec1.allowed is True
    assert res1 is not None

    # Try authorizing the exact same signal_id again
    dec2, res2 = auth.authorize_and_reserve(proposal=prop, signal_id=103)
    assert dec2.allowed is True
    assert "already reserved" in dec2.reason.lower()
    assert res2 is not None
    assert res2.id == res1.id

    trades = [t for t in journal_repo.list_trades() if t.signalId == 103]
    assert len(trades) == 1


# -----------------------------------------------------------------------------
# 4. PENDING Reservation Expires After 45 Minutes
# -----------------------------------------------------------------------------
def test_pending_reservation_expires_after_45_minutes(test_setup):
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(minutes=50)

    trade = journal_repo.create_trade(
        make_trade_create(
            symbol="EURUSD",
            direction="BUY",
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            status="PENDING",
            signal_id=104,
            trade_date=old_time,
            notes="Auto-reserved from signal candidate",
            reason_for_entry="Capital Guardian authorized reservation",
        )
    )

    resolver = SignalOutcomeResolver()
    with patch("app.core.services.signal_outcome_resolver.database_enabled", return_value=False), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=make_mock_quote("EURUSD", 1.1000)):
        
        summary = resolver.resolve_signals()

    updated = journal_repo.get_trade(trade.id)
    assert updated.status == "EXPIRED"
    assert updated.result == "EXPIRED"
    assert updated.closeDate is not None
    assert "45m" in updated.reasonForExit


# -----------------------------------------------------------------------------
# 5. PENDING Reservation Remains Active Under 45 Minutes
# -----------------------------------------------------------------------------
def test_pending_reservation_not_expired_under_45_minutes(test_setup):
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)
    recent_time = now - timedelta(minutes=20)

    trade = journal_repo.create_trade(
        make_trade_create(
            symbol="EURUSD",
            direction="BUY",
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            status="PENDING",
            signal_id=105,
            trade_date=recent_time,
            notes="Auto-reserved from signal candidate",
        )
    )

    resolver = SignalOutcomeResolver()
    with patch("app.core.services.signal_outcome_resolver.database_enabled", return_value=False), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=make_mock_quote("EURUSD", 1.1000)):
        
        summary = resolver.resolve_signals()

    updated = journal_repo.get_trade(trade.id)
    assert updated.status == "PENDING"
    assert updated.closeDate is None


# -----------------------------------------------------------------------------
# 6. PENDING Reservation Invalidated If Stop Loss Breached Prior to Entry
# -----------------------------------------------------------------------------
def test_pending_reservation_invalidated_if_stop_loss_breached_prior_to_entry(test_setup):
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)
    recent_time = now - timedelta(minutes=10)

    trade = journal_repo.create_trade(
        make_trade_create(
            symbol="EURUSD",
            direction="BUY",
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            status="PENDING",
            signal_id=106,
            trade_date=recent_time,
            notes="Auto-reserved from signal candidate",
        )
    )

    resolver = SignalOutcomeResolver()
    # Market quote drops below SL (1.0950) to 1.0940
    with patch("app.core.services.signal_outcome_resolver.database_enabled", return_value=False), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=make_mock_quote("EURUSD", 1.0940)):
        
        summary = resolver.resolve_signals()

    updated = journal_repo.get_trade(trade.id)
    assert updated.status == "INVALIDATED"
    assert updated.result == "INVALIDATED"
    assert updated.closeDate is not None
    assert "breached stop loss" in updated.reasonForExit.lower()


# -----------------------------------------------------------------------------
# 7. Genuine Execution Never Expired by 45m Timeout
# -----------------------------------------------------------------------------
def test_genuine_execution_never_expired_by_45m_timeout(test_setup):
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=3)

    # Genuine execution with fillPrice populated
    trade = journal_repo.create_trade(
        make_trade_create(
            symbol="EURUSD",
            direction="BUY",
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            status="OPEN",
            fill_price=1.1002,
            fill_time=old_time,
            signal_id=107,
            trade_date=old_time,
            notes="Manual MT5 execution confirmed",
        )
    )

    resolver = SignalOutcomeResolver()
    # Current quote at 1.1030 (between SL and TP)
    with patch("app.core.services.signal_outcome_resolver.database_enabled", return_value=False), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=make_mock_quote("EURUSD", 1.1030)):
        
        summary = resolver.resolve_signals()

    updated = journal_repo.get_trade(trade.id)
    assert updated.status == "OPEN"
    assert updated.closeDate is None


# -----------------------------------------------------------------------------
# 8. Genuine Execution Remains OPEN Until SL/TP Breach
# -----------------------------------------------------------------------------
def test_genuine_execution_remains_open_until_tp_or_sl(test_setup):
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)

    trade = journal_repo.create_trade(
        make_trade_create(
            symbol="EURUSD",
            direction="BUY",
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            status="OPEN",
            fill_price=1.1000,
            fill_time=now,
            signal_id=108,
            trade_date=now,
        )
    )

    resolver = SignalOutcomeResolver()

    # Quote 1: 1.1050 (inside boundaries) -> stays OPEN
    with patch("app.core.services.signal_outcome_resolver.database_enabled", return_value=False), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=make_mock_quote("EURUSD", 1.1050)):
        
        resolver.resolve_signals()
        assert journal_repo.get_trade(trade.id).status == "OPEN"

    # Quote 2: 1.1105 (Take Profit hit) -> resolves to WIN / CLOSED
    with patch("app.core.services.signal_outcome_resolver.database_enabled", return_value=False), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=make_mock_quote("EURUSD", 1.1105)):
        
        summary = resolver.resolve_signals()
        assert summary.winsCount == 1

        resolved = journal_repo.get_trade(trade.id)
        assert resolved.status == "CLOSED"
        assert resolved.result == "WIN"
        assert resolved.closeDate is not None


# -----------------------------------------------------------------------------
# 9. Capacity Recovery on PENDING Expiration
# -----------------------------------------------------------------------------
def test_capacity_recovery_on_pending_expiration(test_setup):
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)

    # Create 3 reservations (filling limit to 3)
    t1 = journal_repo.create_trade(
        make_trade_create(
            symbol="EURUSD", direction="BUY", entry_price=1.1000, stop_loss=1.0950,
            take_profit=1.1100, status="PENDING", signal_id=111,
            trade_date=now - timedelta(minutes=50), # Expired!
        )
    )
    t2 = journal_repo.create_trade(
        make_trade_create(
            symbol="EURUSD", direction="BUY", entry_price=1.1000, stop_loss=1.0950,
            take_profit=1.1100, status="PENDING", signal_id=112,
            trade_date=now,
        )
    )
    t3 = journal_repo.create_trade(
        make_trade_create(
            symbol="EURUSD", direction="BUY", entry_price=1.1000, stop_loss=1.0950,
            take_profit=1.1100, status="PENDING", signal_id=113,
            trade_date=now,
        )
    )

    # Active count is 3 -> 4th trade rejected before expiration
    prop = make_eurusd_proposal(entry="1.1000", sl="1.0950", lot="0.01")
    dec_before, _ = auth.authorize_and_reserve(proposal=prop, signal_id=114)
    assert dec_before.allowed is False

    # Run resolver -> t1 expires
    resolver = SignalOutcomeResolver()
    with patch("app.core.services.signal_outcome_resolver.database_enabled", return_value=False), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=make_mock_quote("EURUSD", 1.1000)):
        
        resolver.resolve_signals()

    assert journal_repo.get_trade(t1.id).status == "EXPIRED"

    # Now active count is 2 -> authorization succeeds!
    dec_after, res_after = auth.authorize_and_reserve(proposal=prop, signal_id=114)
    assert dec_after.allowed is True
    assert res_after is not None
    assert res_after.signalId == 114


# -----------------------------------------------------------------------------
# 10. Guardian Blocks When MAX_SIMULTANEOUS_TRADES Reached
# -----------------------------------------------------------------------------
def test_guardian_blocks_when_max_simultaneous_trades_reached(test_setup):
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)

    for i in range(1, 4):
        journal_repo.create_trade(
            make_trade_create(
                symbol="EURUSD", direction="BUY", entry_price=1.1000, stop_loss=1.0950,
                take_profit=1.1100, status="PENDING", signal_id=120 + i,
                trade_date=now,
            )
        )

    prop = make_eurusd_proposal()
    decision, res = auth.authorize_and_reserve(proposal=prop, signal_id=124)
    assert decision.allowed is False
    assert "simultaneous" in decision.reason.lower() or "limit" in decision.reason.lower()


# -----------------------------------------------------------------------------
# 11. Guardian Strict Inequality Allows Under Max
# -----------------------------------------------------------------------------
def test_guardian_strict_inequality_allows_under_max(test_setup):
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)

    # 2 active trades
    for i in range(1, 3):
        journal_repo.create_trade(
            make_trade_create(
                symbol="EURUSD", direction="BUY", entry_price=1.1000, stop_loss=1.0950,
                take_profit=1.1100, status="PENDING", signal_id=130 + i,
                trade_date=now,
            )
        )

    prop = make_eurusd_proposal()
    decision, res = auth.authorize_and_reserve(proposal=prop, signal_id=133)
    assert decision.allowed is True
    assert res is not None


# -----------------------------------------------------------------------------
# 12. Guardian Equality Rejection (active == 3 -> Rejected)
# -----------------------------------------------------------------------------
def test_guardian_equality_rejected(test_setup):
    guardian = test_setup["guardian_service"]
    journal_repo = test_setup["journal_repo"]
    active_cycle = test_setup["active_cycle"]
    now = datetime.now(timezone.utc)

    for i in range(1, 4):
        journal_repo.create_trade(
            make_trade_create(
                symbol="EURUSD", direction="BUY", entry_price=1.1000, stop_loss=1.0950,
                take_profit=1.1100, status="PENDING", signal_id=140 + i,
                trade_date=now,
            )
        )

    active_trades = guardian.get_capital_reserving_trades(active_cycle=active_cycle)
    assert len(active_trades) == 3

    prop = make_eurusd_proposal()
    decision = guardian.evaluate_proposed_trade(
        proposal=prop,
        active_cycle=active_cycle,
        active_trades=active_trades,
    )
    assert decision.allowed is False


# -----------------------------------------------------------------------------
# 13. Duplicate signal_id Reservation Rejected Idempotently
# -----------------------------------------------------------------------------
def test_duplicate_signal_id_reservation_rejected_idempotently(test_setup):
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]
    prop = make_eurusd_proposal()

    dec1, res1 = auth.authorize_and_reserve(proposal=prop, signal_id=150)
    assert dec1.allowed is True
    assert res1 is not None

    dec2, res2 = auth.authorize_and_reserve(proposal=prop, signal_id=150)
    assert dec2.allowed is True
    assert res2.id == res1.id
    assert "already reserved" in dec2.reason.lower()

    trades = [t for t in journal_repo.list_trades() if t.signalId == 150]
    assert len(trades) == 1


# -----------------------------------------------------------------------------
# 14. PAPER Mode Isolation
# -----------------------------------------------------------------------------
def test_paper_mode_isolation(test_setup):
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)

    # Create 3 PAPER reservations
    for i in range(1, 4):
        journal_repo.create_trade(
            make_trade_create(
                symbol="EURUSD", direction="BUY", entry_price=1.1000, stop_loss=1.0950,
                take_profit=1.1100, status="PENDING", signal_id=160 + i,
                execution_mode="PAPER",
                trade_date=now,
            )
        )

    # LIVE active reservations query must return 0
    live_res = auth.get_active_reservations(execution_mode="LIVE")
    assert len(live_res) == 0

    # LIVE authorization must succeed despite 3 PAPER trades
    prop = make_eurusd_proposal()
    dec, res = auth.authorize_and_reserve(proposal=prop, signal_id=165, execution_mode="LIVE")
    assert dec.allowed is True
    assert res is not None


# -----------------------------------------------------------------------------
# 15. LIVE Mode Isolation
# -----------------------------------------------------------------------------
def test_live_mode_isolation(test_setup):
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)

    # Create 3 LIVE reservations
    for i in range(1, 4):
        journal_repo.create_trade(
            make_trade_create(
                symbol="EURUSD", direction="BUY", entry_price=1.1000, stop_loss=1.0950,
                take_profit=1.1100, status="PENDING", signal_id=170 + i,
                execution_mode="LIVE",
                trade_date=now,
            )
        )

    # PAPER active reservations query must return 0
    paper_res = auth.get_active_reservations(execution_mode="PAPER")
    assert len(paper_res) == 0


# -----------------------------------------------------------------------------
# 16. Signal Quality Experiment Remains Non-Blocking
# -----------------------------------------------------------------------------
def test_signal_quality_experiment_remains_non_blocking(test_setup):
    journal_repo = test_setup["journal_repo"]
    cand = make_candidate(candidate_id="sq-exp-001")

    # Evaluate candidate via experiment
    eval_item = signal_quality_experiment_service.evaluate_candidate(cand)
    assert eval_item is not None
    assert eval_item.candidateId == "sq-exp-001"

    # Journal remains completely untouched
    assert len(journal_repo.list_trades()) == 0


# -----------------------------------------------------------------------------
# 17. Signal Quality Monitoring Remains Non-Blocking
# -----------------------------------------------------------------------------
def test_signal_quality_monitoring_remains_non_blocking(test_setup):
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)

    # Record counterfactual outcome
    outcome = signal_quality_monitoring_service.record_counterfactual_outcome(
        candidate_id="sq-mon-001",
        would_have_won=True,
        closed_at=now,
        evaluation_source="research_backtest",
        evidence={"quote": 1.1020},
    )
    assert outcome is not None
    # Journal remains untouched
    assert len(journal_repo.list_trades()) == 0


# -----------------------------------------------------------------------------
# 18. Broker Safety: Zero Automation & Invariant Check
# -----------------------------------------------------------------------------
def test_broker_safety_zero_automation():
    # Must enforce assert_no_broker_automation
    with pytest.raises(RuntimeError, match="automated broker execution is strictly prohibited"):
        assert_no_broker_automation("Direct safety probe")

    with pytest.raises(RuntimeError, match="automated broker execution is strictly prohibited"):
        ExecutionModeGuard.assert_no_broker_automation("Class safety probe")


# -----------------------------------------------------------------------------
# 19. Concurrency Safety: 10 Threads Attempting Same signal_id
# -----------------------------------------------------------------------------
def test_concurrency_safety_same_signal_id(test_setup):
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]
    prop = make_eurusd_proposal()
    signal_id = 999

    def try_reserve():
        return auth.authorize_and_reserve(proposal=prop, signal_id=signal_id)

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_reserve) for _ in range(10)]
        for f in as_completed(futures):
            results.append(f.result())

    # All decisions are allowed (either first reservation or idempotent return of existing)
    for dec, res in results:
        assert dec.allowed is True
        assert res is not None
        assert res.signalId == signal_id

    # Exactly 1 trade row was created in the journal
    matching_trades = [t for t in journal_repo.list_trades() if t.signalId == signal_id]
    assert len(matching_trades) == 1


# -----------------------------------------------------------------------------
# 20. Exact Reproduction of Historical Defect
# -----------------------------------------------------------------------------
def test_exact_reproduction_of_historical_defect(test_setup):
    """
    Exact simulation of the historical defect state:
    2 signals produced 4 reserving trade_journal rows:
    - Signal #340304: #2482 (PENDING) & #2485 (OPEN duplicate)
    - Signal #340306: #2483 (PENDING) & #2486 (OPEN duplicate)
    Active count = 4, permanently starving Guardian capacity (limit = 3).
    """
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)
    t_historical = now - timedelta(hours=9)

    # 1. Row #2482: PENDING
    journal_repo.create_trade(
        make_trade_create(
            symbol="EURUSD", direction="BUY", entry_price=1.1650, stop_loss=1.1620,
            take_profit=1.1710, status="PENDING", signal_id=340304,
            trade_date=t_historical, notes="Auto-reserved from signal candidate",
            reason_for_entry="Capital Guardian authorized reservation",
        )
    )
    # 2. Row #2485: Speculative OPEN duplicate created by old resolver
    journal_repo.create_trade(
        make_trade_create(
            symbol="EURUSD", direction="BUY", entry_price=1.1650, stop_loss=1.1620,
            take_profit=1.1710, status="OPEN", signal_id=340304,
            trade_date=t_historical + timedelta(seconds=1),
            notes="Active signal monitored by Falcon (London Momentum)",
            reason_for_entry="Active signal monitored by Falcon",
        )
    )
    # 3. Row #2483: PENDING
    journal_repo.create_trade(
        make_trade_create(
            symbol="GBPUSD", direction="BUY", entry_price=1.3500, stop_loss=1.3450,
            take_profit=1.3600, status="PENDING", signal_id=340306,
            trade_date=t_historical, notes="Auto-reserved from signal candidate",
            reason_for_entry="Capital Guardian authorized reservation",
        )
    )
    # 4. Row #2486: Speculative OPEN duplicate created by old resolver
    journal_repo.create_trade(
        make_trade_create(
            symbol="GBPUSD", direction="BUY", entry_price=1.3500, stop_loss=1.3450,
            take_profit=1.3600, status="OPEN", signal_id=340306,
            trade_date=t_historical + timedelta(seconds=1),
            notes="Active signal monitored by Falcon (European Breakout)",
            reason_for_entry="Active signal monitored by Falcon",
        )
    )

    # Verify Guardian active count is 4
    active_res = auth.get_active_reservations(execution_mode="LIVE")
    assert len(active_res) == 4

    # Any new candidate is blocked!
    prop = make_eurusd_proposal()
    decision, _ = auth.authorize_and_reserve(proposal=prop, signal_id=340308)
    assert decision.allowed is False


# -----------------------------------------------------------------------------
# 21. Capacity Recovery After Defect Resolution
# -----------------------------------------------------------------------------
def test_capacity_recovery_after_defect_resolution(test_setup):
    """
    Running SignalOutcomeResolver on the historical defect state
    classifies and expires all 4 unexecuted rows, dropping active count
    from 4 to 0, restoring full Guardian capacity.
    """
    auth = test_setup["auth_service"]
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)
    t_historical = now - timedelta(hours=9)

    journal_repo.create_trade(
        make_trade_create(
            symbol="EURUSD", direction="BUY", entry_price=1.1650, stop_loss=1.1620,
            take_profit=1.1710, status="PENDING", signal_id=340304,
            trade_date=t_historical, notes="Auto-reserved from signal candidate",
            reason_for_entry="Capital Guardian authorized reservation",
        )
    )
    journal_repo.create_trade(
        make_trade_create(
            symbol="EURUSD", direction="BUY", entry_price=1.1650, stop_loss=1.1620,
            take_profit=1.1710, status="OPEN", signal_id=340304,
            trade_date=t_historical + timedelta(seconds=1),
            notes="Active signal monitored by Falcon (London Momentum)",
            reason_for_entry="Active signal monitored by Falcon",
        )
    )
    journal_repo.create_trade(
        make_trade_create(
            symbol="GBPUSD", direction="BUY", entry_price=1.3500, stop_loss=1.3450,
            take_profit=1.3600, status="PENDING", signal_id=340306,
            trade_date=t_historical, notes="Auto-reserved from signal candidate",
            reason_for_entry="Capital Guardian authorized reservation",
        )
    )
    journal_repo.create_trade(
        make_trade_create(
            symbol="GBPUSD", direction="BUY", entry_price=1.3500, stop_loss=1.3450,
            take_profit=1.3600, status="OPEN", signal_id=340306,
            trade_date=t_historical + timedelta(seconds=1),
            notes="Active signal monitored by Falcon (European Breakout)",
            reason_for_entry="Active signal monitored by Falcon",
        )
    )

    resolver = SignalOutcomeResolver()
    with patch("app.core.services.signal_outcome_resolver.database_enabled", return_value=False), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=make_mock_quote("EURUSD", 1.1650)):
        
        summary = resolver.resolve_signals()

    # Verify all 4 rows are expired
    all_trades = journal_repo.list_trades()
    assert len(all_trades) == 4
    for t in all_trades:
        assert t.status == "EXPIRED"
        assert t.result == "EXPIRED"

    # Active reservations count drops from 4 to 0
    active_res = auth.get_active_reservations(execution_mode="LIVE")
    assert len(active_res) == 0

    # Candidate authorization now succeeds!
    prop = make_eurusd_proposal()
    decision, res = auth.authorize_and_reserve(proposal=prop, signal_id=340308)
    assert decision.allowed is True
    assert res is not None
    assert res.signalId == 340308


# -----------------------------------------------------------------------------
# 22. Authoritative Classification of Legacy Records
# -----------------------------------------------------------------------------
def test_authoritative_classification_of_legacy_records():
    now = datetime.now(timezone.utc)

    # 1. PENDING reservation
    t_pending = make_trade_item(
        id=2482, symbol="EURUSD", direction="BUY", entry_price=1.1650, stop_loss=1.1620,
        take_profit=1.1710, status="PENDING", signal_id=340304,
        trade_date=now, notes="Auto-reserved from signal candidate",
        reason_for_entry="Capital Guardian authorized reservation",
    )
    # 2. Speculative OPEN duplicate
    t_dup = make_trade_item(
        id=2485, symbol="EURUSD", direction="BUY", entry_price=1.1650, stop_loss=1.1620,
        take_profit=1.1710, status="OPEN", signal_id=340304,
        trade_date=now, notes="Active signal monitored by Falcon (London Momentum)",
        reason_for_entry="Active signal monitored by Falcon",
    )
    # 3. Genuine execution with fillPrice
    t_genuine_fill = make_trade_item(
        id=2487, symbol="EURUSD", direction="BUY", entry_price=1.1650, stop_loss=1.1620,
        take_profit=1.1710, status="OPEN", fill_price=1.1652,
        trade_date=now,
    )
    # 4. Genuine execution with ticket note
    t_genuine_ticket = make_trade_item(
        id=2488, symbol="EURUSD", direction="BUY", entry_price=1.1650, stop_loss=1.1620,
        take_profit=1.1710, status="OPEN", notes="Ticket #8847192 executed",
        trade_date=now,
    )
    # 5. Ambiguous record without provenance
    t_unknown = make_trade_item(
        id=2489, symbol="EURUSD", direction="BUY", entry_price=1.1650, stop_loss=1.1620,
        take_profit=1.1710, status="OPEN", notes="Some random trade",
        trade_date=now,
    )

    all_list = [t_pending, t_dup, t_genuine_fill, t_genuine_ticket, t_unknown]

    assert classify_record(t_pending, all_list) == LifecycleClassification.LEGACY_UNEXECUTED_RESERVATION
    assert classify_record(t_dup, all_list) == LifecycleClassification.DUPLICATE_SPECULATIVE_EXECUTION
    assert classify_record(t_genuine_fill, all_list) == LifecycleClassification.LEGITIMATE_ACTUAL_EXECUTION
    assert classify_record(t_genuine_ticket, all_list) == LifecycleClassification.LEGITIMATE_ACTUAL_EXECUTION
    assert classify_record(t_unknown, all_list) == LifecycleClassification.UNKNOWN


# -----------------------------------------------------------------------------
# 23. Preservation of UNKNOWN Legacy Records Without Mutation
# -----------------------------------------------------------------------------
def test_preservation_of_unknown_records_without_mutation(test_setup):
    journal_repo = test_setup["journal_repo"]
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=5)

    # Insert an UNKNOWN legacy record: OPEN, no fill, but no paired reservation & no resolver signature
    trade = journal_repo.create_trade(
        make_trade_create(
            symbol="EURUSD",
            direction="BUY",
            entry_price=1.1650,
            stop_loss=1.1620,
            take_profit=1.1710,
            status="OPEN",
            fill_price=None,
            fill_time=None,
            signal_id=999999,
            trade_date=old_time,
            notes="Manual inspection needed — provenance unclear",
            reason_for_entry="Unknown origin",
        )
    )

    resolver = SignalOutcomeResolver()
    # Market quote within boundaries
    with patch("app.core.services.signal_outcome_resolver.database_enabled", return_value=False), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=make_mock_quote("EURUSD", 1.1660)):
        
        summary = resolver.resolve_signals()

    # Record must be untouched!
    untouched = journal_repo.get_trade(trade.id)
    assert untouched.status == "OPEN"
    assert untouched.closeDate is None
    assert "Manual inspection needed" in untouched.notes
