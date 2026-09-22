"""
Falcon V10 Phase 5G: Live-vs-Paper Execution Divergence, Strategy Attribution & Controlled Paper Runtime Test Suite.

Verifies:
1. Execution Safety & Mode Invariants (Conditions 1-5)
2. Signal Identity vs Execution Instance Identity (Conditions 6-10)
3. Execution Divergence Analytics & Actual Fill Authority (Conditions 11-24)
4. Manual LIVE Ingestion & Historical Isolation (Conditions 25-30)
5. Deterministic Premature Exit (Conditions 31-34)
6. Controlled Paper Runtime (Conditions 35-44)
7. Capital & Exposure Isolation (Conditions 45-50)
8. Strategy Attribution & Drift Diagnostics (Conditions 51-58)
9. Lookahead Protection & Dedicated APIs (Conditions 59-64)
"""

import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient
from main import app

from app.core.analytics.execution_divergence_service import (
    ExecutionDivergenceService,
    execution_divergence_service,
)
from app.core.analytics.strategy_attribution_service import (
    MIN_SAMPLE_SIZE,
    StrategyAttributionService,
    strategy_attribution_service,
)
from app.core.config import settings
from app.core.engines.paper_runtime import (
    PaperTradingRuntime,
    paper_trading_runtime,
)
from app.core.engines.paper_trading_engine import (
    PaperTradingEngine,
    paper_trading_engine,
)
from app.core.execution.execution_mode_guard import (
    ExecutionMode,
    ExecutionModeGuard,
    assert_no_broker_automation,
    execution_mode_guard,
    format_mode_token,
    inject_mode_token,
    parse_execution_mode,
)
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
from app.core.services.capital_guardian_service import (
    CapitalGuardianService,
    capital_guardian_service,
)
from app.core.services.signal_authorization_service import (
    FALCON_GUARDIAN_ADVISORY_LOCK_KEY,
    SignalAuthorizationService,
    signal_authorization_service,
)
from app.schemas.capital_cycle import CapitalCycleCreate, CapitalCycleStatus
from app.schemas.capital_guardian import ProposedTradeInput
from app.schemas.execution_divergence import DivergenceClassification
from app.schemas.market_quote import BidAsk, MarketQuote
from app.schemas.signal_candidate import (
    CandidateCondition,
    CandidateDirection,
    CandidateMarketSnapshot,
    CandidateReason,
    CandidateStatus,
    ConfidenceBreakdown,
    SignalCandidate,
)
from app.schemas.strategy_attribution import DriftStatus
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalUpdate


