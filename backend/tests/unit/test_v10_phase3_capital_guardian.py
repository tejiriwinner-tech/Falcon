"""
Falcon V10 — Phase 3: Capital Guardian & 3-Trade Protection Test Suite

Validates:
1. No active cycle -> REJECT
2. Active capital = $20 -> valid baseline
3. Zero existing trades + safe proposed loss -> ALLOW
4. Exactly 3 live capital-reserving trades -> REJECT
5. Two live trades -> 3rd trade allowed, 4th strictly prevented
6. Existing exposure + proposed exposure below capital -> ALLOW
7. Existing exposure + proposed exposure exactly equal to capital -> REJECT
8. Existing exposure + proposed exposure above capital -> REJECT
9. Protected profit must not increase active risk capacity ($20 active + $460 protected -> $25 risk REJECTED)
10. Missing entry -> REJECT
11. Missing stop-loss -> REJECT
12. Invalid BUY stop-loss (SL >= Entry) -> REJECT
13. Invalid SELL stop-loss (SL <= Entry) -> REJECT
14. Invalid quantity (missing, 0, or negative) -> REJECT
15. Invalid direction -> REJECT
16. Zero or negative active capital -> REJECT
17. Decimal precision across all monetary fields (no float leakage)
18. Deterministic decision reasons
19. Existing capital-reserving states (PENDING, OPEN, FILLED counted; CLOSED, EXPIRED, INVALIDATED ignored)
20. Arbitrary caller-supplied monetaryRisk cannot bypass Guardian
21. Unsupported monetary conversion causes REJECT rather than guessing
22. Ambiguous cycle association cannot cause unsafe authorization
23. Injected custom monetary calculator support
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
import pytest

from app.core.config.settings import settings
from app.core.instruments.instrument_registry import (
    CanonicalInstrumentRegistry,
    instrument_registry,
)
from app.core.repository.capital_cycle_repository import (
    CapitalCycleRepository,
    InMemoryCapitalCycleStorage,
)
from app.core.repository.trade_journal_repository import (
    TradeJournalRepository,
    InMemoryTradeJournalStorage,
)
from app.core.services.capital_cycle_service import CapitalCycleService
from app.core.services.capital_guardian_service import CapitalGuardianService
from app.schemas.capital_cycle import CapitalCycleCreate, CapitalCycleItem, CapitalCycleStatus
from app.schemas.capital_guardian import (
    CapitalGuardianDecision,
    GuardianState,
    ProposedTradeInput,
)
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalItem


@pytest.fixture
def mem_cycle_repo() -> CapitalCycleRepository:
    storage = InMemoryCapitalCycleStorage()
    return CapitalCycleRepository(storage=storage)


@pytest.fixture
def cycle_service(mem_cycle_repo: CapitalCycleRepository) -> CapitalCycleService:
    return CapitalCycleService(repository=mem_cycle_repo)


@pytest.fixture
def mem_journal_repo() -> TradeJournalRepository:
    # Dedicated InMemory storage for isolated tests
    storage = InMemoryTradeJournalStorage()
    repo = TradeJournalRepository.__new__(TradeJournalRepository)
    repo._storage = storage
    repo.clear()
    return repo


@pytest.fixture
def registry() -> CanonicalInstrumentRegistry:
    return instrument_registry


@pytest.fixture
def guardian(
    cycle_service: CapitalCycleService,
    mem_journal_repo: TradeJournalRepository,
    registry: CanonicalInstrumentRegistry,
) -> CapitalGuardianService:
    return CapitalGuardianService(
        cycle_service=cycle_service,
        journal_repository=mem_journal_repo,
        instrument_registry=registry,
    )


def _make_active_cycle(
    cycle_service: CapitalCycleService,
    active_capital: Decimal = Decimal("20.00"),
    protected_profit: Decimal = Decimal("0.00"),
    status: CapitalCycleStatus = CapitalCycleStatus.ACTIVE,
) -> CapitalCycleItem:
    """Helper to initialize an active cycle in the repository."""
    payload = CapitalCycleCreate(
        cycleId="cycle-1",
        cycleNumber=1,
        startingCapital=Decimal("20.00"),
        targetCapital=Decimal("500.00"),
        activeTradingCapital=active_capital,
        protectedProfit=protected_profit,
        status=status,
        startedAt=datetime.now(timezone.utc),
    )
    return cycle_service._repo.create_cycle(payload)


def _make_journal_trade(
    journal_repo: TradeJournalRepository,
    symbol: str = "EURUSD",
    direction: str = "BUY",
    entry: float = 1.1000,
    sl: float = 1.0950,
    status: str = "OPEN",
    trade_date: Optional[datetime] = None,
    close_date: Optional[datetime] = None,
) -> TradeJournalItem:
    """Helper to create a trade entry in the test journal repository."""
    t_date = trade_date or datetime.now(timezone.utc)
    create_payload = TradeJournalCreate(
        symbol=symbol,
        direction=direction,
        entryPrice=entry,
        stopLoss=sl,
        takeProfit=entry + 0.0100 if direction == "BUY" else entry - 0.0100,
        timeframe="1h",
        marketSession="London / New York",
        tradeDate=t_date,
        closeDate=close_date,
        status=status,
        result=status,
        profitLoss=0.0,
        riskReward=2.0,
        confidence=85,
        reasonForEntry="Test setup",
    )
    return journal_repo.create_trade(create_payload)


# ==============================================================================
# 1. No Active Cycle -> REJECT
# ==============================================================================

def test_no_active_cycle_rejects(guardian: CapitalGuardianService):
    """When no active cycle exists, Guardian must fail closed and reject immediately."""
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        quantity=Decimal("1000"),
    )
    decision = guardian.evaluate_proposed_trade(proposal)

    assert decision.allowed is False
    assert "No active capital cycle" in decision.reason
    assert decision.state == GuardianState.HALTED
    assert decision.activeTradingCapital == Decimal("0.00")


# ==============================================================================
# 2. Active Capital = $20 -> Valid Baseline
# ==============================================================================

def test_active_capital_valid_baseline(guardian: CapitalGuardianService, cycle_service: CapitalCycleService):
    """Verify active capital baseline ($20.00) is correctly retrieved from CapitalCycleService."""
    _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        quantity=Decimal("1000"),  # Risk: 0.0050 * 1000 = $5.00
    )
    decision = guardian.evaluate_proposed_trade(proposal)

    assert decision.allowed is True
    assert decision.activeTradingCapital == Decimal("20.00")
    assert decision.proposedWorstCaseLoss == Decimal("5.00")
    assert decision.remainingLossCapacity == Decimal("15.00")
    assert decision.state == GuardianState.NORMAL


# ==============================================================================
# 3. Zero Existing Trades + Safe Proposed Loss -> ALLOW
# ==============================================================================

def test_zero_existing_trades_safe_loss_allows(guardian: CapitalGuardianService, cycle_service: CapitalCycleService):
    """With 0 active trades and proposed loss < active capital ($5.00 < $20.00), trade is permitted."""
    _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        quantity=Decimal("1000"),
    )
    decision = guardian.evaluate_proposed_trade(proposal)

    assert decision.allowed is True
    assert decision.currentLiveTradeCount == 0
    assert decision.aggregateWorstCaseLossAfter == Decimal("5.00")
    assert "permitted" in decision.reason.lower()


# ==============================================================================
# 4. Exactly 3 Live Capital-Reserving Trades -> REJECT
# ==============================================================================

def test_exactly_3_live_trades_rejects(
    guardian: CapitalGuardianService,
    cycle_service: CapitalCycleService,
    mem_journal_repo: TradeJournalRepository,
):
    """Hard 3-Trade Limit: Exactly 3 capital-reserving trades exist -> REJECT any new trade."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))

    # Create 3 live trades: 2 OPEN, 1 PENDING
    _make_journal_trade(mem_journal_repo, symbol="EURUSD", status="OPEN", entry=1.1000, sl=1.0990)
    _make_journal_trade(mem_journal_repo, symbol="GBPUSD", status="OPEN", entry=1.3000, sl=1.2990)
    _make_journal_trade(mem_journal_repo, symbol="EURUSD", status="PENDING", entry=1.1100, sl=1.1090)

    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0990"),
        quantity=Decimal("100"),
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is False
    assert "Maximum simultaneous capital-reserving trades (3) reached" in decision.reason
    assert decision.currentLiveTradeCount == 3


