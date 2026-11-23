"""
Tests for strat-030 (NZD/USD Pacific Range Sweep & Sister-SMT)
and strat-031 (EUR/JPY Frankfurt Judas Sweep & Dual-Cross Momentum).
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from app.core.instruments.instrument_registry import instrument_registry
from app.core.engines.strategy_engine import strategy_engine
from app.schemas.strategy import StrategyStatus
from app.schemas.trade_journal import TradeJournalItem
from app.schemas.capital_guardian import ProposedTradeInput
from app.schemas.capital_cycle import CapitalCycleItem, CapitalCycleStatus
from app.core.services.capital_guardian_service import capital_guardian_service


def test_instrument_registry_nzdusd_eurjpy():
    """Verify NZDUSD and EURJPY are registered with correct precision, pip size, and provider mappings."""
    nzd = instrument_registry.get_instrument("NZDUSD")
    assert nzd is not None
    assert nzd.canonicalSymbol == "NZDUSD"
    assert nzd.pipSize == 0.0001
    assert nzd.precision == 4
    assert nzd.currency == "USD"
    assert nzd.providerMappings.get("oanda") == "NZD_USD"

    ej = instrument_registry.get_instrument("EURJPY")
    assert ej is not None
    assert ej.canonicalSymbol == "EURJPY"
    assert ej.pipSize == 0.01
    assert ej.precision == 3
    assert ej.currency == "JPY"
    assert ej.providerMappings.get("oanda") == "EUR_JPY"


def test_active_roster_contains_9_strategies():
    """Verify active roster contains exactly 9 active strategies including strat-030 and strat-031."""
    active_strategies = [s for s in strategy_engine.get_strategies() if s.status == StrategyStatus.ACTIVE]
    active_ids = {s.id for s in active_strategies}
    
    assert "strat-030" in active_ids
    assert "strat-031" in active_ids
    assert len(active_ids) == 9

    s30 = next(s for s in active_strategies if s.id == "strat-030")
    assert s30.symbol == "NZD/USD"
    assert s30.bestTimeframe == "M15"
    assert s30.minimumRiskReward >= 1.25

    s31 = next(s for s in active_strategies if s.id == "strat-031")
    assert s31.symbol == "EUR/JPY"
    assert s31.bestTimeframe == "M15"
    assert s31.minimumRiskReward >= 1.30


def test_capital_guardian_cluster_firewall_nzd_usd():
    """Verify Currency Cluster Firewall blocks NZDUSD BUY when AUDUSD BUY is already active."""
    from app.core.config import settings
    orig_gate = settings.ENABLE_CURRENCY_CLUSTER_GATE
    orig_limit = settings.MAX_CURRENCY_CLUSTER_EXPOSURE
    try:
        settings.ENABLE_CURRENCY_CLUSTER_GATE = True
        settings.MAX_CURRENCY_CLUSTER_EXPOSURE = 1

        mock_cycle = CapitalCycleItem(
            id=1,
            cycleId="cycle-test",
            cycleNumber=1,
            status=CapitalCycleStatus.ACTIVE,
            activeTradingCapital=Decimal("1000.00"),
            protectedProfit=Decimal("0.00"),
            startingCapital=Decimal("1000.00"),
            targetCapital=Decimal("5000.00"),
            totalCycles=1,
            successfulCycles=0,
            failedCycles=0,
            totalTrades=0,
            winningTrades=0,
            losingTrades=0,
            createdAt=datetime.now(timezone.utc),
            updatedAt=datetime.now(timezone.utc),
        )

        # Existing trade: Long AUD, Short USD
        existing_trade = MagicMock(spec=TradeJournalItem)
        existing_trade.symbol = "AUDUSD"
        existing_trade.direction = "BUY"
        existing_trade.lotSize = 0.1
        existing_trade.entryPrice = 0.6500
        existing_trade.stopLoss = 0.6480
        existing_trade.takeProfit = 0.6540
        existing_trade.closedAt = None

        # Proposal: BUY NZDUSD (Long NZD, Short USD -> correlates with existing Short USD)
        proposal = ProposedTradeInput(
            symbol="NZDUSD",
            direction="BUY",
            entryPrice=Decimal("0.5900"),
            stopLoss=Decimal("0.5885"),
            takeProfit=Decimal("0.5925"),
            lotSize=Decimal("0.10"),
            confidence=Decimal("88"),
            strategyId="strat-030",
        )

        decision = capital_guardian_service.evaluate_proposed_trade(
            proposal=proposal,
            active_cycle=mock_cycle,
            active_trades=[existing_trade],
        )

        assert not decision.allowed
        assert "Currency cluster limit exceeded" in decision.reason
        assert "USD" in decision.reason
    finally:
        settings.ENABLE_CURRENCY_CLUSTER_GATE = orig_gate
        settings.MAX_CURRENCY_CLUSTER_EXPOSURE = orig_limit


def test_capital_guardian_cluster_firewall_eur_jpy():
    """Verify Currency Cluster Firewall blocks EURJPY BUY when GBPJPY BUY is already active."""
    from app.core.config import settings
    orig_gate = settings.ENABLE_CURRENCY_CLUSTER_GATE
    orig_limit = settings.MAX_CURRENCY_CLUSTER_EXPOSURE
    try:
        settings.ENABLE_CURRENCY_CLUSTER_GATE = True
        settings.MAX_CURRENCY_CLUSTER_EXPOSURE = 1

        mock_cycle = CapitalCycleItem(
            id=1,
            cycleId="cycle-test",
            cycleNumber=1,
            status=CapitalCycleStatus.ACTIVE,
            activeTradingCapital=Decimal("1000.00"),
            protectedProfit=Decimal("0.00"),
            startingCapital=Decimal("1000.00"),
            targetCapital=Decimal("5000.00"),
            totalCycles=1,
            successfulCycles=0,
            failedCycles=0,
            totalTrades=0,
            winningTrades=0,
            losingTrades=0,
            createdAt=datetime.now(timezone.utc),
            updatedAt=datetime.now(timezone.utc),
        )

        # Existing trade: Long GBP, Short JPY
        existing_trade = MagicMock(spec=TradeJournalItem)
        existing_trade.symbol = "GBPJPY"
        existing_trade.direction = "BUY"
        existing_trade.lotSize = 0.1
        existing_trade.entryPrice = 190.00
        existing_trade.stopLoss = 189.50
        existing_trade.takeProfit = 191.00
        existing_trade.closedAt = None

        # Proposal: BUY EURJPY (Long EUR, Short JPY -> correlates with existing Short JPY)
        proposal = ProposedTradeInput(
            symbol="EURJPY",
            direction="BUY",
            entryPrice=Decimal("160.00"),
            stopLoss=Decimal("159.70"),
            takeProfit=Decimal("160.50"),
            lotSize=Decimal("0.10"),
            confidence=Decimal("89"),
            strategyId="strat-031",
        )

        decision = capital_guardian_service.evaluate_proposed_trade(
            proposal=proposal,
            active_cycle=mock_cycle,
            active_trades=[existing_trade],
        )

        assert not decision.allowed
        assert "Currency cluster limit exceeded" in decision.reason
        assert "JPY" in decision.reason
    finally:
        settings.ENABLE_CURRENCY_CLUSTER_GATE = orig_gate
        settings.MAX_CURRENCY_CLUSTER_EXPOSURE = orig_limit