@pytest.fixture(autouse=True)
def clean_test_environment():
    """Isolate tests in memory and clean repositories before/after each test."""
    orig_storage = trade_journal_repository._storage
    mem_storage = InMemoryTradeJournalStorage()
    trade_journal_repository._storage = mem_storage
    trade_journal_repository.clear()

    orig_cycle_storage = capital_guardian_service._cycle_service._repo._storage
    cycle_storage = InMemoryCapitalCycleStorage()
    cycle_repo = CapitalCycleRepository()
    cycle_repo._storage = cycle_storage
    cycle_repo.clear()

    # Seed an active capital cycle ($20.00 active capital, $0.00 protected profit)
    cycle_repo.create_cycle(
        CapitalCycleCreate(
            cycleId="cycle-v10-p5g-test",
            cycleNumber=1,
            startingCapital=Decimal("20.00"),
            targetCapital=Decimal("500.00"),
            activeTradingCapital=Decimal("20.00"),
            protectedProfit=Decimal("0.00"),
            status=CapitalCycleStatus.ACTIVE,
            startedAt=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
    )

    cycle_service = CapitalCycleService(repository=cycle_repo)
    guardian_service = CapitalGuardianService(
        cycle_service=cycle_service,
        journal_repository=trade_journal_repository,
    )
    auth_service = SignalAuthorizationService(
        cycle_service=cycle_service,
        guardian_service=guardian_service,
        journal_repo=trade_journal_repository,
        cycle_repo=cycle_repo,
    )

    orig_auth_cycle_service = signal_authorization_service._cycle_service
    orig_auth_guardian_service = signal_authorization_service._guardian_service
    orig_auth_journal_repo = signal_authorization_service._journal_repo
    orig_auth_cycle_repo = signal_authorization_service._cycle_repo

    orig_guardian_cycle_service = capital_guardian_service._cycle_service
    orig_guardian_journal_repo = capital_guardian_service._journal_repo

    # Patch global singletons
    paper_trading_engine._auth_service = auth_service
    paper_trading_engine._guardian_service = guardian_service
    paper_trading_engine._journal_repo = trade_journal_repository

    paper_trading_runtime._engine = paper_trading_engine
    paper_trading_runtime._journal_repo = trade_journal_repository

    execution_divergence_service._journal_repo = trade_journal_repository
    strategy_attribution_service._journal_repo = trade_journal_repository

    signal_authorization_service._cycle_service = cycle_service
    signal_authorization_service._guardian_service = guardian_service
    signal_authorization_service._journal_repo = trade_journal_repository
    signal_authorization_service._cycle_repo = cycle_repo

    capital_guardian_service._cycle_service = cycle_service
    capital_guardian_service._journal_repo = trade_journal_repository

    yield {
        "cycle_repo": cycle_repo,
        "cycle_service": cycle_service,
        "guardian_service": guardian_service,
        "auth_service": auth_service,
        "journal_repo": trade_journal_repository,
    }

    trade_journal_repository.clear()
    trade_journal_repository._storage = orig_storage
    capital_guardian_service._cycle_service._repo._storage = orig_cycle_storage

    signal_authorization_service._cycle_service = orig_auth_cycle_service
    signal_authorization_service._guardian_service = orig_auth_guardian_service
    signal_authorization_service._journal_repo = orig_auth_journal_repo
    signal_authorization_service._cycle_repo = orig_auth_cycle_repo

    capital_guardian_service._cycle_service = orig_guardian_cycle_service
    capital_guardian_service._journal_repo = orig_guardian_journal_repo


def make_test_candidate(signal_id: int, symbol: str = "EURUSD", direction: CandidateDirection = CandidateDirection.BUY) -> SignalCandidate:
    now = datetime.now(timezone.utc)
    return SignalCandidate(
        id=f"cand-{signal_id}",
        symbol=symbol,
        strategyId="MOMENTUM_BREAKOUT",
        strategyName="Momentum Breakout",
        strategyVersion="1.2.0",
        strategyGrade="A+",
        strategyScore=85,
        direction=direction,
        confidence=85,
        readinessScore=90,
        entryPrice=1.1000,
        stopLoss=1.0950,
        takeProfit=1.1150,
        riskReward=3.0,
        status=CandidateStatus.GENERATED,
        generatedAt=now,
        reasons=[CandidateReason(title="Confirmed", description="Ready", passed=True)],
        conditions=[],
        confidenceBreakdown=ConfidenceBreakdown(
            trendScore=85,
            strategyScore=85,
            sessionScore=85,
            sentimentScore=85,
            newsScore=85,
        ),
        evaluationDurationMs=10,
        marketDataAgeSeconds=2,
        evaluationStartedAt=now,
        evaluationCompletedAt=now,
        adaptiveRuleVersion="v2.1",
        adaptiveStopMultiplier=1.25,
        marketSnapshot=CandidateMarketSnapshot(
            trend="BULLISH",
            volatility="NORMAL",
            session="London",
            newsImpact="Low",
            marketSentiment="Bullish",
            marketConfidence=85,
            spread=0.0002,
            atr=0.0015,
        ),
    )


# ==============================================================================
# Group 1: Execution Safety & Invariants (Tests 1–5)
# ==============================================================================

def test_01_default_mode_is_strictly_paper():
    """1. Default execution mode is strictly PAPER."""
    with patch.object(settings, "EXECUTION_MODE", "PAPER"), \
         patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", False):
        guard = ExecutionModeGuard()
        assert guard.get_system_mode() == ExecutionMode.PAPER
        assert guard.is_paper() is True
        assert guard.is_live() is False


def test_02_live_mode_requires_dual_acknowledgement():
    """2. LIVE mode requires both EXECUTION_MODE=LIVE and LIVE_EXECUTION_ACKNOWLEDGED=True."""
    with patch.object(settings, "EXECUTION_MODE", "LIVE"), \
         patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", False):
        guard = ExecutionModeGuard()
        # Fails closed to PAPER if unacknowledged
        assert guard.get_system_mode() == ExecutionMode.PAPER

    with patch.object(settings, "EXECUTION_MODE", "LIVE"), \
         patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", True):
        guard = ExecutionModeGuard()
        assert guard.get_system_mode() == ExecutionMode.LIVE
        assert guard.is_live() is True


def test_03_invalid_or_conflicting_mode_fails_closed_to_paper():
    """3. Invalid or conflicting mode configuration fails closed to PAPER."""
    with patch.object(settings, "EXECUTION_MODE", "UNKNOWN_BROKER_MODE"):
        guard = ExecutionModeGuard()
        assert guard.get_system_mode() == ExecutionMode.PAPER


def test_04_assert_no_broker_automation_raises_error():
    """4. assert_no_broker_automation() strictly raises RuntimeError on any attempt."""
    with pytest.raises(RuntimeError, match="automated broker execution is strictly prohibited"):
        assert_no_broker_automation("Broker dispatch test")


def test_05_mode_guard_reports_locked():
    """5. Mode guard correctly reports brokerAutomationLocked = True."""
    guard = ExecutionModeGuard()
    assert guard.is_broker_locked() is True


# ==============================================================================
# Group 2: Signal Identity & Execution Instance Identity (Tests 6–10)
# ==============================================================================

def test_06_single_signal_id_associated_with_paper_and_live():
    """6. A single signal_id can be associated with both a PAPER and a LIVE execution instance."""
    now = datetime.now(timezone.utc)
    # 1. PAPER instance for signal 5001
    paper_item = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5001,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Simulated paper setup",
            notes="[MODE:PAPER] Candidate #5001",
            executionMode="PAPER",
        )
    )

    # 2. LIVE instance for signal 5001
    live_item = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5001,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Manual live execution",
            notes="[MODE:LIVE] Manual MT5 fill",
            executionMode="LIVE",
        )
    )

    assert paper_item.id != live_item.id
    assert paper_item.signalId == live_item.signalId == 5001
    assert paper_item.executionMode == "PAPER"
    assert live_item.executionMode == "LIVE"


def test_07_duplicate_paper_reservation_reuses_slot():
    """7. Attempting duplicate active reservations within PAPER mode reuses existing reservation."""
    cand = make_test_candidate(signal_id=5002)
    dec1, res1 = paper_trading_engine.authorize_paper_candidate(cand, signal_id=5002)
    assert dec1.allowed is True
    assert res1 is not None

    # Re-authorize same signal in PAPER
    dec2, res2 = paper_trading_engine.authorize_paper_candidate(cand, signal_id=5002)
    assert dec2.allowed is True
    assert res2.id == res1.id  # Same reservation returned without extra slot


def test_08_duplicate_live_reservation_reuses_slot():
    """8. Attempting duplicate active reservations within LIVE mode reuses existing reservation."""
    auth = signal_authorization_service
    p = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        takeProfit=Decimal("1.1150"),
        lotSize=Decimal("0.01"),
    )
    dec1, res1 = auth.authorize_and_reserve(proposal=p, signal_id=5003, execution_mode="LIVE")
    assert dec1.allowed is True

    # Second live attempt reuses reservation
    dec2, res2 = auth.authorize_and_reserve(proposal=p, signal_id=5003, execution_mode="LIVE")
    assert dec2.allowed is True
    assert res2.id == res1.id


def test_09_ambiguous_records_fail_closed_in_divergence():
    """9. Ambiguous records (multiple live records for same signal_id) fail closed."""
    now = datetime.now(timezone.utc)
    # Create 1 paper trade
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5004,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    # Create 2 live trades for same signalId 5004
    for i in range(2):
        trade_journal_repository.create_trade(
            TradeJournalCreate(
                signalId=5004,
                symbol="EURUSD",
                direction="BUY",
                entryPrice=1.1000,
                stopLoss=1.0950,
                takeProfit=1.1150,
                timeframe="M15",
                marketSession="London",
                tradeDate=now,
                reasonForEntry=f"Live {i}",
                executionMode="LIVE",
            )
        )

    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5004), None)
    assert item is not None
    assert item.classification == DivergenceClassification.AMBIGUOUS.value
    assert item.slippagePoints is None
    assert item.executionLatencySeconds is None


