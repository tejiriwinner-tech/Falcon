"""
Unit tests for Falcon Capital Defense Upgrades:
- Automated Move-to-Breakeven (BE) at +1.5R (TP1)
- Risk-free Breakeven stop-out protection (+0.75R banked net)
- Economic Calendar High-Impact News Blackout Shield
- Spread-Spike Protection (> 2.0 pips limit)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from app.core.services.economic_calendar_service import economic_calendar_service
from app.core.services.watchlist_poller_service import WatchlistPollerService
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.schemas.trade_journal import TradeJournalCreate
from app.schemas.market_state import EconomicEvent


@pytest.fixture(autouse=True)
def clean_trade_journal():
    trade_journal_repository.clear()
    yield
    trade_journal_repository.clear()


def test_watchlist_poller_move_to_breakeven_at_tp1():
    """Verify that when price runs +1.5R in profit, poller moves SL to breakeven + spread."""
    poller = WatchlistPollerService(poll_interval_seconds=30)

    # Create a BUY trade: entry 1.1000, SL 1.0980 (20 pips risk), TP 1.1050 (+2.5R)
    # TP1 (+1.5R) = 1.1000 + (1.5 * 0.0020) = 1.1030
    trade = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=9901,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0980,
            takeProfit=1.1050,
            timeframe="M15",
            marketSession="London",
            tradeDate=datetime.now(timezone.utc),
            status="OPEN",
            result="PENDING",
            profitLoss=0.0,
            riskReward=2.5,
            confidence=85,
            reasonForEntry="Test Sniper Entry",
        )
    )

    # Mock market price reaching 1.1032 (beyond TP1 of 1.1030)
    mock_quote = MagicMock()
    mock_quote.quote.lastPrice = 1.1032
    mock_quote.quote.bidAsk.spread = 0.00010

    with patch("app.core.services.watchlist_poller_service.provider_manager.get_market_quote", return_value=mock_quote), \
         patch("app.core.services.signal_service.signal_service.build_signals", return_value=MagicMock(signals=[])), \
         patch("app.core.services.session_budget_manager.session_budget_manager.is_active", return_value=True):

        import asyncio
        asyncio.run(poller.poll_once())

    # Retrieve trade
    updated = trade_journal_repository.get_trade(trade.id)
    assert updated is not None
    # SL should have moved to Breakeven + spread (1.1000 + 0.00010 = 1.1001)
    assert updated.stopLoss == 1.1001
    assert "BE_PROTECTED" in (updated.notes or "")
    assert updated.status.upper() == "OPEN"


def test_watchlist_poller_breakeven_closure():
    """Verify that when a BE-protected trade is stopped out, it closes with result=BREAKEVEN (+0.75R)."""
    poller = WatchlistPollerService(poll_interval_seconds=30)

    # Trade already moved to BE with notes containing [BE_PROTECTED]
    trade = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=9902,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.1001,
            takeProfit=1.1050,
            timeframe="M15",
            marketSession="London",
            tradeDate=datetime.now(timezone.utc),
            status="OPEN",
            result="PENDING",
            profitLoss=0.0,
            riskReward=2.5,
            confidence=85,
            reasonForEntry="Test Sniper Entry",
            notes="[BE_PROTECTED: TP1 +1.5R reached at 1.1032; SL moved to 1.1001]",
        )
    )

    # Market price pulls back to 1.1000 (below SL of 1.1001)
    mock_quote = MagicMock()
    mock_quote.quote.lastPrice = 1.1000
    mock_quote.quote.bidAsk.spread = 0.00010

    with patch("app.core.services.watchlist_poller_service.provider_manager.get_market_quote", return_value=mock_quote), \
         patch("app.core.services.signal_service.signal_service.build_signals", return_value=MagicMock(signals=[])), \
         patch("app.core.services.session_budget_manager.session_budget_manager.is_active", return_value=True), \
         patch("app.core.services.signal_outcome_resolver.signal_outcome_resolver._conduct_post_mortem_learning") as mock_learn:

        import asyncio
        asyncio.run(poller.poll_once())

    updated = trade_journal_repository.get_trade(trade.id)
    assert updated is not None
    assert updated.status.upper() == "CLOSED"
    assert updated.result.upper() == "BREAKEVEN"
    assert updated.realizedRMultiple == 0.75
    assert "Break-Even" in (updated.reasonForExit or "")
    assert "Capital defended" in (updated.lessonLearned or "")


def test_economic_calendar_blackout_detection():
    """Verify that High-Impact news within 30m triggers news blackout."""
    now = datetime.now(timezone.utc)
    future_event_time = now + timedelta(minutes=18)

    dummy_event = EconomicEvent(
        title="US CPI (YoY)",
        currency="USD",
        impact="High",
        eventTime=future_event_time,
        countdownMinutes=18,
        forecast="3.1%",
        previous="3.2%",
        provider="ForexFactory",
    )

    with patch.object(economic_calendar_service, "get_events", return_value=[dummy_event]):
        is_blk, title, curr, delta, phase = economic_calendar_service.check_blackout_status("EURUSD")
        assert is_blk is True
        assert title == "US CPI (YoY)"
        assert curr == "USD"
        assert delta in (17, 18)
        assert phase == "UPCOMING"

        # Instrument without USD should not be blacked out
        is_blk_jpy, _, _, _, _ = economic_calendar_service.check_blackout_status("EURGBP")
        assert is_blk_jpy is False
