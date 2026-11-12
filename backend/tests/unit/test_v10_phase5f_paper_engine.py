"""
Falcon V10 Phase 5F: Paper Trading Engine & Hard LIVE Execution Safety Guard Test Suite.
========================================================================================

Verifies all mandatory conditions:
1. Default mode is PAPER.
2. Explicit PAPER remains PAPER.
3. LIVE cannot activate without explicit affirmative acknowledgment.
4. Invalid LIVE configuration (e.g. 'REAL', 'PROD', 'YES') fails closed to PAPER.
5. Ambiguous/missing authorization fails closed to PAPER.
6. LIVE state does not automatically place a broker order (assert prohibition).
7. Authorized PAPER signal becomes PENDING with [MODE:PAPER] token.
8. PAPER fill creates OPEN state using authoritative market quote (BUY at Ask, SELL at Bid).
9. BUY TP closes correctly.
10. BUY SL closes correctly.
11. SELL TP closes correctly.
12. SELL SL closes correctly.
13. Terminal PAPER trade (CLOSED, EXPIRED, INVALIDATED) cannot receive further observations.
14. PAPER reservation is released correctly after closure (closeDate set, slot freed).
15. Duplicate active signal_id reservation remains impossible.
16. PAPER still passes Capital Guardian rules.
17. 3-trade ceiling remains enforced in PAPER mode.
18. Strict aggregate worst-case-loss invariant remains enforced in PAPER mode.
19. CRITICAL: PAPER trades CANNOT consume LIVE Guardian capacity (3 paper trades do not block LIVE).
20. CRITICAL: PAPER trades CANNOT reduce LIVE active-capital capacity or increase LIVE worst-case loss.
21. PAPER results do not modify real active trading capital or protected profit.
22. PAPER trades cannot advance or damage a LIVE capital cycle.
23. CRITICAL: Simultaneous genuine SL/TP breach resolves deterministically to Stop Loss (fail-closed).
24. Clean single SL or TP hits resolve cleanly without manufacturing false SL hits.
25. Canonical parser accepts exact tokens [MODE:PAPER] and [MODE:LIVE].
26. Ordinary text in notes (e.g. 'trading live on gold') cannot activate LIVE (returns None).
27. Malformed or conflicting tokens (e.g. '[MODE:PAPER] [MODE:LIVE]') fail closed to None.
28. Historical records without mode tags remain executionMode = None.
29. Canonical analytics separates PAPER and LIVE populations.
30. Phase 5D provenance (strategyVersion, adaptiveRuleVersion, adaptiveStopMultiplier) preserved.
31. Realized R uses persisted initial monetary risk from Capital Guardian.
32. MFE/MAE follows Phase 5C execution quality rules (post-fill only).
33. Historical PAPER evaluation passes as_of (Phase 5E lookahead protection).
34. Zero automated broker order placement, modification, closure, or cancellation.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock, patch
import pytest

from app.core.analytics.canonical_analytics_service import CanonicalAnalyticsService
from app.core.config.settings import Settings, settings
from app.core.engines.paper_trading_engine import (
    PaperTradingEngine,
    paper_trading_engine,
)
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.execution.execution_mode_guard import (
    ExecutionMode,
    ExecutionModeGuard,
    TOKEN_LIVE,
    TOKEN_PAPER,
    execution_mode_guard,
    format_mode_token,
    inject_mode_token,
    parse_execution_mode,
)
from app.core.repository.capital_cycle_repository import (
    CapitalCycleRepository,
    InMemoryCapitalCycleStorage,
)
from app.core.repository.mission_repository import (
    InMemoryMissionStorage,
    MissionRepository,
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
from app.schemas.market_quote import BidAsk, MarketQuote
from app.schemas.market_state import MarketPrice, MarketState
from app.schemas.signal_candidate import (
    CandidateCondition,
    CandidateDirection,
    CandidateMarketSnapshot,
    CandidateReason,
    CandidateStatus,
    ConfidenceBreakdown,
    SignalCandidate,
)
from app.schemas.strategy import StrategyItem, StrategyScore, StrategyStatus, StrategyType
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
            cycleId="cycle-v10-p5f-test",
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

    # Patch services
    paper_trading_engine._auth_service = auth_service
    paper_trading_engine._guardian_service = guardian_service
    paper_trading_engine._journal_repo = trade_journal_repository

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


# ==============================================================================
# 1. Mode Tests (Conditions 1 - 6)
# ==============================================================================

def test_01_default_mode_is_paper():
    """1. Default execution mode is strictly PAPER."""
    with patch.object(settings, "EXECUTION_MODE", "PAPER"), \
         patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", False):
        mode = ExecutionModeGuard.get_system_mode()
        assert mode == ExecutionMode.PAPER
        assert ExecutionModeGuard.is_paper_mode() is True
        assert ExecutionModeGuard.is_live_authorized() is False


def test_02_explicit_paper_remains_paper():
    """2. Explicit configuration of PAPER remains PAPER."""
    with patch.object(settings, "EXECUTION_MODE", "PAPER"), \
         patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", True):
        assert ExecutionModeGuard.get_system_mode() == ExecutionMode.PAPER


def test_03_live_cannot_activate_without_explicit_acknowledgment():
    """3. LIVE mode cannot activate unless LIVE_EXECUTION_ACKNOWLEDGED is True."""
    with patch.object(settings, "EXECUTION_MODE", "LIVE"), \
         patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", False):
        # Fails closed to PAPER
        assert ExecutionModeGuard.get_system_mode() == ExecutionMode.PAPER
        assert ExecutionModeGuard.is_live_authorized() is False

    # When explicitly acknowledged, LIVE activates
    with patch.object(settings, "EXECUTION_MODE", "LIVE"), \
         patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", True):
        assert ExecutionModeGuard.get_system_mode() == ExecutionMode.LIVE
        assert ExecutionModeGuard.is_live_authorized() is True


def test_04_invalid_live_configuration_fails_closed():
    """4. Invalid configurations (e.g. 'REAL', 'PROD', 'TRUE') cannot activate LIVE."""
    for invalid_val in ["REAL", "PROD", "TRUE", "1", "YES", "production", "live_trading"]:
        with patch.object(settings, "EXECUTION_MODE", invalid_val), \
             patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", True):
            assert ExecutionModeGuard.get_system_mode() == ExecutionMode.PAPER


def test_05_ambiguous_missing_authorization_fails_closed():
    """5. Missing, None, or ambiguous authorization fails closed to PAPER."""
    with patch.object(settings, "EXECUTION_MODE", None), \
         patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", None):
        assert ExecutionModeGuard.get_system_mode() == ExecutionMode.PAPER

    with patch.object(settings, "EXECUTION_MODE", ""), \
         patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", "maybe"):
        assert ExecutionModeGuard.get_system_mode() == ExecutionMode.PAPER


def test_06_live_state_does_not_place_broker_order():
    """6. Hard safety check: assert_no_broker_automation() always blocks automated broker trading."""
    with pytest.raises(RuntimeError) as exc_info:
        ExecutionModeGuard.assert_no_broker_automation()
    assert "AUTOMATED_BROKER_EXECUTION_BLOCKED" in str(exc_info.value)


# ==============================================================================
# 2. Paper Lifecycle Tests (Conditions 7 - 15)
# ==============================================================================

def test_07_authorized_paper_signal_becomes_pending_with_mode_token():
    """7. Authorized PAPER signal creates a PENDING reservation with [MODE:PAPER] token."""
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0990"),
        takeProfit=Decimal("1.1030"),
        lotSize=Decimal("0.01"),
        riskReward=Decimal("3.0"),
    )
    decision, reservation = paper_trading_engine.authorize_and_reserve_paper(
        proposal=proposal,
        signal_id=5001,
        strategy_id="SCALPING",
        timeframe="M15",
    )
    assert decision.allowed is True
    assert reservation is not None
    assert reservation.status == "PENDING"
    assert reservation.result == "PENDING"
    assert reservation.executionMode == "PAPER"
    assert TOKEN_PAPER in reservation.notes
    assert reservation.initialMonetaryRisk == decision.proposedWorstCaseLoss


def test_08_paper_fill_creates_open_state_using_authoritative_quote():
    """8. PAPER fill transitions PENDING -> OPEN using authoritative quote (BUY at Ask)."""
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0990"),
        takeProfit=Decimal("1.1030"),
        lotSize=Decimal("0.01"),
    )
    _, res = paper_trading_engine.authorize_and_reserve_paper(proposal, signal_id=5002)

    # Simulated market quote with ask = 1.1002 (0.2 pips spread)
    quote = MarketQuote(
        symbol="EURUSD",
        lastPrice=1.1000,
        bidAsk=BidAsk(bid=1.0998, ask=1.1002, spread=0.0004),
        timestamp=datetime.now(timezone.utc),
        providerId="twelvedata",
        providerName="TwelveData",
    )
    filled = paper_trading_engine.simulate_fill(trade_id=res.id, quote=quote)

    assert filled is not None
    assert filled.status == "OPEN"
    assert filled.fillPrice == 1.1002
    assert filled.fillTime is not None
    assert filled.peakPrice == 1.1002
    assert filled.troughPrice == 1.1002
    assert filled.mfeR == 0.0
    assert filled.maeR == 0.0
    assert filled.executionMode == "PAPER"
    assert filled.initialMonetaryRisk == res.initialMonetaryRisk


def test_09_buy_tp_closes_correctly():
    """9. BUY TP reached closes trade as WIN with positive PnL and realized R."""
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0990"),
        takeProfit=Decimal("1.1030"),
        lotSize=Decimal("0.01"),
    )
    _, res = paper_trading_engine.authorize_and_reserve_paper(proposal, signal_id=5003)
    paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)

    # Market reaches TP (1.1035 >= 1.1030)
    closed = paper_trading_engine.evaluate_paper_trade(
        trade_id=res.id,
        current_price=1.1035,
        bid=1.1034,
        ask=1.1036,
    )
    assert closed is not None
    assert closed.status == "CLOSED"
    assert closed.result == "WIN"
    assert closed.exitPrice == 1.1030
    assert closed.closeDate is not None
    assert closed.profitLoss > 0.0
    assert closed.realizedRMultiple is not None
    assert closed.realizedRMultiple > 0.0


def test_10_buy_sl_closes_correctly():
    """10. BUY SL reached closes trade as LOSS with negative PnL and realized R."""
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0990"),
        takeProfit=Decimal("1.1030"),
        lotSize=Decimal("0.01"),
    )
    _, res = paper_trading_engine.authorize_and_reserve_paper(proposal, signal_id=5004)
    paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)

    # Price drops to 1.0988 (<= 1.0990)
    closed = paper_trading_engine.evaluate_paper_trade(
        trade_id=res.id,
        current_price=1.0988,
        bid=1.0987,
        ask=1.0989,
    )
    assert closed is not None
    assert closed.status == "CLOSED"
    assert closed.result == "LOSS"
    assert closed.exitPrice == 1.0990
    assert closed.profitLoss < 0.0
    assert closed.realizedRMultiple is not None
    assert closed.realizedRMultiple < 0.0


def test_11_sell_tp_closes_correctly():
    """11. SELL TP reached closes trade as WIN with positive PnL."""
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="SELL",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.1010"),
        takeProfit=Decimal("1.0970"),
        lotSize=Decimal("0.01"),
    )
    _, res = paper_trading_engine.authorize_and_reserve_paper(proposal, signal_id=5005)
    paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)

    # Price drops to 1.0965 (<= 1.0970)
    closed = paper_trading_engine.evaluate_paper_trade(
        trade_id=res.id,
        current_price=1.0965,
        bid=1.0964,
        ask=1.0966,
    )
    assert closed is not None
    assert closed.status == "CLOSED"
    assert closed.result == "WIN"
    assert closed.exitPrice == 1.0970
    assert closed.profitLoss > 0.0


def test_12_sell_sl_closes_correctly():
    """12. SELL SL reached closes trade as LOSS with negative PnL."""
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="SELL",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.1010"),
        takeProfit=Decimal("1.0970"),
        lotSize=Decimal("0.01"),
    )
    _, res = paper_trading_engine.authorize_and_reserve_paper(proposal, signal_id=5006)
    paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)

    # Price rises to 1.1015 (>= 1.1010)
    closed = paper_trading_engine.evaluate_paper_trade(
        trade_id=res.id,
        current_price=1.1015,
        bid=1.1014,
        ask=1.1016,
    )
    assert closed is not None
    assert closed.status == "CLOSED"
    assert closed.result == "LOSS"
    assert closed.exitPrice == 1.1010
    assert closed.profitLoss < 0.0


def test_13_terminal_paper_trade_cannot_receive_further_observations():
    """13. Once CLOSED, EXPIRED, or INVALIDATED, no further price observations mutate the trade."""
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0990"),
        takeProfit=Decimal("1.1030"),
        lotSize=Decimal("0.01"),
    )
    _, res = paper_trading_engine.authorize_and_reserve_paper(proposal, signal_id=5007)
    paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)

    # Close as WIN
    closed = paper_trading_engine.evaluate_paper_trade(trade_id=res.id, current_price=1.1035)
    assert closed.status == "CLOSED"
    first_pnl = closed.profitLoss
    first_exit = closed.exitPrice

    # Feed an adverse price afterwards
    afterward = paper_trading_engine.evaluate_paper_trade(trade_id=res.id, current_price=1.0950)
    assert afterward.status == "CLOSED"
    assert afterward.result == "WIN"
    assert afterward.profitLoss == first_pnl
    assert afterward.exitPrice == first_exit


def test_14_paper_reservation_released_after_closure():
    """14. Paper reservation is released from reserving trades upon closure (closeDate set)."""
    guardian = paper_trading_engine._guardian_service
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0990"),
        takeProfit=Decimal("1.1030"),
        lotSize=Decimal("0.01"),
    )
    _, res = paper_trading_engine.authorize_and_reserve_paper(proposal, signal_id=5008)
    assert len(guardian.get_capital_reserving_trades(execution_mode="PAPER")) == 1

    paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)
    assert len(guardian.get_capital_reserving_trades(execution_mode="PAPER")) == 1

    # Close trade
    paper_trading_engine.evaluate_paper_trade(trade_id=res.id, current_price=1.1035)
    # Reserving count must drop to 0
    assert len(guardian.get_capital_reserving_trades(execution_mode="PAPER")) == 0


def test_15_duplicate_active_signal_id_reservation_prevented():
    """15. Re-authorizing the exact same signal_id returns existing reservation without consuming new slot."""
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0990"),
        takeProfit=Decimal("1.1030"),
        lotSize=Decimal("0.01"),
    )
    d1, r1 = paper_trading_engine.authorize_and_reserve_paper(proposal, signal_id=5009)
    assert d1.allowed is True

    # Re-authorize same signal_id
    d2, r2 = paper_trading_engine.authorize_and_reserve_paper(proposal, signal_id=5009)
    assert d2.allowed is True
    assert r2.id == r1.id
    # Only 1 trade exists
    assert len(trade_journal_repository.list_trades()) == 1


# ==============================================================================
# 3. Risk & Capital Isolation Tests (Conditions 16 - 22)
# ==============================================================================

def test_16_paper_still_passes_capital_guardian(monkeypatch):
    from app.core.config.settings import settings
    monkeypatch.setattr(settings, "NEWS_BLACKOUT_ENABLED", False)
    """16. PAPER trade must pass Capital Guardian invariants before authorization."""
    # Proposal exceeding active trading capital ($25 risk vs $20 capital)
    huge_proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0750"),  # 250 pips = $25 on 0.01 lot
        takeProfit=Decimal("1.1500"),
        lotSize=Decimal("0.01"),
    )
    decision, res = paper_trading_engine.authorize_and_reserve_paper(huge_proposal, signal_id=5010)
    assert decision.allowed is False
    assert res is None
    assert "worst-case loss" in decision.reason.lower() or "active trading capital" in decision.reason.lower()


def test_17_three_trade_ceiling_enforced_in_paper():
    """17. PAPER mode enforces the hard maximum of 3 simultaneous trades."""
    for i in range(1, 4):
        p = ProposedTradeInput(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=Decimal("1.1000"),
            stopLoss=Decimal("1.0990"),  # $1 risk each
            takeProfit=Decimal("1.1030"),
            lotSize=Decimal("0.01"),
        )
        dec, res = paper_trading_engine.authorize_and_reserve_paper(p, signal_id=5020 + i)
        assert dec.allowed is True

    # 4th trade must be rejected
    p4 = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0990"),
        takeProfit=Decimal("1.1030"),
        lotSize=Decimal("0.01"),
    )
    dec4, res4 = paper_trading_engine.authorize_and_reserve_paper(p4, signal_id=5024)
    assert dec4.allowed is False
    assert res4 is None
    assert "maximum simultaneous trade count" in dec4.reason.lower() or "3" in dec4.reason


def test_18_strict_aggregate_worst_case_loss_enforced_in_paper(monkeypatch):
    from app.core.config.settings import settings
    monkeypatch.setattr(settings, "NEWS_BLACKOUT_ENABLED", False)
    """18. Aggregate worst-case loss in PAPER cannot exceed active trading capital ($20)."""
    # 2 trades with $9.50 risk each = $19.00 <= $20.00 active capital
    p1 = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0905"),  # 95 pips = $9.50 on 0.01 lot
        takeProfit=Decimal("1.2000"),
        lotSize=Decimal("0.01"),
    )
    dec1, _ = paper_trading_engine.authorize_and_reserve_paper(p1, signal_id=5031)
    assert dec1.allowed is True

    p2 = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0905"),  # 95 pips = $9.50 on 0.01 lot
        takeProfit=Decimal("1.2000"),
        lotSize=Decimal("0.01"),
    )
    dec2, _ = paper_trading_engine.authorize_and_reserve_paper(p2, signal_id=5032)
    assert dec2.allowed is True

    # 3rd trade with $2.00 risk ($19 + $2 = $21 > $20 capital) -> rejected
    p3 = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0980"),  # 20 pips = $2.00 on 0.01 lot
        takeProfit=Decimal("1.1500"),
        lotSize=Decimal("0.01"),
    )
    dec3, _ = paper_trading_engine.authorize_and_reserve_paper(p3, signal_id=5033)
    assert dec3.allowed is False



def test_19_critical_paper_trades_cannot_consume_live_guardian_capacity():
    """
    19. CRITICAL ISOLATION: Having 3 active PAPER trades CANNOT consume LIVE Guardian capacity!
    A valid LIVE/manual signal CAN be authorized while 3 PAPER trades are active.
    """
    auth = signal_authorization_service

    # Create 3 active PAPER reservations
    for i in range(1, 4):
        p = ProposedTradeInput(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=Decimal("1.1000"),
            stopLoss=Decimal("1.0990"),  # $1.00 risk
            takeProfit=Decimal("1.1030"),
            lotSize=Decimal("0.01"),
        )
        dec, res = paper_trading_engine.authorize_and_reserve_paper(p, signal_id=6000 + i)
        assert dec.allowed is True
        paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)

    # 3 PAPER trades are OPEN
    paper_reserving = auth._guardian_service.get_capital_reserving_trades(execution_mode="PAPER")
    assert len(paper_reserving) == 3

    # LIVE reserving count must remain 0!
    live_reserving = auth._guardian_service.get_capital_reserving_trades(execution_mode="LIVE")
    assert len(live_reserving) == 0

    # A LIVE proposal MUST be allowed (LIVE capacity is completely intact!)
    live_proposal = ProposedTradeInput(
        symbol="XAUUSD",
        direction="BUY",
        entryPrice=Decimal("2000.00"),
        stopLoss=Decimal("1995.00"),  # $5.00 risk
        takeProfit=Decimal("2015.00"),
        lotSize=Decimal("0.01"),
    )
    live_decision, live_res = auth.authorize_and_reserve(
        proposal=live_proposal,
        signal_id=7001,
        execution_mode="LIVE",
    )
    assert live_decision.allowed is True, f"LIVE trade blocked by paper trades: {live_decision.reason}"
    assert live_res is not None
    assert live_decision.currentLiveTradeCount == 0  # 0 live trades prior to this one!


def test_20_critical_paper_trades_cannot_reduce_live_active_capital_capacity():
    """20. CRITICAL: PAPER aggregate loss does not reduce LIVE remaining loss capacity."""
    auth = signal_authorization_service

    # Create 2 PAPER trades with $8.00 risk each ($16.00 total paper risk)
    for i in range(1, 3):
        p = ProposedTradeInput(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=Decimal("1.1000"),
            stopLoss=Decimal("1.0920"),  # 80 pips = $8.00 on 0.01 lot
            takeProfit=Decimal("1.2000"),
            lotSize=Decimal("0.01"),
        )
        paper_trading_engine.authorize_and_reserve_paper(p, signal_id=6010 + i)

    # Now evaluate a LIVE proposal with $15.00 risk ($15.00 < $20.00 active capital).
    # If paper risk leaked into live, $16 + $15 = $31 > $20 and it would be rejected.
    live_p = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0850"),  # 150 pips = $15.00 on 0.01 lot
        takeProfit=Decimal("1.3000"),
        lotSize=Decimal("0.01"),
    )
    live_dec, live_res = auth.authorize_and_reserve(
        proposal=live_p,
        signal_id=7002,
        execution_mode="LIVE",
    )

    assert live_dec.allowed is True, f"LIVE trade falsely blocked: {live_dec.reason}"
    assert live_dec.currentAggregateWorstCaseLoss == Decimal("0.00")
    assert live_dec.proposedWorstCaseLoss == Decimal("15.00")
    assert live_dec.remainingLossCapacity == Decimal("5.00")


def test_21_paper_results_do_not_modify_real_capital_cycle(clean_test_environment):
    """21. Closing PAPER trades with profit or loss NEVER alters real active capital or protected profit."""
    cycle_service = clean_test_environment["cycle_service"]
    cycle_before = cycle_service.get_active_cycle()
    capital_before = cycle_before.activeTradingCapital
    protected_before = cycle_before.protectedProfit

    # Create and close a paper WIN (+$100 profit)
    p = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0990"),
        takeProfit=Decimal("1.1100"),
        lotSize=Decimal("0.01"),
    )
    _, res = paper_trading_engine.authorize_and_reserve_paper(p, signal_id=8001)
    paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)
    paper_trading_engine.evaluate_paper_trade(trade_id=res.id, current_price=1.1150)

    # Verify real cycle capital is 100% UNCHANGED
    cycle_after = cycle_service.get_active_cycle()
    assert cycle_after.activeTradingCapital == capital_before == Decimal("20.00")
    assert cycle_after.protectedProfit == protected_before == Decimal("0.00")
    assert cycle_after.status == CapitalCycleStatus.ACTIVE


def test_22_paper_trades_cannot_advance_or_damage_live_cycle(clean_test_environment):
    """22. PAPER trades cannot complete, halt, or transition a LIVE capital cycle."""
    cycle_service = clean_test_environment["cycle_service"]

    # Create and close a paper trade with catastrophic simulated loss
    p = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0900"),
        takeProfit=Decimal("1.1200"),
        lotSize=Decimal("0.01"),
    )
    _, res = paper_trading_engine.authorize_and_reserve_paper(p, signal_id=8002)
    paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)
    paper_trading_engine.evaluate_paper_trade(trade_id=res.id, current_price=1.0800)

    # Real cycle remains ACTIVE (not HALTED)
    cycle = cycle_service.get_active_cycle()
    assert cycle.status == CapitalCycleStatus.ACTIVE
    assert cycle.activeTradingCapital == Decimal("20.00")


# ==============================================================================
# 4. Simultaneous SL/TP Handling Tests (Conditions 23 & 24)
# ==============================================================================

def test_23_critical_simultaneous_sltp_resolves_fail_closed_to_loss():
    """
    23. CRITICAL: When a market observation indicates an ambiguous simultaneous hit
    (e.g. an extreme volatility bar where low <= SL and high >= TP),
    Falcon resolves deterministically to Stop Loss (LOSS) under fail-closed policy.
    Zero optimistic bias is permitted.
    """
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),   # SL at 1.0950
        takeProfit=Decimal("1.1100"),  # TP at 1.1100
        lotSize=Decimal("0.01"),
    )
    _, res = paper_trading_engine.authorize_and_reserve_paper(proposal, signal_id=9001)
    paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)

    # Extreme volatility bar: Low is 1.0940 (<= SL), High is 1.1110 (>= TP)
    closed = paper_trading_engine.evaluate_paper_trade(
        trade_id=res.id,
        high=1.1110,
        low=1.0940,
    )
    assert closed is not None
    assert closed.status == "CLOSED"
    assert closed.result == "LOSS"
    assert closed.exitPrice == 1.0950  # Resolved to Stop Loss
    assert "Simultaneous SL/TP breach" in closed.reasonForExit
    assert closed.profitLoss < 0.0


def test_24_clean_single_hits_resolve_normally_without_false_sl():
    """24. When only TP is reached (without SL breach), it resolves cleanly to WIN."""
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        takeProfit=Decimal("1.1100"),
        lotSize=Decimal("0.01"),
    )
    _, res = paper_trading_engine.authorize_and_reserve_paper(proposal, signal_id=9002)
    paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)

    # Normal bullish bar: High reaches TP, Low stays far above SL
    closed = paper_trading_engine.evaluate_paper_trade(
        trade_id=res.id,
        high=1.1105,
        low=1.1020,  # Far above 1.0950
    )
    assert closed is not None
    assert closed.result == "WIN"
    assert closed.exitPrice == 1.1100
    assert closed.profitLoss > 0.0


# ==============================================================================
# 5. Canonical Execution-Mode Parser Tests (Conditions 25 - 28)
# ==============================================================================

def test_25_canonical_parser_accepts_exact_tokens():
    """25. Canonical parser correctly recognizes [MODE:PAPER] and [MODE:LIVE]."""
    assert parse_execution_mode("Trade note [MODE:PAPER]") == "PAPER"
    assert parse_execution_mode("[MODE:LIVE] Auto-executed") == "LIVE"
    assert parse_execution_mode("[MODE:PAPER]") == "PAPER"
    assert parse_execution_mode("[MODE:LIVE]") == "LIVE"


def test_26_ordinary_text_cannot_activate_live():
    """26. Ordinary text in notes (e.g. 'trading live on gold') CANNOT activate LIVE."""
    assert parse_execution_mode("Trading live on Gold M15") is None
    assert parse_execution_mode("Live account testing") is None
    assert parse_execution_mode("Mode: Live") is None
    assert parse_execution_mode("mode=live") is None
    assert parse_execution_mode("[LIVE]") is None
    assert parse_execution_mode("[PAPER]") is None


def test_27_malformed_or_conflicting_tokens_fail_closed_to_none():
    """27. Malformed or conflicting tokens (both PAPER and LIVE) fail closed to None."""
    # Conflicting modes in same string
    assert parse_execution_mode("Trade note [MODE:PAPER] and [MODE:LIVE]") is None
    # Malformed tokens
    assert parse_execution_mode("[MODE:LIVEE]") is None
    assert parse_execution_mode("[MODE:PAPER_TEST]") is None
    assert parse_execution_mode("[mode:live]") is None


def test_28_historical_records_without_mode_remain_none():
    """28. Historical records without mode tags parse strictly as executionMode = None."""
    assert parse_execution_mode(None) is None
    assert parse_execution_mode("") is None
    assert parse_execution_mode("Legacy breakout test without tags") is None

    # Verify TradeJournalItem creation from legacy dict leaves executionMode None
    now = datetime.now(timezone.utc)
    item = trade_journal_repository.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            reasonForEntry="Legacy test record",
            notes="Legacy trade without mode tag",
        )
    )
    assert item.executionMode is None


# ==============================================================================
# 6. Analytics Separation & Provenance Tests (Conditions 29 - 32)
# ==============================================================================

def test_29_canonical_analytics_separates_paper_and_live_populations():
    """29. Canonical analytics does not silently mix PAPER and LIVE populations."""
    repo = trade_journal_repository
    now = datetime.now(timezone.utc)

    # Create 1 LIVE closed trade
    live_trade = repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=now - timedelta(hours=2),
            closeDate=now - timedelta(hours=1),
            fillPrice=1.1000,
            fillTime=now - timedelta(hours=2),
            status="CLOSED",
            result="WIN",
            profitLoss=50.0,
            reasonForEntry="Live trade",
            executionMode="LIVE",
        )
    )

    # Create 2 PAPER closed trades
    for i in range(2):
        repo.create_trade(
            TradeJournalCreate(
                symbol="GBPUSD",
                direction="SELL",
                entryPrice=1.3000,
                stopLoss=1.3050,
                takeProfit=1.2900,
                timeframe="M15",
                marketSession="London",
                tradeDate=now - timedelta(hours=2),
                closeDate=now - timedelta(hours=1),
                fillPrice=1.3000,
                fillTime=now - timedelta(hours=2),
                status="CLOSED",
                result="LOSS",
                profitLoss=-20.0,
                reasonForEntry="Paper trade",
                executionMode="PAPER",
            )
        )

    analytics_service = CanonicalAnalyticsService(journal_repo=repo)

    # LIVE analytics must report exactly 1 closed trade (WIN)
    live_report = analytics_service.get_live_analytics()
    assert live_report.populations.closedCount == 1
    assert live_report.closedOutcomes.wins == 1
    assert live_report.closedOutcomes.losses == 0

    # PAPER analytics must report exactly 2 closed trades (LOSSES)
    paper_report = analytics_service.get_paper_analytics()
    assert paper_report.populations.closedCount == 2
    assert paper_report.closedOutcomes.wins == 0
    assert paper_report.closedOutcomes.losses == 2


def test_30_phase5d_provenance_preserved_in_paper():
    """30. Strategy version, adaptive rule version, and multiplier are preserved in PAPER candidate."""
    now = datetime.now(timezone.utc)
    candidate = SignalCandidate(
        id="cand-paper-001",
        symbol="EURUSD",
        strategyId="MOMENTUM_BREAKOUT",
        strategyName="Momentum Breakout",
        strategyVersion="1.2.0",
        strategyGrade="A+",
        strategyScore=85,
        direction=CandidateDirection.BUY,
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
    dec, res = paper_trading_engine.authorize_paper_candidate(candidate, signal_id=9501)

    assert dec.allowed is True
    assert res.strategyVersion == "1.2.0"
    assert res.adaptiveRuleVersion == "v2.1"
    assert res.adaptiveStopMultiplier == 1.25
    assert res.spreadAtEntry == 0.0002


def test_31_realized_r_uses_persisted_initial_monetary_risk():
    """31. Realized R uses strictly persisted initial monetary risk from Capital Guardian."""
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0980"),  # 20 pips = $2.00 initial risk
        takeProfit=Decimal("1.1060"),
        lotSize=Decimal("0.01"),
    )
    _, res = paper_trading_engine.authorize_and_reserve_paper(proposal, signal_id=9502)
    assert res.initialMonetaryRisk == Decimal("2.00")

    paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)
    # Win at 1.1060 (60 pips = $6.00 profit) -> Realized R = 6.00 / 2.00 = 3.0
    closed = paper_trading_engine.evaluate_paper_trade(trade_id=res.id, current_price=1.1065)
    assert closed.status == "CLOSED"
    assert closed.realizedRMultiple == 3.0


def test_32_mfe_mae_tracks_post_fill_excursion():
    """32. MFE/MAE excursions only track post-fill prices and follow Phase 5C conventions."""
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        takeProfit=Decimal("1.1100"),
        lotSize=Decimal("0.01"),
    )
    _, res = paper_trading_engine.authorize_and_reserve_paper(proposal, signal_id=9503)
    paper_trading_engine.simulate_fill(trade_id=res.id, fill_price=1.1000)

    # In-trade observation: price rises to 1.1050 (+50 pips), dips to 1.0980 (-20 pips)
    trade_open = paper_trading_engine.evaluate_paper_trade(trade_id=res.id, current_price=1.1050)
    assert trade_open.peakPrice == 1.1050

    trade_open = paper_trading_engine.evaluate_paper_trade(trade_id=res.id, current_price=1.0980)
    assert trade_open.troughPrice == 1.0980
    assert trade_open.mfeR is not None
    assert trade_open.maeR is not None


# ==============================================================================
# 7. Lookahead Protection Tests (Condition 33)
# ==============================================================================

def test_33_historical_paper_evaluation_respects_as_of_lookahead_protection():
    """33. Historical PAPER evaluation respects as_of timestamp (zero lookahead)."""
    t0 = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    t_past = t0 - timedelta(days=2)
    t_future = t0 + timedelta(days=2)

    # Add a trade closed in the future
    repo = trade_journal_repository
    future_trade = repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t_future,
            closeDate=t_future,
            status="CLOSED",
            result="WIN",
            profitLoss=100.0,
            reasonForEntry="Future trade",
            executionMode="PAPER",
        )
    )

    # Analytics as of t0 must exclude the future trade
    analytics_service = CanonicalAnalyticsService(journal_repo=repo)
    as_of_report = analytics_service.get_canonical_analytics(analysis_timestamp=t0, execution_mode="PAPER")
    assert as_of_report.populations.closedCount == 0


# ==============================================================================
# 8. Execution Boundary Tests (Condition 34)
# ==============================================================================

def test_34_zero_automated_broker_order_execution():
    """34. Hard broker boundary: automatic order execution to MT5/Exness is completely barred."""
    from app.services.execution.cloud_mt5_service import cloud_mt5_service
    from app.services.execution.order_execution_service import order_execution_service
    from app.schemas.execution_order import ExecutionOrderCreate, OrderAction

    # Direct call to cloud_mt5_service.execute_order raises RuntimeError
    with pytest.raises(RuntimeError) as exc_info:
        cloud_mt5_service.execute_order(
            symbol="EURUSD",
            action="BUY",
            volume=0.01,
            stop_loss=1.0950,
            take_profit=1.1100,
        )
    assert "AUTOMATED_BROKER_EXECUTION_BLOCKED" in str(exc_info.value)

    # Creating an order in order_execution_service queues it as PENDING and does NOT dispatch to broker
    order_in = ExecutionOrderCreate(
        symbol="EURUSD",
        action=OrderAction.BUY,
        lot_size=0.01,
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profit=1.1100,
    )
    queued = order_execution_service.create_order(order_in)
    assert queued.status.value == "PENDING"
    assert queued.ticket_number is None  # Never auto-executed