# ==============================================================================
# 5. Two Live Trades -> 3rd Allowed, 4th Strictly Prevented
# ==============================================================================

def test_two_live_trades_allows_3rd_rejects_4th(
    guardian: CapitalGuardianService,
    cycle_service: CapitalCycleService,
    mem_journal_repo: TradeJournalRepository,
):
    """Verify that with 2 active trades, trade #3 is allowed, but trade #4 is strictly rejected."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))

    _make_journal_trade(mem_journal_repo, symbol="EURUSD", status="OPEN", entry=1.1000, sl=1.0980)  # loss = $2.00
    _make_journal_trade(mem_journal_repo, symbol="GBPUSD", status="OPEN", entry=1.3000, sl=1.2980)  # loss = $2.00

    # 3rd trade proposed (loss = $2.00, total = $6.00 < $20.00)
    proposal3 = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0980"),
        quantity=Decimal("1000"),
    )
    decision3 = guardian.evaluate_proposed_trade(proposal3, active_cycle=cycle)
    assert decision3.allowed is True
    assert decision3.currentLiveTradeCount == 2

    # Now add trade 3 to repository to simulate it being placed
    _make_journal_trade(mem_journal_repo, symbol="EURUSD", status="PENDING", entry=1.1000, sl=1.0980)

    # 4th trade proposed
    proposal4 = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0980"),
        quantity=Decimal("1000"),
    )
    decision4 = guardian.evaluate_proposed_trade(proposal4, active_cycle=cycle)
    assert decision4.allowed is False
    assert "Maximum simultaneous capital-reserving trades (3) reached" in decision4.reason
    assert decision4.currentLiveTradeCount == 3


# ==============================================================================
# 6. Existing Exposure + Proposed Exposure Below Capital -> ALLOW
# ==============================================================================

def test_existing_plus_proposed_below_capital_allows(
    guardian: CapitalGuardianService,
    cycle_service: CapitalCycleService,
    mem_journal_repo: TradeJournalRepository,
):
    """Existing worst-case loss ($5.00) + proposed ($10.00) = $15.00 < $20.00 -> ALLOW."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))
    _make_journal_trade(mem_journal_repo, symbol="EURUSD", status="OPEN", entry=1.1000, sl=1.0950)  # 0.0050 * 1000 = $5.00

    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0900"),
        quantity=Decimal("1000"),  # 0.0100 * 1000 = $10.00
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is True
    assert decision.currentAggregateWorstCaseLoss == Decimal("5.00")
    assert decision.proposedWorstCaseLoss == Decimal("10.00")
    assert decision.aggregateWorstCaseLossAfter == Decimal("15.00")
    assert decision.remainingLossCapacity == Decimal("5.00")


