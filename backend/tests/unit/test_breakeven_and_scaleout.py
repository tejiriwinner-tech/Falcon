import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.core.services.signal_outcome_resolver import SignalOutcomeResolver
from app.schemas.trade_journal import TradeJournalItem, TradeJournalUpdate
from app.schemas.market_quote import MarketQuoteResponse, MarketQuote, BidAsk


class TestBreakevenAndScaleOut(unittest.TestCase):
    def setUp(self):
        self.resolver = SignalOutcomeResolver()

    @patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[]))
    @patch("app.core.services.signal_outcome_resolver.trade_journal_repository")
    @patch("app.core.services.signal_outcome_resolver.provider_manager")
    def test_retrace_after_1r_excursion_resolves_as_breakeven_not_loss(self, mock_pm, mock_repo, mock_sigs):
        """
        Critical Institutional Test:
        Trade enters at 1.1000 with SL=1.0980 (20 pips risk).
        Price previously reached 1.1025 (+1.25R excursion, peakPrice=1.1025).
        Price now drops back to 1.0975 (below original SL).
        BECAUSE it reached +1.25R, it MUST resolve as BREAKEVEN with $0.00 loss, NEVER LOSS!
        """
        now = datetime.now(timezone.utc)
        trade = TradeJournalItem(
            id=101,
            signalId=1001,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0980,  # 20 pips risk
            takeProfit=1.1040,  # 40 pips target (2R)
            status="OPEN",
            tradeDate=now,
            confidence=85,
            notes="Falcon Test Trade",
            peakPrice=1.1025,  # Reached +1.25R excursion!
            mfeR=1.25,
            timeframe="M15",
            marketSession="London",
            reasonForEntry="Sniper Test",
            createdAt=now,
            updatedAt=now,
            fillPrice=1.1000,
            fillTime=now,
        )
        mock_repo.list_trades.return_value = [trade]

        # Current price has retraced to 1.0975 (below initial SL)
        mock_quote = MarketQuote(
            symbol="EURUSD",
            providerId="oanda",
            providerName="OANDA",
            bid=1.0974,
            ask=1.0976,
            lastPrice=1.0975,
            spread=0.2,
            timestamp=now,
            bidAsk=BidAsk(bid=1.0974, ask=1.0976, spread=0.0002),
        )
        mock_pm.get_market_quote.return_value = MarketQuoteResponse(quote=mock_quote)

        summary = self.resolver.resolve_signals()

        # Verify update was called on trade_journal_repository
        self.assertTrue(mock_repo.update_trade.called)
        # Verify result was BREAKEVEN, not LOSS
        calls = mock_repo.update_trade.call_args_list
        final_update = calls[-1][0][1]
        self.assertIsInstance(final_update, TradeJournalUpdate)
        self.assertEqual(final_update.result, "BREAKEVEN")
        self.assertEqual(final_update.status, "CLOSED")
        self.assertGreaterEqual(final_update.profitLoss, 0.0)  # Zero loss!

    @patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[]))
    @patch("app.core.services.signal_outcome_resolver.trade_journal_repository")
    @patch("app.core.services.signal_outcome_resolver.provider_manager")
    def test_tp1_scale_out_and_subsequent_retrace_banks_profit(self, mock_pm, mock_repo, mock_sigs):
        """
        Trade reached TP1 (+1.5R excursion at 1.1030).
        Price now retraces to 1.1000 (entry).
        Resolver must credit realized_r = 0.75 (50% scale-out banked at 1.5R) and exit BREAKEVEN.
        """
        now = datetime.now(timezone.utc)
        trade = TradeJournalItem(
            id=102,
            signalId=1002,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0980,
            takeProfit=1.1060,
            status="OPEN",
            tradeDate=now,
            confidence=85,
            notes="Falcon Trade | [TP1_SCALED_OUT_50: 50% profit banked at +1.5R] | [BE_PROTECTED: Locked at entry at +1.0R]",
            peakPrice=1.1030,
            mfeR=1.5,
            timeframe="M15",
            marketSession="London",
            reasonForEntry="Sniper Test",
            createdAt=now,
            updatedAt=now,
            fillPrice=1.1000,
            fillTime=now,
        )
        mock_repo.list_trades.return_value = [trade]

        # Price retraces to entry
        mock_quote = MarketQuote(
            symbol="EURUSD",
            providerId="oanda",
            providerName="OANDA",
            bid=1.0999,
            ask=1.1001,
            lastPrice=1.1000,
            spread=0.2,
            timestamp=now,
            bidAsk=BidAsk(bid=1.0999, ask=1.1001, spread=0.0002),
        )
        mock_pm.get_market_quote.return_value = MarketQuoteResponse(quote=mock_quote)

        summary = self.resolver.resolve_signals()
        self.assertTrue(mock_repo.update_trade.called)
        final_update = mock_repo.update_trade.call_args_list[-1][0][1]
        self.assertEqual(final_update.result, "BREAKEVEN")
        self.assertEqual(final_update.realizedRMultiple, 0.75)  # 50% scale-out profit recorded!


if __name__ == "__main__":
    unittest.main()