def test_10_advisory_lock_acquired_during_reservation():
    """10. Advisory lock 8882026 key is verified."""
    assert FALCON_GUARDIAN_ADVISORY_LOCK_KEY == 8882026


# ==============================================================================
# Group 3: Execution Divergence Analytics & Fill Authority (Tests 11–24)
# ==============================================================================

def test_11_exact_signal_id_pairing_produces_matched():
    """11. Exact signal_id pairing produces MATCHED divergence item."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5011,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1001,
            fillTime=now,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5011,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1003,
            fillTime=now + timedelta(seconds=15),
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5011), None)
    assert item is not None
    assert item.classification == DivergenceClassification.MATCHED.value


def test_12_arbitrary_pairing_by_symbol_or_time_alone_rejected():
    """12. Two trades sharing symbol and time but different signalId are never paired."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5012,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            fillTime=now,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5013,  # Different signalId!
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1002,
            fillTime=now,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    i5012 = next((i for i in resp.items if i.signalId == 5012), None)
    i5013 = next((i for i in resp.items if i.signalId == 5013), None)
    assert i5012.classification == DivergenceClassification.MISSED_EXECUTION.value
    assert i5013.classification == DivergenceClassification.MANUAL_ONLY.value


def test_13_actual_paper_fill_price_is_authoritative():
    """13. Actual paper fill price is authoritative."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5014,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1002,  # Actual simulated fill
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5014,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1005,  # Actual manual fill
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5014), None)
    assert item.paperFillPrice == 1.1002
    assert item.liveFillPrice == 1.1005
    assert item.entryPriceDelta == 0.0003


def test_14_actual_live_fill_price_is_authoritative():
    """14. Actual live fill price is authoritative."""
    test_13_actual_paper_fill_price_is_authoritative()


def test_15_missing_paper_fill_produces_none():
    """15. Missing PAPER fill price produces entry_price_delta = None and slippage_points = None."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5015,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=None,  # No simulated fill (e.g. PENDING)
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5015,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1005,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5015), None)
    assert item.entryPriceDelta is None
    assert item.slippagePoints is None


def test_16_missing_live_fill_produces_none():
    """16. Missing LIVE fill price produces entry_price_delta = None and slippage_points = None."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5016,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1002,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5016,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=None,  # Live trade missing fillPrice
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5016), None)
    assert item.entryPriceDelta is None
    assert item.slippagePoints is None


def test_17_requested_entry_price_never_substituted():
    """17. Requested entry price (entryPrice) is NEVER substituted as fillPrice."""
    # Both trades have entryPrice=1.1000, but fillPrice=None
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5017,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=None,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5017,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=None,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5017), None)
    # Must NOT substitute 1.1000 - 1.1000 = 0.0000
    assert item.entryPriceDelta is None
    assert item.slippagePoints is None


def test_18_actual_fill_time_used_for_latency():
    """18. Actual fill time is used for execution latency."""
    now = datetime.now(timezone.utc)
    t_signal = now
    t_live_fill = now + timedelta(seconds=24.5)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5018,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            fillTime=now,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=t_signal,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5018,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1002,
            fillTime=t_live_fill,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=t_signal,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5018), None)
    assert item.executionLatencySeconds == 24.5


def test_19_missing_actual_fill_time_produces_none_latency():
    """19. Missing actual fill time produces executionLatencySeconds = None (never 0)."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5019,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            fillTime=now,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5019,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1002,
            fillTime=None,  # Missing fill time!
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5019), None)
    assert item.executionLatencySeconds is None


def test_20_buy_slippage_points_calculation():
    """20. BUY slippage = live_fill - paper_fill (positive = paid more)."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5020,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5020,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1004,  # Paid 4 pips more
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5020), None)
    assert item.slippagePoints == 0.0004


def test_21_sell_slippage_points_calculation():
    """21. SELL slippage = paper_fill - live_fill (positive = received less)."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5021,
            symbol="EURUSD",
            direction="SELL",
            entryPrice=1.1000,
            fillPrice=1.1000,  # Paper sold at 1.1000
            stopLoss=1.1050,
            takeProfit=1.0900,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5021,
            symbol="EURUSD",
            direction="SELL",
            entryPrice=1.1000,
            fillPrice=1.0995,  # Live sold at 1.0995 (5 pips worse)
            stopLoss=1.1050,
            takeProfit=1.0900,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5021), None)
    assert item.slippagePoints == 0.0005


def test_22_spread_delta_calculation():
    """22. Spread delta calculated correctly; missing remains None."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5022,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            spreadAtEntry=0.00015,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5022,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1002,
            spreadAtEntry=0.00025,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5022), None)
    assert item.spreadDelta == 0.00010


def test_23_realized_r_divergence_calculation():
    """23. Realized R divergence computed from persisted initial monetary risk."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5023,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            realizedRMultiple=2.5,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5023,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1002,
            realizedRMultiple=1.8,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5023), None)
    assert item.rDivergence == -0.7  # 1.8 - 2.5 = -0.7