# ==============================================================================
# 7. Existing Exposure + Proposed Exposure Exactly Equal to Capital -> REJECT
# ==============================================================================

def test_existing_plus_proposed_exactly_equal_capital_rejects(
    guardian: CapitalGuardianService,
    cycle_service: CapitalCycleService,
    mem_journal_repo: TradeJournalRepository,
):
    """Invariant: aggregate loss cannot EQUAL active capital ($5.00 + $15.00 = $20.00 == $20.00 -> REJECT)."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))
    _make_journal_trade(mem_journal_repo, symbol="EURUSD", status="OPEN", entry=1.1000, sl=1.0950)  # $5.00

    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0850"),
        quantity=Decimal("1000"),  # 0.0150 * 1000 = $15.00
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is False
    assert decision.aggregateWorstCaseLossAfter == Decimal("20.00")
    assert "equal or exceed" in decision.reason


# ==============================================================================
# 8. Existing Exposure + Proposed Exposure Above Capital -> REJECT
# ==============================================================================

def test_existing_plus_proposed_above_capital_rejects(
    guardian: CapitalGuardianService,
    cycle_service: CapitalCycleService,
    mem_journal_repo: TradeJournalRepository,
):
    """Aggregate loss ($5.00 + $16.00 = $21.00 > $20.00) -> REJECT."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))
    _make_journal_trade(mem_journal_repo, symbol="EURUSD", status="OPEN", entry=1.1000, sl=1.0950)  # $5.00

    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0840"),
        quantity=Decimal("1000"),  # 0.0160 * 1000 = $16.00
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is False
    assert decision.aggregateWorstCaseLossAfter == Decimal("21.00")
    assert "equal or exceed" in decision.reason


