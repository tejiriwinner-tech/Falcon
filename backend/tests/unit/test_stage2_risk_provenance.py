"""
Stage 2.1 Verification: Risk Provenance Recovery Hierarchy & Unscorable Legacy Trades

Verifies the 4-level quantitative recovery hierarchy for initial risk distance:
1. Verified immutable initialStopLoss.
2. Verified stopLoss (if not yet moved to entry).
3. Documented reconstruction from original takeProfit and historical riskReward.
4. Documented reconstruction from verified entry-time ATR and stop multiplier.
5. Unrecoverable: returns (0.0, 'UNRECOVERED'), realized_r is None (unscorable), monetary P&L preserved.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.core.providers.provider_manager import MarketQuoteResponse
from app.core.repository.trade_journal_repository import InMemoryTradeJournalStorage, trade_journal_repository
from app.core.services.signal_outcome_resolver import SignalOutcomeResolver
from app.schemas.market_quote import BidAsk, MarketQuote, MarketStatus, QuoteStatus
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalItem


@pytest.fixture(autouse=True)
def clean_journal():
    orig_storage = trade_journal_repository._storage
    trade_journal_repository._storage = InMemoryTradeJournalStorage()
    trade_journal_repository.clear()
    yield
    trade_journal_repository.clear()
    trade_journal_repository._storage = orig_storage


def make_quote(symbol: str, price: float, spread: float = 0.0001) -> MarketQuoteResponse:
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


def test_provenance_level1_immutable_initial_stop_loss():
    """Level 1: If initialStopLoss is populated, it is authoritative even if current stop is at entry."""
    trade = TradeJournalItem(
        id=101,
        symbol="EUR/USD",
        direction="BUY",
        entryPrice=1.1000,
        stopLoss=1.1000,  # Moved to breakeven!
        takeProfit=1.1150,
        initialStopLoss=1.0950,  # Initial risk = 0.0050 (50 pips)
        status="OPEN",
        timeframe="H1",
        marketSession="London",
        reasonForEntry="Test Entry",
        tradeDate=datetime.now(timezone.utc),
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )
    dist, prov = SignalOutcomeResolver.recover_initial_risk_distance(trade)
    assert round(dist, 5) == 0.0050
    assert prov == "INITIAL_STOP_LOSS"


def test_provenance_level2_current_stop_loss():
    """Level 2: If initialStopLoss is None, but current stop has not moved to entry, use current stop."""
    trade = TradeJournalItem(
        id=102,
        symbol="GBP/USD",
        direction="BUY",
        entryPrice=1.3000,
        stopLoss=1.2960,  # 40 pips below entry
        takeProfit=1.3080,
        initialStopLoss=None,
        status="OPEN",
        timeframe="H1",
        marketSession="London",
        reasonForEntry="Test Entry",
        tradeDate=datetime.now(timezone.utc),
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )
    dist, prov = SignalOutcomeResolver.recover_initial_risk_distance(trade)
    assert round(dist, 5) == 0.0040
    assert prov == "CURRENT_STOP_LOSS"


def test_provenance_level3_reconstruction_from_target_and_rr():
    """Level 3: Legacy trade with stop moved to entry and initialStopLoss missing. Reconstruct from TP and riskReward."""
    trade = TradeJournalItem(
        id=103,
        symbol="USD/JPY",
        direction="BUY",
        entryPrice=150.00,
        stopLoss=150.00,  # Moved to BE
        takeProfit=151.50,  # Target dist = 1.50
        riskReward=2.0,     # Implied initial risk = 1.50 / 2.0 = 0.75
        initialStopLoss=None,
        status="OPEN",
        timeframe="H1",
        marketSession="Asian",
        reasonForEntry="Test Entry",
        tradeDate=datetime.now(timezone.utc),
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )
    dist, prov = SignalOutcomeResolver.recover_initial_risk_distance(trade)
    assert round(dist, 4) == 0.7500
    assert prov == "RECONSTRUCTED_TARGET_RR"


def test_provenance_level4_reconstruction_from_atr_at_entry():
    """Level 4: Legacy trade with stop at entry, no initialStopLoss, riskReward=0, but valid atrAtEntry."""
    trade = TradeJournalItem(
        id=104,
        symbol="GBP/JPY",
        direction="SELL",
        entryPrice=211.50,
        stopLoss=211.50,  # Moved to BE
        takeProfit=210.00,
        riskReward=0.0,   # Missing/zero RR
        atrAtEntry=0.40,  # ATR = 0.40
        adaptiveStopMultiplier=1.5,
        initialStopLoss=None,
        status="OPEN",
        timeframe="H1",
        marketSession="London",
        reasonForEntry="Test Entry",
        tradeDate=datetime.now(timezone.utc),
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )
    dist, prov = SignalOutcomeResolver.recover_initial_risk_distance(trade)
    assert round(dist, 4) == 0.6000  # 1.5 * 0.40 = 0.60
    assert prov == "RECONSTRUCTED_ATR"


def test_provenance_level5_unrecoverable_legacy_trade_marked_unscorable():
    """Level 5: Legacy trade with stop at entry, initialStopLoss None, no RR, no ATR. Excluded from R calculations."""
    trade = TradeJournalItem(
        id=105,
        symbol="AUD/USD",
        direction="BUY",
        entryPrice=0.7000,
        stopLoss=0.7000,  # Moved to BE
        takeProfit=0.7070,
        riskReward=0.0,
        atrAtEntry=None,
        initialStopLoss=None,
        status="OPEN",
        timeframe="H1",
        marketSession="London",
        reasonForEntry="Test Entry",
        tradeDate=datetime.now(timezone.utc),
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )
    dist, prov = SignalOutcomeResolver.recover_initial_risk_distance(trade)
    assert dist == 0.0
    assert prov == "UNRECOVERED"


def test_unrecoverable_trade_preserves_monetary_pnl_with_none_realized_r():
    """When an unrecoverable trade hits TP, realizedRMultiple is None (unscorable), but cash PnL is preserved."""
    resolver = SignalOutcomeResolver()
    now = datetime.now(timezone.utc)

    # Ingest unrecoverable trade into repository
    t = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=9988,
            strategyId="strat-017",
            symbol="AUD/USD",
            direction="BUY",
            entryPrice=0.7000,
            stopLoss=0.7000,  # Stop already moved to entry
            takeProfit=0.7050,
            timeframe="H1",
            marketSession="London",
            tradeDate=now,
            status="OPEN",
            result="OPEN",
            fillPrice=0.7000,
            fillTime=now,
            confidence=80,
            riskReward=0.0,
            atrAtEntry=None,
            initialStopLoss=None,
            reasonForEntry="Legacy Unrecoverable Trade",
        )
    )

    with patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=None), \
         patch("app.core.services.signal_outcome_resolver.mission_repository.get_all_missions", return_value=[]), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote") as mock_quote:

        # Price hits take profit at 0.7060
        mock_quote.return_value = make_quote("AUD/USD", 0.7060)

        summary = resolver.resolve_signals()
        assert summary.resolvedCount == 1

        updated = trade_journal_repository.get_trade(t.id)
        assert updated.status == "CLOSED"
        assert updated.result == "WIN"
        # Cash monetary PnL is accurately preserved: (0.7050 - 0.7000) * 10000 = +500.0
        assert updated.profitLoss > 0
        # Realized R is strictly None because risk denominator is unrecoverable (cannot invent an R-multiple)
        assert updated.realizedRMultiple is None