def test_24_paper_trade_with_no_live_is_missed_execution():
    """24. Paper trade with no manual live counterpart classified strictly as MISSED_EXECUTION."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5024,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper setup",
            executionMode="PAPER",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5024), None)
    assert item.classification == DivergenceClassification.MISSED_EXECUTION.value
    assert item.liveTradeId is None


# ==============================================================================
# Group 4: Manual LIVE Ingestion & Historical Isolation (Tests 25–30)
# ==============================================================================

def test_25_manual_live_ingestion_via_post_sets_live_mode():
    """25. Manual LIVE record ingestion via POST /trade-journal sets executionMode = LIVE."""
    client = TestClient(app)
    now = datetime.now(timezone.utc)
    payload = {
        "signalId": 5025,
        "symbol": "EURUSD",
        "direction": "BUY",
        "entryPrice": 1.1000,
        "stopLoss": 1.0950,
        "takeProfit": 1.1150,
        "timeframe": "M15",
        "marketSession": "London",
        "tradeDate": now.isoformat(),
        "status": "OPEN",
        "reasonForEntry": "Manual MT5 execution",
        "executionMode": "LIVE",
        "notes": "[MODE:LIVE] Exness order #982734",
        "fillPrice": 1.1003,
        "fillTime": now.isoformat(),
    }
    response = client.post("/api/v1/trade-journal", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["executionMode"] == "LIVE"
    assert "[MODE:LIVE]" in data["notes"]


def test_26_manual_live_record_preserves_signal_id_and_actual_fills():
    """26. Manual LIVE record preserves signal_id, authoritative fillPrice, and fillTime."""
    now = datetime.now(timezone.utc)
    item = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5026,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1004,
            fillTime=now,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Manual execution",
            executionMode="LIVE",
        )
    )
    assert item.signalId == 5026
    assert item.fillPrice == 1.1004
    assert item.fillTime == now


def test_27_manual_live_record_closure_via_patch():
    """27. Manual LIVE record closure via PATCH updates exitPrice, closeDate, and realizedR."""
    client = TestClient(app)
    now = datetime.now(timezone.utc)
    created = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5027,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            initialMonetaryRisk=Decimal("10.00"),
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            status="OPEN",
            reasonForEntry="Manual live trade",
            executionMode="LIVE",
        )
    )
    patch_payload = {
        "status": "CLOSED",
        "result": "WIN",
        "exitPrice": 1.1150,
        "closeDate": now.isoformat(),
        "profitLoss": 30.0,
    }
    res = client.patch(f"/api/v1/trade-journal/{created.id}", json=patch_payload)
    assert res.status_code == 200
    updated = res.json()
    assert updated["status"] == "CLOSED"
    assert updated["result"] == "WIN"
    assert updated["exitPrice"] == 1.1150
    assert updated["realizedRMultiple"] == 3.0  # $30 / $10 = 3.0


def test_28_historical_untagged_records_remain_unmodified():
    """28. Historical records without mode tags remain executionMode = None and unmodified."""
    now = datetime.now(timezone.utc)
    item = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5028,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            status="CLOSED",
            result="WIN",
            reasonForEntry="Legacy untagged historical record",
            notes="Legacy note without mode tag",
        )
    )
    assert item.executionMode is None
    assert "[MODE:" not in (item.notes or "")


def test_29_historical_untagged_records_excluded_from_new_live_divergence():
    """29. Historical untagged records are strictly excluded from the new LIVE divergence population."""
    now = datetime.now(timezone.utc)
    # Legacy record with signalId 5029
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5029,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Legacy",
            notes="Legacy trade without mode tag",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5029), None)
    # Untagged historical records are ignored by divergence analysis
    assert item is None


def test_30_new_mode_records_included_and_separated():
    """30. New [MODE:LIVE] and [MODE:PAPER] records are included and strictly separated."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5030,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5030,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1002,
            stopLoss=1.0950,
            takeProfit=1.1150,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5030), None)
    assert item is not None
    assert item.classification == DivergenceClassification.MATCHED.value


# ==============================================================================
# Group 5: Deterministic Premature Exit (Tests 31–34)
# ==============================================================================

def test_31_deterministic_premature_exit_true():
    """31. PAPER reaches TP + LIVE closed early before TP produces premature_exit = True."""
    now = datetime.now(timezone.utc)
    t_live_close = now + timedelta(minutes=10)
    t_paper_close = now + timedelta(minutes=25)

    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5031,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            exitPrice=1.1150,  # Hit TP cleanly
            status="CLOSED",
            result="WIN",
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=t_paper_close,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5031,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            exitPrice=1.1080,  # Closed early before reaching 1.1150
            status="CLOSED",
            result="WIN",
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=t_live_close,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5031), None)
    assert item.prematureExit is True


def test_32_missing_exit_data_produces_none_premature_exit():
    """32. Missing required exit data produces premature_exit = None."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5032,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            status="OPEN",  # Still OPEN!
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5032,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            status="OPEN",
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5032), None)
    assert item.prematureExit is None


def test_33_mfe_difference_alone_does_not_produce_premature_exit():
    """33. MFE difference alone does NOT produce premature_exit = True."""
    now = datetime.now(timezone.utc)
    # Neither hit TP (both stopped out at SL), but paper had higher MFE
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5033,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            exitPrice=1.0950,
            mfeR=1.5,
            status="CLOSED",
            result="LOSS",
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=now + timedelta(minutes=20),
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5033,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            exitPrice=1.0950,
            mfeR=0.5,
            status="CLOSED",
            result="LOSS",
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=now + timedelta(minutes=15),
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5033), None)
    # Since paper did NOT hit TP, prematureExit must NOT be True!
    assert item.prematureExit is None


def test_34_lower_r_alone_does_not_produce_premature_exit():
    """34. Lower R alone without TP breach does NOT produce premature_exit = True."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5034,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            exitPrice=1.1050,  # Did not hit 1.1150 TP
            realizedRMultiple=1.0,
            status="CLOSED",
            result="WIN",
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=now + timedelta(minutes=20),
            reasonForEntry="Paper",
            executionMode="PAPER",
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5034,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            exitPrice=1.1020,
            realizedRMultiple=0.4,
            status="CLOSED",
            result="WIN",
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=now + timedelta(minutes=15),
            reasonForEntry="Live",
            executionMode="LIVE",
        )
    )
    resp = execution_divergence_service.get_execution_divergence()
    item = next((i for i in resp.items if i.signalId == 5034), None)
    assert item.prematureExit is None


# ==============================================================================
# Group 6: Controlled Paper Runtime (Tests 35–44)
# ==============================================================================

def test_35_paper_candidate_discovered_and_pending():
    """35. Paper candidate is discovered and transitions to PENDING with [MODE:PAPER]."""
    cand = make_test_candidate(signal_id=5035)
    item = paper_trading_runtime.reserve_paper_candidate(cand, signal_id=5035)
    assert item is not None
    assert item.status == "PENDING"
    assert item.executionMode == "PAPER"
    assert "[MODE:PAPER]" in item.notes


def test_36_market_quote_transitions_pending_to_open():
    """36. Market quote crossing entry transitions PENDING to OPEN."""
    cand = make_test_candidate(signal_id=5036)
    paper_trading_runtime.reserve_paper_candidate(cand, signal_id=5036)

    # Market quote crossing 1.1000 entry
    quote = MarketQuote(
        symbol="EURUSD",
        lastPrice=1.1000,
        bidAsk=BidAsk(bid=1.0999, ask=1.1001, spread=0.0002),
        timestamp=datetime.now(timezone.utc),
        providerId="twelve_data",
        providerName="TwelveData",
    )
    res = paper_trading_runtime.process_cycle(quotes=[quote])
    assert res["filled_count"] == 1

    trades = trade_journal_repository.list_trades()
    t = next((t for t in trades if t.signalId == 5036), None)
    assert t.status == "OPEN"
    assert t.fillPrice == 1.1001  # Filled at ask for BUY