# ==============================================================================
# 9. Protected Profit Must Not Increase Active Risk Capacity
# ==============================================================================

def test_protected_profit_does_not_increase_risk_capacity(
    guardian: CapitalGuardianService,
    cycle_service: CapitalCycleService,
):
    """
    Active Capital: $20.00
    Protected Profit: $460.00 (from previous completed cycle)
    Proposed Trade Loss: $25.00
    Even though $20 + $460 = $480, risk capacity is strictly $20.00 -> MUST REJECT!
    """
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"), protected_profit=Decimal("460.00"))

    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0750"),
        quantity=Decimal("1000"),  # 0.0250 * 1000 = $25.00
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is False
    assert decision.activeTradingCapital == Decimal("20.00")
    assert decision.protectedProfit == Decimal("460.00")
    assert decision.proposedWorstCaseLoss == Decimal("25.00")
    assert "equal or exceed" in decision.reason


# ==============================================================================
# 10. Missing Entry -> REJECT
# ==============================================================================

def test_missing_entry_rejects(guardian: CapitalGuardianService, cycle_service: CapitalCycleService):
    """Fail closed when entry price is invalid or zero."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("0.00"),
        stopLoss=Decimal("1.0950"),
        quantity=Decimal("1000"),
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is False
    assert "entry price" in decision.reason.lower()


# ==============================================================================
# 11. Missing Stop-Loss -> REJECT
# ==============================================================================

def test_missing_stop_loss_rejects(guardian: CapitalGuardianService, cycle_service: CapitalCycleService):
    """Fail closed when stop-loss is missing or zero."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("0.00"),
        quantity=Decimal("1000"),
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is False
    assert "stop loss" in decision.reason.lower()


# ==============================================================================
# 12. Invalid BUY Stop-Loss -> REJECT
# ==============================================================================

def test_invalid_buy_stop_loss_rejects(guardian: CapitalGuardianService, cycle_service: CapitalCycleService):
    """For BUY trades, stop loss >= entry price must be strictly rejected."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.1050"),  # SL above entry!
        quantity=Decimal("1000"),
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is False
    assert "strictly below entry" in decision.reason


# ==============================================================================
# 13. Invalid SELL Stop-Loss -> REJECT
# ==============================================================================

def test_invalid_sell_stop_loss_rejects(guardian: CapitalGuardianService, cycle_service: CapitalCycleService):
    """For SELL trades, stop loss <= entry price must be strictly rejected."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="SELL",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),  # SL below entry!
        quantity=Decimal("1000"),
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is False
    assert "strictly above entry" in decision.reason


# ==============================================================================
# 14. Invalid Quantity -> REJECT
# ==============================================================================

def test_invalid_quantity_rejects(guardian: CapitalGuardianService, cycle_service: CapitalCycleService):
    """Quantity missing, zero, or negative must fail closed."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))

    # Quantity is None and lotSize is None
    proposal1 = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        quantity=None,
        lotSize=None,
    )
    decision1 = guardian.evaluate_proposed_trade(proposal1, active_cycle=cycle)
    assert decision1.allowed is False
    assert "position sizing" in decision1.reason.lower()

    # Quantity <= 0
    proposal2 = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        quantity=Decimal("-100"),
    )
    decision2 = guardian.evaluate_proposed_trade(proposal2, active_cycle=cycle)
    assert decision2.allowed is False
    assert "strictly positive" in decision2.reason.lower()


# ==============================================================================
# 15. Invalid Direction -> REJECT
# ==============================================================================

def test_invalid_direction_rejects(guardian: CapitalGuardianService, cycle_service: CapitalCycleService):
    """Direction must be strictly BUY or SELL."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="HOLD",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        quantity=Decimal("1000"),
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is False
    assert "trade direction" in decision.reason.lower()


