import unittest
from decimal import Decimal
from datetime import datetime, timezone

from app.core.services.capital_guardian_service import CapitalGuardianService
from app.schemas.capital_cycle import CapitalCycleItem, CapitalCycleStatus
from app.schemas.capital_guardian import ProposedTradeInput
from app.schemas.trade_journal import TradeJournalItem


class DummyRepo:
    def __init__(self, trades=None):
        self._trades = trades or []

    def list_trades(self, session=None):
        return list(self._trades)


class DummyCycleService:
    def __init__(self, cycle=None):
        self._cycle = cycle

    def get_active_cycle(self, session=None):
        return self._cycle


class TestCapitalGuardianBreakeven(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.cycle = CapitalCycleItem(
            id=1,
            cycleId="cycle-test-01",
            cycleNumber=1,
            startingCapital=Decimal("20.00"),
            targetCapital=Decimal("500.00"),
            activeTradingCapital=Decimal("250.00"),
            protectedProfit=Decimal("0.00"),
            status=CapitalCycleStatus.ACTIVE,
            startedAt=self.now,
            createdAt=self.now,
            updatedAt=self.now,
        )

    def test_calculate_trade_worst_case_loss_breakeven_buy(self):
        service = CapitalGuardianService(cycle_service=DummyCycleService(self.cycle), journal_repository=DummyRepo())
        # With allow_breakeven=True, sl == entry must return Decimal("0.00")
        loss = service.calculate_trade_worst_case_loss(
            direction="BUY",
            entry_price=Decimal("158.0845"),
            stop_loss=Decimal("158.0845"),
            lot_size=Decimal("0.01"),
            symbol="USDJPY",
            allow_breakeven=True,
        )
        self.assertEqual(loss, Decimal("0.00"))

    def test_calculate_trade_worst_case_loss_breakeven_sell(self):
        service = CapitalGuardianService(cycle_service=DummyCycleService(self.cycle), journal_repository=DummyRepo())
        loss = service.calculate_trade_worst_case_loss(
            direction="SELL",
            entry_price=Decimal("1.3265"),
            stop_loss=Decimal("1.3265"),
            lot_size=Decimal("0.01"),
            symbol="GBPUSD",
            allow_breakeven=True,
        )
        self.assertEqual(loss, Decimal("0.00"))

    def test_get_trade_worst_case_loss_with_be_protected_trade(self):
        service = CapitalGuardianService(cycle_service=DummyCycleService(self.cycle), journal_repository=DummyRepo())
        trade_be = TradeJournalItem(
            id=2770,
            signalId=690009,
            strategyId="strat-009",
            symbol="USD/JPY",
            direction="BUY",
            entryPrice=158.0845,
            stopLoss=158.0845,
            takeProfit=158.752,
            timeframe="M15",
            marketSession="New York",
            tradeDate=self.now,
            status="OPEN",
            result="PENDING",
            profitLoss=0.0,
            riskReward=1.85,
            confidence=84,
            reasonForEntry="Test",
            notes="Auto-recorded | [BE_PROTECTED: Locked at entry]",
            createdAt=self.now,
            updatedAt=self.now,
        )
        worst_loss = service.get_trade_worst_case_loss(trade_be)
        self.assertEqual(worst_loss, Decimal("0.00"))

    def test_evaluate_proposed_trade_with_breakeven_trade_in_live_trades(self):
        trade_be = TradeJournalItem(
            id=2770,
            signalId=690009,
            strategyId="strat-009",
            symbol="USD/JPY",
            direction="BUY",
            entryPrice=158.0845,
            stopLoss=158.0845,
            takeProfit=158.752,
            timeframe="M15",
            marketSession="New York",
            tradeDate=self.now,
            status="OPEN",
            result="PENDING",
            profitLoss=0.0,
            riskReward=1.85,
            confidence=84,
            reasonForEntry="Test",
            notes="Auto-recorded | [BE_PROTECTED: Locked at entry]",
            createdAt=self.now,
            updatedAt=self.now,
        )
        service = CapitalGuardianService(
            cycle_service=DummyCycleService(self.cycle),
            journal_repository=DummyRepo(trades=[trade_be]),
        )
        proposal = ProposedTradeInput(
            symbol="XAUUSD",
            direction="SELL",
            entryPrice=Decimal("4143.72"),
            stopLoss=Decimal("4162.92"),
            takeProfit=Decimal("4109.16"),
            lotSize=Decimal("0.01"),
            riskReward=Decimal("1.8"),
        )
        decision = service.evaluate_proposed_trade(proposal, active_cycle=self.cycle)
        self.assertTrue(decision.allowed, f"Proposal should be allowed, but got: {decision.reason}")
        self.assertEqual(decision.currentAggregateWorstCaseLoss, Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