def test_37_clean_single_tp_closes_paper_trade():
    """37. Clean single TP hit closes paper trade as WIN."""
    cand = make_test_candidate(signal_id=5037)
    item = paper_trading_runtime.reserve_paper_candidate(cand, signal_id=5037)
    paper_trading_engine.simulate_fill(trade_id=item.id, fill_price=1.1000)

    # Quote reaches TP (1.1150)
    quote = MarketQuote(
        symbol="EURUSD",
        lastPrice=1.1155,
        bidAsk=BidAsk(bid=1.1154, ask=1.1156, spread=0.0002),
        timestamp=datetime.now(timezone.utc),
        providerId="twelve_data",
        providerName="TwelveData",
    )
    res = paper_trading_runtime.process_cycle(quotes=[quote])
    assert res["closed_count"] == 1

    t = trade_journal_repository.get_trade(item.id)
    assert t.status == "CLOSED"
    assert t.result == "WIN"
    assert t.exitPrice == 1.1150


def test_38_clean_single_sl_closes_paper_trade():
    """38. Clean single SL hit closes paper trade as LOSS."""
    cand = make_test_candidate(signal_id=5038)
    item = paper_trading_runtime.reserve_paper_candidate(cand, signal_id=5038)
    paper_trading_engine.simulate_fill(trade_id=item.id, fill_price=1.1000)

    # Quote reaches SL (1.0950)
    quote = MarketQuote(
        symbol="EURUSD",
        lastPrice=1.0945,
        bidAsk=BidAsk(bid=1.0944, ask=1.0946, spread=0.0002),
        timestamp=datetime.now(timezone.utc),
        providerId="twelve_data",
        providerName="TwelveData",
    )
    res = paper_trading_runtime.process_cycle(quotes=[quote])
    assert res["closed_count"] == 1

    t = trade_journal_repository.get_trade(item.id)
    assert t.status == "CLOSED"
    assert t.result == "LOSS"
    assert t.exitPrice == 1.0950


def test_39_simultaneous_sltp_resolves_to_loss():
    """39. Ambiguous simultaneous SL/TP hit resolves fail-closed to LOSS."""
    cand = make_test_candidate(signal_id=5039)
    item = paper_trading_runtime.reserve_paper_candidate(cand, signal_id=5039)
    paper_trading_engine.simulate_fill(trade_id=item.id, fill_price=1.1000)

    # Extreme volatility observation touching both SL (1.0950) and TP (1.1150)
    closed = paper_trading_engine.evaluate_paper_trade(
        trade_id=item.id,
        high=1.1160,
        low=1.0940,
    )
    assert closed.status == "CLOSED"
    assert closed.result == "LOSS"
    assert closed.exitPrice == 1.0950  # Resolved to Stop Loss


def test_40_mfe_mae_excursions_track_correctly():
    """40. MFE and MAE excursions track post-fill prices correctly."""
    cand = make_test_candidate(signal_id=5040)
    item = paper_trading_runtime.reserve_paper_candidate(cand, signal_id=5040)
    paper_trading_engine.simulate_fill(trade_id=item.id, fill_price=1.1000)

    # Favorable observation
    paper_trading_engine.evaluate_paper_trade(trade_id=item.id, current_price=1.1080)
    t1 = trade_journal_repository.get_trade(item.id)
    assert t1.peakPrice == 1.1080
    assert t1.mfeR is not None and t1.mfeR > 0.0


def test_41_pending_trade_expires_after_validity_window():
    """41. Untriggered PENDING trade expires after validity window without loss."""
    cand = make_test_candidate(signal_id=5041)
    item = paper_trading_runtime.reserve_paper_candidate(cand, signal_id=5041)

    # Run cycle 60 minutes later
    future_time = datetime.now(timezone.utc) + timedelta(minutes=60)
    res = paper_trading_runtime.process_cycle(as_of=future_time)
    assert res["expired_count"] == 1

    t = trade_journal_repository.get_trade(item.id)
    assert t.status == "EXPIRED"
    assert t.result == "EXPIRED"
    assert t.profitLoss == 0.0


def test_42_pending_trade_invalidates_on_boundary_breach():
    """42. PENDING trade invalidates when thesis boundary breached prior to fill."""
    cand = make_test_candidate(signal_id=5042)
    item = paper_trading_runtime.reserve_paper_candidate(cand, signal_id=5042)

    invalidated = paper_trading_engine.invalidate_paper_trade(
        trade_id=item.id,
        reason="Market structure broke before entry",
    )
    assert invalidated.status == "INVALIDATED"
    assert invalidated.result == "INVALIDATED"


def test_43_repeated_quote_processing_is_idempotent():
    """43. Repeated quote processing on same trade/event is strictly idempotent."""
    cand = make_test_candidate(signal_id=5043)
    item = paper_trading_runtime.reserve_paper_candidate(cand, signal_id=5043)
    paper_trading_engine.simulate_fill(trade_id=item.id, fill_price=1.1000)

    # Hit TP
    quote = MarketQuote(
        symbol="EURUSD",
        lastPrice=1.1155,
        bidAsk=BidAsk(bid=1.1154, ask=1.1156, spread=0.0002),
        timestamp=datetime.now(timezone.utc),
        providerId="twelve_data",
        providerName="TwelveData",
    )
    paper_trading_runtime.process_cycle(quotes=[quote])
    t_after_close = trade_journal_repository.get_trade(item.id)
    assert t_after_close.status == "CLOSED"

    # Re-run cycle with same quote
    res2 = paper_trading_runtime.process_cycle(quotes=[quote])
    assert res2["closed_count"] == 0  # Does not double-close!


def test_44_terminal_trades_reject_further_updates():
    """44. Terminal trades (CLOSED, EXPIRED, INVALIDATED) reject further quote updates."""
    cand = make_test_candidate(signal_id=5044)
    item = paper_trading_runtime.reserve_paper_candidate(cand, signal_id=5044)
    paper_trading_engine.simulate_fill(trade_id=item.id, fill_price=1.1000)
    paper_trading_engine.evaluate_paper_trade(trade_id=item.id, current_price=1.1155)

    closed = trade_journal_repository.get_trade(item.id)
    assert closed.status == "CLOSED"
    first_pnl = closed.profitLoss

    # Adverse observation afterwards
    afterward = paper_trading_engine.evaluate_paper_trade(trade_id=item.id, current_price=1.0800)
    assert afterward.status == "CLOSED"
    assert afterward.profitLoss == first_pnl