# ==============================================================================
# 16. Zero or Negative Active Capital -> REJECT
# ==============================================================================

def test_zero_or_negative_active_capital_rejects(guardian: CapitalGuardianService, cycle_service: CapitalCycleService):
    """If active trading capital is $0.00 or depleted negative, new trades are blocked and Guardian halts."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("0.00"))
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        quantity=Decimal("1000"),
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is False
    assert "zero or negative" in decision.reason
    assert decision.state == GuardianState.HALTED


# ==============================================================================
# 17. Decimal Precision / No Float Leakage
# ==============================================================================

def test_decimal_precision_strict(guardian: CapitalGuardianService, cycle_service: CapitalCycleService):
    """All monetary outputs must be Decimal with no binary floating-point representation."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.10555"),
        stopLoss=Decimal("1.10222"),
        quantity=Decimal("1000"),
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert isinstance(decision.activeTradingCapital, Decimal)
    assert isinstance(decision.protectedProfit, Decimal)
    assert isinstance(decision.currentAggregateWorstCaseLoss, Decimal)
    assert isinstance(decision.proposedWorstCaseLoss, Decimal)
    assert isinstance(decision.aggregateWorstCaseLossAfter, Decimal)
    assert isinstance(decision.remainingLossCapacity, Decimal)


# ==============================================================================
# 18. Deterministic Decision Reason
# ==============================================================================

def test_deterministic_decision_reason(guardian: CapitalGuardianService, cycle_service: CapitalCycleService):
    """Decision reasons must be explicit, consistent, and deterministic."""
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))
    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        quantity=Decimal("1000"),
    )
    d1 = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)
    d2 = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert d1.allowed == d2.allowed == True
    assert d1.reason == d2.reason == "Trade permitted under capital guardian rules"


# ==============================================================================
# 19. Existing Capital-Reserving States (Lifecycle Semantics)
# ==============================================================================

def test_lifecycle_capital_reserving_semantics(
    guardian: CapitalGuardianService,
    cycle_service: CapitalCycleService,
    mem_journal_repo: TradeJournalRepository,
):
    """
    Confirmed Lifecycle Semantics:
    - PENDING: reserves capital
    - OPEN: reserves capital
    - FILLED: reserves capital
    - CLOSED: capital released
    - EXPIRED: capital released
    - INVALIDATED: capital released
    """
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))

    # Non-reserving trades (must NOT count)
    _make_journal_trade(mem_journal_repo, status="CLOSED", close_date=datetime.now(timezone.utc))
    _make_journal_trade(mem_journal_repo, status="EXPIRED", close_date=datetime.now(timezone.utc))
    _make_journal_trade(mem_journal_repo, status="INVALIDATED", close_date=datetime.now(timezone.utc))

    reserving = guardian.get_capital_reserving_trades(active_cycle=cycle)
    assert len(reserving) == 0

    # Reserving trades (MUST count)
    _make_journal_trade(mem_journal_repo, status="PENDING")
    _make_journal_trade(mem_journal_repo, status="OPEN")
    _make_journal_trade(mem_journal_repo, status="FILLED")

    reserving_after = guardian.get_capital_reserving_trades(active_cycle=cycle)
    assert len(reserving_after) == 3


# ==============================================================================
# 20. Arbitrary Caller-Supplied monetaryRisk Cannot Bypass Guardian
# ==============================================================================

