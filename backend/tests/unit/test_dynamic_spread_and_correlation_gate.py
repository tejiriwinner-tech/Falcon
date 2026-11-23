"""
Unit tests for Currency Cluster Correlation Gate and Dynamic Spread Filters.
Verifies portfolio risk governors preventing over-exposure to correlated currencies.
"""
from decimal import Decimal
import pytest
from unittest.mock import MagicMock

from app.core.services.capital_guardian_service import CapitalGuardianService
from app.schemas.capital_cycle import CapitalCycleItem, CapitalCycleStatus
from app.schemas.capital_guardian import ProposedTradeInput
from app.schemas.trade_journal import TradeJournalItem


@pytest.fixture
def mock_cycle():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return CapitalCycleItem(
        id=1,
        cycleId="cycle-test-1",
        cycleNumber=1,
        startingCapital=Decimal("500.00"),
        targetCapital=Decimal("1000.00"),
        activeTradingCapital=Decimal("500.00"),
        protectedProfit=Decimal("0.00"),
        status=CapitalCycleStatus.ACTIVE,
        createdAt=now,
        updatedAt=now,
    )


def test_currency_cluster_gate_permits_two_trades(mock_cycle, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "ENABLE_CURRENCY_CLUSTER_GATE", True)
    monkeypatch.setattr(settings, "MAX_CURRENCY_CLUSTER_EXPOSURE", 2)
    # Setup: 1 existing BUY on EURUSD (short USD)
    existing_trade = MagicMock(spec=TradeJournalItem)
    existing_trade.symbol = "EURUSD"
    existing_trade.direction = "BUY"
    existing_trade.status = "OPEN"
    existing_trade.closeDate = None
    existing_trade.entryPrice = 1.1000
    existing_trade.stopLoss = 1.0950
    existing_trade.initialMonetaryRisk = Decimal("5.00")

    guardian = CapitalGuardianService(
        cycle_service=MagicMock(get_active_cycle=MagicMock(return_value=mock_cycle)),
        journal_repository=MagicMock(),
        instrument_registry=MagicMock(),
        monetary_risk_calculator=lambda **kw: Decimal("5.00"),
    )

    # 2nd trade: GBPUSD BUY (also short USD) -> Permitted
    proposal2 = ProposedTradeInput(
        symbol="GBPUSD",
        direction="BUY",
        entryPrice=Decimal("1.3000"),
        stopLoss=Decimal("1.2950"),
        takeProfit=Decimal("1.3150"),
        lotSize=Decimal("0.01"),
    )
    decision = guardian.evaluate_proposed_trade(
        proposal=proposal2, active_cycle=mock_cycle, active_trades=[existing_trade]
    )
    assert decision.allowed is True


def test_currency_cluster_gate_blocks_third_correlated_trade(mock_cycle, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "ENABLE_CURRENCY_CLUSTER_GATE", True)
    # Setup: 2 existing trades both short USD (EURUSD BUY and GBPUSD BUY)
    trade1 = MagicMock(spec=TradeJournalItem)
    trade1.symbol = "EURUSD"
    trade1.direction = "BUY"
    trade1.status = "OPEN"
    trade1.closeDate = None
    trade1.entryPrice = 1.1000
    trade1.stopLoss = 1.0950
    trade1.initialMonetaryRisk = Decimal("5.00")

    trade2 = MagicMock(spec=TradeJournalItem)
    trade2.symbol = "GBPUSD"
    trade2.direction = "BUY"
    trade2.status = "OPEN"
    trade2.closeDate = None
    trade2.entryPrice = 1.3000
    trade2.stopLoss = 1.2950
    trade2.initialMonetaryRisk = Decimal("5.00")

    guardian = CapitalGuardianService(
        cycle_service=MagicMock(get_active_cycle=MagicMock(return_value=mock_cycle)),
        journal_repository=MagicMock(),
        instrument_registry=MagicMock(),
        monetary_risk_calculator=lambda **kw: Decimal("5.00"),
    )

    # 3rd trade: AUDUSD BUY (would create 3rd short USD exposure) -> BLOCKED
    proposal3 = ProposedTradeInput(
        symbol="AUDUSD",
        direction="BUY",
        entryPrice=Decimal("0.6500"),
        stopLoss=Decimal("0.6450"),
        takeProfit=Decimal("0.6650"),
        lotSize=Decimal("0.01"),
    )
    decision = guardian.evaluate_proposed_trade(
        proposal=proposal3, active_cycle=mock_cycle, active_trades=[trade1, trade2]
    )
    assert decision.allowed is False
    assert "Currency cluster limit exceeded" in decision.reason
    assert "USD" in decision.reason


def test_currency_cluster_risk_percentage_cap(mock_cycle, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "ENABLE_CURRENCY_CLUSTER_GATE", True)
    monkeypatch.setattr(settings, "MAX_CURRENCY_CLUSTER_EXPOSURE", 5)  # Allow multiple trades count
    monkeypatch.setattr(settings, "MAX_CURRENCY_CLUSTER_RISK_PCT", 2.0)  # But cap risk at 2.0% ($10.00 on $500 capital)

    # 1 existing trade with $7.00 monetary risk (short USD)
    trade1 = MagicMock(spec=TradeJournalItem)
    trade1.symbol = "EURUSD"
    trade1.direction = "BUY"
    trade1.status = "OPEN"
    trade1.closeDate = None
    trade1.entryPrice = 1.1000
    trade1.stopLoss = 1.0950
    trade1.initialMonetaryRisk = Decimal("7.00")

    guardian = CapitalGuardianService(
        cycle_service=MagicMock(get_active_cycle=MagicMock(return_value=mock_cycle)),
        journal_repository=MagicMock(),
        instrument_registry=MagicMock(),
        monetary_risk_calculator=lambda **kw: Decimal("4.00"),
    )

    # 2nd proposed trade also short USD with $4.00 monetary risk:
    # Total cluster risk would be $7.00 + $4.00 = $11.00, exceeding 2.0% ($10.00) -> BLOCKED
    proposal = ProposedTradeInput(
        symbol="GBPUSD",
        direction="BUY",
        entryPrice=Decimal("1.3000"),
        stopLoss=Decimal("1.2950"),
        takeProfit=Decimal("1.3150"),
        lotSize=Decimal("0.01"),
    )
    decision = guardian.evaluate_proposed_trade(
        proposal=proposal, active_cycle=mock_cycle, active_trades=[trade1]
    )
    assert decision.allowed is False
    assert "Currency cluster risk limit exceeded" in decision.reason
    assert "USD" in decision.reason