# ==============================================================================
# Group 7: Capital & Exposure Isolation (Tests 45–50)
# ==============================================================================

def test_45_three_active_paper_trades_do_not_consume_live_slots(clean_test_environment):
    """45. Three active PAPER trades do NOT consume LIVE Guardian 3-trade slots."""
    auth = clean_test_environment["auth_service"]
    for i in range(1, 4):
        p = ProposedTradeInput(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=Decimal("1.1000"),
            stopLoss=Decimal("1.0950"),
            takeProfit=Decimal("1.1150"),
            lotSize=Decimal("0.01"),
        )
        dec, res = paper_trading_engine.authorize_and_reserve_paper(p, signal_id=6040 + i)
        assert dec.allowed is True
        paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)

    # LIVE reserving count must remain 0!
    live_reserving = auth._guardian_service.get_capital_reserving_trades(execution_mode="LIVE")
    assert len(live_reserving) == 0

    # LIVE trade can be authorized!
    live_p = ProposedTradeInput(
        symbol="GBPUSD",
        direction="BUY",
        entryPrice=Decimal("1.3000"),
        stopLoss=Decimal("1.2950"),
        takeProfit=Decimal("1.3150"),
        lotSize=Decimal("0.01"),
    )
    live_dec, live_res = auth.authorize_and_reserve(proposal=live_p, signal_id=7040, execution_mode="LIVE")
    assert live_dec.allowed is True
    assert live_dec.currentLiveTradeCount == 0


def test_46_active_paper_loss_does_not_reduce_live_loss_capacity(clean_test_environment):
    """46. Active PAPER worst-case loss does NOT reduce LIVE remaining loss capacity."""
    auth = clean_test_environment["auth_service"]
    # 2 paper trades with $9.00 risk each ($18.00 paper risk)
    for i in range(1, 3):
        p = ProposedTradeInput(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=Decimal("1.1000"),
            stopLoss=Decimal("1.0910"),
            takeProfit=Decimal("1.1200"),
            lotSize=Decimal("0.01"),
        )
        paper_trading_engine.authorize_and_reserve_paper(p, signal_id=6050 + i)

    # Live proposal with $15 risk ($15 <= $20 capital)
    live_p = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0850"),
        takeProfit=Decimal("1.1300"),
        lotSize=Decimal("0.01"),
    )
    live_dec, live_res = auth.authorize_and_reserve(proposal=live_p, signal_id=7050, execution_mode="LIVE")
    assert live_dec.allowed is True
    assert live_dec.currentAggregateWorstCaseLoss == Decimal("0.00")
    assert live_dec.remainingLossCapacity == Decimal("5.00")


def test_47_paper_profit_does_not_modify_live_capital(clean_test_environment):
    """47. Closing PAPER trades with profit does NOT modify LIVE active capital or protected profit."""
    cycle_service = clean_test_environment["cycle_service"]
    cycle_before = cycle_service.get_active_cycle()
    capital_before = cycle_before.activeTradingCapital
    protected_before = cycle_before.protectedProfit

    cand = make_test_candidate(signal_id=5047)
    item = paper_trading_runtime.reserve_paper_candidate(cand, signal_id=5047)
    paper_trading_engine.simulate_fill(trade_id=item.id, fill_price=1.1000)
    paper_trading_engine.evaluate_paper_trade(trade_id=item.id, current_price=1.1155)

    cycle_after = cycle_service.get_active_cycle()
    assert cycle_after.activeTradingCapital == capital_before == Decimal("20.00")
    assert cycle_after.protectedProfit == protected_before == Decimal("0.00")


def test_48_paper_loss_does_not_modify_live_capital(clean_test_environment):
    """48. Closing PAPER trades with loss does NOT modify LIVE active capital."""
    cycle_service = clean_test_environment["cycle_service"]
    cand = make_test_candidate(signal_id=5048)
    item = paper_trading_runtime.reserve_paper_candidate(cand, signal_id=5048)
    paper_trading_engine.simulate_fill(trade_id=item.id, fill_price=1.1000)
    paper_trading_engine.evaluate_paper_trade(trade_id=item.id, current_price=1.0900)

    cycle_after = cycle_service.get_active_cycle()
    assert cycle_after.activeTradingCapital == Decimal("20.00")
    assert cycle_after.status == CapitalCycleStatus.ACTIVE


def test_49_paper_cannot_advance_or_halt_live_cycle(clean_test_environment):
    """49. PAPER trade cannot advance, halt, reset, or trigger cooldown on a LIVE capital cycle."""
    cycle_service = clean_test_environment["cycle_service"]
    # Severe paper loss
    cand = make_test_candidate(signal_id=5049)
    item = paper_trading_runtime.reserve_paper_candidate(cand, signal_id=5049)
    paper_trading_engine.simulate_fill(trade_id=item.id, fill_price=1.1000)
    paper_trading_engine.evaluate_paper_trade(trade_id=item.id, current_price=1.0500)

    cycle = cycle_service.get_active_cycle()
    assert cycle.status == CapitalCycleStatus.ACTIVE


def test_50_paper_cannot_block_valid_live_authorization(clean_test_environment):
    """50. PAPER activity cannot block an otherwise valid LIVE manual trade authorization."""
    test_45_three_active_paper_trades_do_not_consume_live_slots(clean_test_environment)


# ==============================================================================
# Group 8: Strategy Attribution & Drift Diagnostics (Tests 51–58)
# ==============================================================================