def test_arbitrary_monetary_risk_cannot_bypass(
    guardian: CapitalGuardianService,
    cycle_service: CapitalCycleService,
):
    """
    An arbitrary caller passing monetaryRisk = $0.50 (with isVerifiedRisk=False)
    MUST NOT bypass validation. The Guardian must reject it fail-closed.
    """
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))

    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        quantity=Decimal("1000"),
        monetaryRisk=Decimal("0.50"),  # Arbitrary claimed risk
        isVerifiedRisk=False,          # Not verified!
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is False
    assert "Unverified monetaryRisk input rejected" in decision.reason


# ==============================================================================
# 21. Unsupported Monetary Conversion Causes REJECT Rather Than Guessing
# ==============================================================================

def test_unsupported_instrument_conversion_rejects(
    guardian: CapitalGuardianService,
    cycle_service: CapitalCycleService,
):
    """
    For an instrument with non-USD quote currency (e.g. USDJPY where currency is JPY)
    or an unknown instrument, the Guardian must fail closed rather than guessing FX conversion.
    """
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))

    # USDJPY (quote currency is JPY, no live exchange rate conversion available)
    proposal_jpy = ProposedTradeInput(
        symbol="USDJPY",
        direction="BUY",
        entryPrice=Decimal("150.00"),
        stopLoss=Decimal("149.50"),
        quantity=Decimal("1000"),
    )
    decision_jpy = guardian.evaluate_proposed_trade(proposal_jpy, active_cycle=cycle)

    assert decision_jpy.allowed is False
    assert "quote currency is 'JPY'" in decision_jpy.reason

    # Unknown instrument
    proposal_unknown = ProposedTradeInput(
        symbol="EXOTIC_PAIR",
        direction="BUY",
        entryPrice=Decimal("10.00"),
        stopLoss=Decimal("9.00"),
        quantity=Decimal("100"),
    )
    decision_unknown = guardian.evaluate_proposed_trade(proposal_unknown, active_cycle=cycle)

    assert decision_unknown.allowed is False
    assert "not registered" in decision_unknown.reason


# ==============================================================================
# 22. Ambiguous Cycle Association Cannot Cause Unsafe Authorization
# ==============================================================================

def test_ambiguous_cycle_association_fails_closed(
    guardian: CapitalGuardianService,
    cycle_service: CapitalCycleService,
    mem_journal_repo: TradeJournalRepository,
):
    """
    If existing trade exposure cannot be reliably calculated (e.g. invalid existing trade),
    the Guardian fails closed and refuses to authorize new risk.
    """
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))

    # Create an invalid open trade (SL breached or non-USD)
    _make_journal_trade(
        mem_journal_repo,
        symbol="USDJPY",  # JPY cannot be reliably converted in existing layer
        status="OPEN",
        entry=150.00,
        sl=149.00,
    )

    proposal = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        quantity=Decimal("1000"),
    )
    decision = guardian.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is False
    assert "Failed to calculate existing trade exposure" in decision.reason


# ==============================================================================
# 23. Custom Injected Monetary Risk Calculator Support
# ==============================================================================

def test_custom_injected_monetary_calculator(
    cycle_service: CapitalCycleService,
    mem_journal_repo: TradeJournalRepository,
    registry: CanonicalInstrumentRegistry,
):
    """Demonstrates pluggable authoritative broker/MT5 converter support for future Phase 4."""
    def mock_authoritative_calculator(**kwargs):
        # Deterministic loss calculator: $4.50
        return Decimal("4.50")

    service = CapitalGuardianService(
        cycle_service=cycle_service,
        journal_repository=mem_journal_repo,
        instrument_registry=registry,
        monetary_risk_calculator=mock_authoritative_calculator,
    )
    cycle = _make_active_cycle(cycle_service, active_capital=Decimal("20.00"))

    proposal = ProposedTradeInput(
        symbol="USDJPY",
        direction="BUY",
        entryPrice=Decimal("150.00"),
        stopLoss=Decimal("149.50"),
        quantity=Decimal("1000"),
    )
    decision = service.evaluate_proposed_trade(proposal, active_cycle=cycle)

    assert decision.allowed is True
    assert decision.proposedWorstCaseLoss == Decimal("4.50")
    assert decision.remainingLossCapacity == Decimal("15.50")
