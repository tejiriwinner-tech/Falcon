from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.core.providers.provider_manager import MarketQuoteResponse
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.services.signal_outcome_resolver import SignalOutcomeResolver
from app.core.services.trade_intelligence_service import build_trade_intelligence
from app.schemas.market_quote import BidAsk, MarketQuote, MarketStatus, QuoteStatus


@pytest.fixture(autouse=True)
def clean_journal():
    from app.core.repository.trade_journal_repository import InMemoryTradeJournalStorage
    original_storage = trade_journal_repository._storage
    trade_journal_repository._storage = InMemoryTradeJournalStorage()
    trade_journal_repository.clear()
    yield
    trade_journal_repository.clear()
    trade_journal_repository._storage = original_storage


def make_mock_quote(symbol: str, price: float, spread: float = 0.0001) -> MarketQuoteResponse:
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


def test_buy_signal_hits_stop_loss():
    resolver = SignalOutcomeResolver()

    mock_signal = MagicMock(
        id=9901,
        symbol="EUR/USD",
        action="BUY",
        entry=1.1650,
        stopLoss=1.1620,
        takeProfit=1.1710,
        confidence=85,
        timeframe="H1",
        strategyId="strat-eur",
        strategyName="Euro Momentum",
        timestamp=datetime.now(timezone.utc),
    )

    with patch("app.core.services.signal_outcome_resolver.signal_service.build_signals") as mock_sigs, \
         patch("app.core.services.signal_outcome_resolver.mission_repository.get_all_missions", return_value=[]), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote") as mock_quote:

        mock_sigs.return_value = MagicMock(signals=[mock_signal])
        # Price has dropped below SL of 1.1620
        mock_quote.return_value = make_mock_quote("EUR/USD", 1.1610, spread=0.0004)

        summary = resolver.resolve_signals()

        assert summary.totalChecked >= 1
        assert summary.resolvedCount == 1
        assert summary.lossesCount == 1
        assert summary.winsCount == 0

        # Check Trade Journal
        trades = trade_journal_repository.list_trades()
        assert len(trades) == 1
        trade = trades[0]
        assert trade.signalId == 9901
        assert trade.status == "CLOSED"
        assert trade.result == "LOSS"
        assert trade.profitLoss < 0
        assert "Stop Loss hit" in trade.reasonForExit
        assert trade.lessonLearned is not None

        # Verify Trade Intelligence updates automatically
        intel = build_trade_intelligence()
        assert intel.totalTrades == 1
        assert intel.losingTrades == 1
        assert intel.winRate == 0.0
        assert intel.mostCommonLossReason != "N/A"


def test_buy_signal_hits_take_profit():
    resolver = SignalOutcomeResolver()

    mock_signal = MagicMock(
        id=9902,
        symbol="GBP/USD",
        action="BUY",
        entry=1.3500,
        stopLoss=1.3450,
        takeProfit=1.3600,
        confidence=90,
        timeframe="H1",
        strategyId="strat-gbp",
        strategyName="London Breakout",
        timestamp=datetime.now(timezone.utc),
    )

    with patch("app.core.services.signal_outcome_resolver.signal_service.build_signals") as mock_sigs, \
         patch("app.core.services.signal_outcome_resolver.mission_repository.get_all_missions", return_value=[]), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote") as mock_quote:

        mock_sigs.return_value = MagicMock(signals=[mock_signal])
        # Price has surged past TP of 1.3600
        mock_quote.return_value = make_mock_quote("GBP/USD", 1.3610)

        summary = resolver.resolve_signals()

        assert summary.resolvedCount == 1
        assert summary.winsCount == 1
        assert summary.lossesCount == 0

        # Check Trade Journal
        trades = trade_journal_repository.list_trades()
        assert len(trades) == 1
        trade = trades[0]
        assert trade.signalId == 9902
        assert trade.result == "WIN"
        assert trade.profitLoss > 0
        assert "Take Profit" in trade.reasonForExit

        # Verify Trade Intelligence
        intel = build_trade_intelligence()
        assert intel.totalTrades == 1
        assert intel.winningTrades == 1
        assert intel.winRate == 1.0


def test_idempotency_prevents_duplicate_journaling():
    resolver = SignalOutcomeResolver()

    mock_signal = MagicMock(
        id=9903,
        symbol="XAU/USD",
        action="BUY",
        entry=4410.0,
        stopLoss=4400.0,
        takeProfit=4430.0,
        confidence=88,
        timeframe="H1",
        strategyId="strat-gold",
        strategyName="Gold Trend",
        timestamp=datetime.now(timezone.utc),
    )

    with patch("app.core.services.signal_outcome_resolver.signal_service.build_signals") as mock_sigs, \
         patch("app.core.services.signal_outcome_resolver.mission_repository.get_all_missions", return_value=[]), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote") as mock_quote:

        mock_sigs.return_value = MagicMock(signals=[mock_signal])
        mock_quote.return_value = make_mock_quote("XAU/USD", 4395.0)

        # First resolution
        summary1 = resolver.resolve_signals()
        assert summary1.resolvedCount == 1

        # Second resolution — should skip because signal 9903 is already closed in journal
        summary2 = resolver.resolve_signals()
        assert summary2.resolvedCount == 0

        trades = trade_journal_repository.list_trades()
        assert len(trades) == 1