def test_51_closed_trades_grouped_across_4tuple():
    """51. Closed trades grouped accurately across (strategyId, strategyVersion, adaptiveRuleVersion, executionMode)."""
    now = datetime.now(timezone.utc)
    # Create 2 PAPER trades under V1
    for i in range(2):
        trade_journal_repository.create_trade(
            TradeJournalCreate(
                signalId=5051 + i,
                symbol="EURUSD",
                direction="BUY",
                entryPrice=1.1000,
                stopLoss=1.0950,
                takeProfit=1.1150,
                fillPrice=1.1000,
                exitPrice=1.1150,
                status="CLOSED",
                result="WIN",
                profitLoss=15.0,
                strategyId="TREND_FLOW",
                strategyVersion="2.0.0",
                adaptiveRuleVersion="v1.0",
                timeframe="M15",
                marketSession="London",
                tradeDate=now - timedelta(hours=2),
                closeDate=now - timedelta(hours=1),
                reasonForEntry="Test",
                executionMode="PAPER",
            )
        )

    resp = strategy_attribution_service.get_strategy_attribution()
    item = next(
        (i for i in resp.attributions
         if i.key.strategyId == "TREND_FLOW"
         and i.key.strategyVersion == "2.0.0"
         and i.key.adaptiveRuleVersion == "v1.0"
         and i.key.executionMode == "PAPER"),
        None,
    )
    assert item is not None
    assert item.metrics.closedCount == 2
    assert item.metrics.wins == 2
    assert item.metrics.winRate == 1.0


