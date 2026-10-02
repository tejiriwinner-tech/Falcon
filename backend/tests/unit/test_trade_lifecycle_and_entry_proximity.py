"""
Tests for Trade Lifecycle Recording, Entry Proximity, and SL/TP Resolution.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.repository.signal_signature_repository import signal_signature_repository
from app.core.services.watchlist_poller_service import watchlist_poller_service
from app.schemas.trade_journal import TradeJournalCreate
from app.schemas.market_quote import MarketQuote, MarketQuoteResponse, BidAsk, QuoteStatus, MarketStatus


@pytest.fixture(autouse=True)
def clean_repositories():
    """Ensure clean state before and after each test."""
    trade_journal_repository.clear()
    signal_signature_repository.clear()
    yield
    trade_journal_repository.clear()
    signal_signature_repository.clear()


def test_trade_journal_and_signature_purge():
    """Verify that clearing repositories leaves 0 records."""
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=999,
            strategyId="test-strat",
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1300,
            stopLoss=1.1280,
            takeProfit=1.1340,
            timeframe="M15",
            marketSession="London",
            tradeDate=datetime.now(timezone.utc),
            status="OPEN",
            result="PENDING",
            profitLoss=0.0,
            riskReward=2.0,
            confidence=85,
            reasonForEntry="Test entry",
        )
    )
    signal_signature_repository.record_signature("EURUSD", "BUY", 1.1300, 1.1280, 1.1340, status="ACTIVE")

    assert len(trade_journal_repository.list_trades()) == 1
    assert len(signal_signature_repository.get_all_signatures()) == 1

    # Perform purge
    trade_journal_repository.clear()
    signal_signature_repository.clear()

    assert len(trade_journal_repository.list_trades()) == 0
    assert len(signal_signature_repository.get_all_signatures()) == 0


@pytest.mark.asyncio
async def test_watchlist_poller_resolves_stop_loss(monkeypatch):
    """Verify that when market hits Stop Loss, poller auto-closes trade as LOST with post-mortem."""
    # 1. Create an active OPEN trade
    open_trade = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=101,
            strategyId="london-breakout",
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1300,
            stopLoss=1.1280,
            takeProfit=1.1340,
            timeframe="M15",
            marketSession="London",
            tradeDate=datetime.now(timezone.utc),
            status="OPEN",
            result="PENDING",
            profitLoss=0.0,
            riskReward=2.0,
            confidence=85,
            reasonForEntry="Live fill",
        )
    )

    # 2. Mock provider manager returning price at 1.1275 (SL breached)
    mock_quote = MarketQuote(
        symbol="EURUSD",
        bidAsk=BidAsk(bid=1.1275, ask=1.1275, spread=0.0),
        lastPrice=1.1275,
        change=-0.0025,
        changePercent=-0.22,
        timestamp=datetime.now(timezone.utc),
        providerId="fmp",
        providerName="Financial Modeling Prep",
        quoteStatus=QuoteStatus.LIVE,
        marketStatus=MarketStatus.OPEN,
        freshnessSeconds=1.0,
    )
    from app.core.providers import provider_manager
    monkeypatch.setattr(provider_manager, "get_market_quote", lambda sym: MarketQuoteResponse(quote=mock_quote))

    # 3. Poll once
    await watchlist_poller_service.poll_once()

    # 4. Verify trade is closed as LOST
    updated = trade_journal_repository.get_trade(open_trade.id)
    assert updated is not None
    assert updated.status == "CLOSED"
    assert updated.result == "LOST"
    assert updated.exitPrice == 1.1280
    assert updated.profitLoss < 0
    assert updated.realizedRMultiple == -1.0
    assert updated.reasonForExit == "Stop Loss Hit"


@pytest.mark.asyncio
async def test_watchlist_poller_resolves_take_profit(monkeypatch):
    """Verify that when market hits Take Profit, poller auto-closes trade as WON."""
    open_trade = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=102,
            strategyId="london-momentum",
            symbol="GBPUSD",
            direction="BUY",
            entryPrice=1.3200,
            stopLoss=1.3180,
            takeProfit=1.3240,
            timeframe="M15",
            marketSession="London",
            tradeDate=datetime.now(timezone.utc),
            status="OPEN",
            result="PENDING",
            profitLoss=0.0,
            riskReward=2.0,
            confidence=85,
            reasonForEntry="Live fill",
        )
    )

    # Mock price at 1.3245 (TP reached)
    mock_quote = MarketQuote(
        symbol="GBPUSD",
        bidAsk=BidAsk(bid=1.3245, ask=1.3245, spread=0.0),
        lastPrice=1.3245,
        change=0.0045,
        changePercent=0.34,
        timestamp=datetime.now(timezone.utc),
        providerId="fmp",
        providerName="Financial Modeling Prep",
        quoteStatus=QuoteStatus.LIVE,
        marketStatus=MarketStatus.OPEN,
        freshnessSeconds=1.0,
    )
    from app.core.providers import provider_manager
    monkeypatch.setattr(provider_manager, "get_market_quote", lambda sym: MarketQuoteResponse(quote=mock_quote))

    await watchlist_poller_service.poll_once()

    updated = trade_journal_repository.get_trade(open_trade.id)
    assert updated is not None
    assert updated.status == "CLOSED"
    assert updated.result == "WON"
    assert updated.exitPrice == 1.3240
    assert updated.profitLoss > 0
    assert updated.realizedRMultiple == 2.0