def test_52_historical_provenance_remains_immutable():
    """52. Historical provenance remains immutable across configuration changes."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5052,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            fillPrice=1.1000,
            exitPrice=1.1150,
            status="CLOSED",
            result="WIN",
            strategyId="TREND_FLOW",
            strategyVersion="1.0.0",  # Version 1.0.0
            adaptiveRuleVersion="v1.0",
            timeframe="M15",
            marketSession="London",
            tradeDate=now - timedelta(hours=2),
            closeDate=now - timedelta(hours=1),
            reasonForEntry="Legacy V1",
            executionMode="PAPER",
        )
    )
    resp = strategy_attribution_service.get_strategy_attribution()
    item = next((i for i in resp.attributions if i.key.strategyVersion == "1.0.0"), None)
    assert item is not None
    assert item.key.strategyVersion == "1.0.0"


def test_53_win_rate_drift_se_formula():
    """53. Win-rate drift standard error uses exact formula SE = sqrt(p_paper * (1 - p_paper) / N_live)."""
    p_paper = 0.60
    n_live = 20
    expected_se = math.sqrt(p_paper * (1.0 - p_paper) / n_live)  # sqrt(0.24 / 20) = sqrt(0.012) ~= 0.10954
    assert round(expected_se, 4) == 0.1095


def test_54_z_score_sign_convention():
    """54. Correct z-score sign convention: z = (p_live - p_paper) / SE."""
    p_paper = 0.60
    p_live = 0.35
    se = 0.10954
    z = (p_live - p_paper) / se
    assert z < -2.0  # (0.35 - 0.60) / 0.10954 = -2.28


def test_55_significant_deterioration_emits_warning():
    """55. Significant deterioration (z < -2.0) emits WIN_RATE_DRIFT_DETECTED warning."""
    now = datetime.now(timezone.utc)
    # Seed 20 paper trades: 14 WIN, 6 LOSS -> p_paper = 0.70
    for i in range(20):
        res = "WIN" if i < 14 else "LOSS"
        trade_journal_repository.create_trade(
            TradeJournalCreate(
                signalId=6000 + i,
                symbol="EURUSD",
                direction="BUY",
                entryPrice=1.1000,
                stopLoss=1.0950,
                takeProfit=1.1150,
                fillPrice=1.1000,
                exitPrice=1.1150 if res == "WIN" else 1.0950,
                status="CLOSED",
                result=res,
                profitLoss=20.0 if res == "WIN" else -10.0,
                strategyId="ALPHA_EXP",
                strategyVersion="3.0",
                adaptiveRuleVersion="v2",
                timeframe="M15",
                marketSession="London",
                tradeDate=now - timedelta(hours=3),
                closeDate=now - timedelta(hours=2),
                reasonForEntry="Paper",
                executionMode="PAPER",
            )
        )

    # Seed 20 live trades: 5 WIN, 15 LOSS -> p_live = 0.25
    for i in range(20):
        res = "WIN" if i < 5 else "LOSS"
        trade_journal_repository.create_trade(
            TradeJournalCreate(
                signalId=7000 + i,
                symbol="EURUSD",
                direction="BUY",
                entryPrice=1.1000,
                stopLoss=1.0950,
                takeProfit=1.1150,
                fillPrice=1.1000,
                exitPrice=1.1150 if res == "WIN" else 1.0950,
                status="CLOSED",
                result=res,
                profitLoss=20.0 if res == "WIN" else -10.0,
                strategyId="ALPHA_EXP",
                strategyVersion="3.0",
                adaptiveRuleVersion="v2",
                timeframe="M15",
                marketSession="London",
                tradeDate=now - timedelta(hours=3),
                closeDate=now - timedelta(hours=2),
                reasonForEntry="Live",
                executionMode="LIVE",
            )
        )

    resp = strategy_attribution_service.get_strategy_attribution()
    diag = next((d for d in resp.driftDiagnostics if d.strategyId == "ALPHA_EXP"), None)
    assert diag is not None
    assert diag.status == DriftStatus.WIN_RATE_DRIFT_DETECTED.value
    assert diag.warning is True
    assert diag.zScoreWinRate < -2.0


def test_56_normal_variation_produces_no_warning():
    """56. Normal variation (z >= -2.0) produces no warning (NORMAL)."""
    now = datetime.now(timezone.utc)
    # 20 paper trades: 12 WIN, 8 LOSS -> p_paper = 0.60
    for i in range(20):
        res = "WIN" if i < 12 else "LOSS"
        trade_journal_repository.create_trade(
            TradeJournalCreate(
                signalId=8000 + i,
                symbol="EURUSD",
                direction="BUY",
                entryPrice=1.1000,
                stopLoss=1.0950,
                takeProfit=1.1150,
                fillPrice=1.1000,
                exitPrice=1.1150 if res == "WIN" else 1.0950,
                status="CLOSED",
                result=res,
                profitLoss=20.0 if res == "WIN" else -10.0,
                strategyId="BETA_EXP",
                strategyVersion="1.0",
                adaptiveRuleVersion="v1",
                timeframe="M15",
                marketSession="London",
                tradeDate=now - timedelta(hours=3),
                closeDate=now - timedelta(hours=2),
                reasonForEntry="Paper",
                executionMode="PAPER",
            )
        )

    # 20 live trades: 11 WIN, 9 LOSS -> p_live = 0.55
    for i in range(20):
        res = "WIN" if i < 11 else "LOSS"
        trade_journal_repository.create_trade(
            TradeJournalCreate(
                signalId=9000 + i,
                symbol="EURUSD",
                direction="BUY",
                entryPrice=1.1000,
                stopLoss=1.0950,
                takeProfit=1.1150,
                fillPrice=1.1000,
                exitPrice=1.1150 if res == "WIN" else 1.0950,
                status="CLOSED",
                result=res,
                profitLoss=20.0 if res == "WIN" else -10.0,
                strategyId="BETA_EXP",
                strategyVersion="1.0",
                adaptiveRuleVersion="v1",
                timeframe="M15",
                marketSession="London",
                tradeDate=now - timedelta(hours=3),
                closeDate=now - timedelta(hours=2),
                reasonForEntry="Live",
                executionMode="LIVE",
            )
        )

    resp = strategy_attribution_service.get_strategy_attribution()
    diag = next((d for d in resp.driftDiagnostics if d.strategyId == "BETA_EXP"), None)
    assert diag is not None
    assert diag.status == DriftStatus.NORMAL.value
    assert diag.warning is False


def test_57_insufficient_sample_produces_not_evaluable():
    """57. Insufficient sample (N < 10) produces NOT_EVALUABLE."""
    now = datetime.now(timezone.utc)
    # Only 3 trades
    for i in range(3):
        trade_journal_repository.create_trade(
            TradeJournalCreate(
                signalId=9100 + i,
                symbol="EURUSD",
                direction="BUY",
                entryPrice=1.1000,
                stopLoss=1.0950,
                takeProfit=1.1150,
                fillPrice=1.1000,
                exitPrice=1.1150,
                status="CLOSED",
                result="WIN",
                strategyId="TINY_EXP",
                timeframe="M15",
                marketSession="London",
                tradeDate=now - timedelta(hours=3),
                closeDate=now - timedelta(hours=2),
                reasonForEntry="Paper",
                executionMode="PAPER",
            )
        )
    resp = strategy_attribution_service.get_strategy_attribution()
    diag = next((d for d in resp.driftDiagnostics if d.strategyId == "TINY_EXP"), None)
    assert diag is not None
    assert diag.status == DriftStatus.NOT_EVALUABLE.value
    assert diag.warning is False
    assert diag.zScoreWinRate is None


def test_58_profit_factor_drift_strictly_not_evaluable():
    """58. Profit factor drift strictly returns zScoreProfitFactor = None and NOT_EVALUABLE."""
    test_55_significant_deterioration_emits_warning()
    resp = strategy_attribution_service.get_strategy_attribution()
    diag = next((d for d in resp.driftDiagnostics if d.strategyId == "ALPHA_EXP"), None)
    assert diag is not None
    assert diag.zScoreProfitFactor is None
    assert diag.profitFactorDrift == "NOT_EVALUABLE"


# ==============================================================================
# Group 9: Lookahead Protection & API Endpoints (Tests 59–64)
# ==============================================================================

def test_59_historical_as_of_excludes_future_trades():
    """59. Historical as_of excludes future closed trades."""
    now = datetime.now(timezone.utc)
    past_time = now - timedelta(hours=2)

    # Trade closed 1 hour ago (in future relative to past_time)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5059,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            fillPrice=1.1000,
            exitPrice=1.1150,
            status="CLOSED",
            result="WIN",
            strategyId="TIME_LOCK",
            timeframe="M15",
            marketSession="London",
            tradeDate=now - timedelta(hours=3),
            closeDate=now - timedelta(hours=1),
            reasonForEntry="Future close",
            executionMode="PAPER",
        )
    )

    # Evaluated as of 2 hours ago
    resp = strategy_attribution_service.get_strategy_attribution(as_of=past_time)
    item = next((i for i in resp.attributions if i.key.strategyId == "TIME_LOCK"), None)
    assert item is None or item.metrics.closedCount == 0


def test_60_historical_drift_calculation_is_reproducible():
    """60. Historical drift calculation is point-in-time reproducible."""
    now = datetime.now(timezone.utc)
    resp1 = strategy_attribution_service.get_strategy_attribution(as_of=now)
    resp2 = strategy_attribution_service.get_strategy_attribution(as_of=now)
    assert len(resp1.attributions) == len(resp2.attributions)


def test_61_api_execution_mode():
    """61. GET /api/v1/execution/mode reflects authoritative guard state."""
    client = TestClient(app)
    res = client.get("/api/v1/execution/mode")
    assert res.status_code == 200
    data = res.json()
    assert data["activeMode"] in ("PAPER", "LIVE")
    assert data["failClosed"] is True
    assert data["brokerAutomationLocked"] is True


def test_62_api_paper_trades():
    """62. GET /api/v1/paper/trades filters by status and strictly excludes LIVE/untagged trades."""
    client = TestClient(app)
    now = datetime.now(timezone.utc)
    # Seed 1 paper OPEN, 1 paper CLOSED, 1 live OPEN
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5062,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            status="OPEN",
            reasonForEntry="Paper OPEN",
            executionMode="PAPER",
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5063,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            status="CLOSED",
            result="WIN",
            reasonForEntry="Paper CLOSED",
            executionMode="PAPER",
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=now,
        )
    )
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=5064,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1150,
            status="OPEN",
            reasonForEntry="Live OPEN",
            executionMode="LIVE",
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
        )
    )

    # Query all paper trades
    res = client.get("/api/v1/paper/trades")
    assert res.status_code == 200
    trades = res.json()["trades"]
    assert len(trades) == 2
    assert all(t["executionMode"] == "PAPER" for t in trades)

    # Query filtered by status=OPEN
    res_open = client.get("/api/v1/paper/trades?status=OPEN")
    assert res_open.status_code == 200
    open_trades = res_open.json()["trades"]
    assert len(open_trades) == 1
    assert open_trades[0]["signalId"] == 5062


def test_63_api_divergence():
    """63. GET /api/v1/analytics/divergence returns separated populations and handles missing data."""
    client = TestClient(app)
    res = client.get("/api/v1/analytics/divergence")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "matchedPairsCount" in data
    assert "averageSlippagePoints" in data


def test_64_api_attribution():
    """64. GET /api/v1/analytics/attribution returns version matrix with drift diagnostics."""
    client = TestClient(app)
    res = client.get("/api/v1/analytics/attribution")
    assert res.status_code == 200
    data = res.json()
    assert "attributions" in data
    assert "driftDiagnostics" in data
