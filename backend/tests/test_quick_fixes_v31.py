"""
Verification test suite for Quick Fixes v3.1:
1. strat-024 +0.65R Fast Breakeven & 50% Scale-Out inside SignalOutcomeResolver (saves +0.75R reversals from becoming -1.0R)
2. OrderFlowEngine detect_l2_spoofing() Notional USD Scaling for Gold (XAU/USD) vs FX & TEST/USD compatibility
3. SignalGenerationEngine Single-Corridor Sequential Double-Sweep Detection
"""
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

sys.path.insert(0, "backend")

from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.order_flow_engine import order_flow_engine
from app.core.engines.session_breakout_engine import session_breakout_engine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.providers.provider_manager import MarketQuoteResponse
from app.core.repository.trade_journal_repository import InMemoryTradeJournalStorage, trade_journal_repository
from app.core.services.signal_outcome_resolver import SignalOutcomeResolver
from app.schemas.market_quote import BidAsk, MarketQuote, MarketStatus, QuoteStatus
from app.schemas.trade_journal import TradeJournalCreate


def _quote(symbol: str, px: float, spread: float = 0.25) -> MarketQuoteResponse:
    now = datetime.now(timezone.utc)
    return MarketQuoteResponse(
        quote=MarketQuote(
            symbol=symbol,
            bidAsk=BidAsk(bid=px, ask=px + spread, spread=spread),
            lastPrice=px,
            timestamp=now,
            providerId="oanda",
            providerName="OANDA",
            quoteStatus=QuoteStatus.LIVE,
            marketStatus=MarketStatus.OPEN,
        )
    )


def test_strat_024_outcome_resolver_065r_breakeven_and_scaleout():
    original_storage = trade_journal_repository._storage
    try:
        trade_journal_repository._storage = InMemoryTradeJournalStorage()
        resolver = SignalOutcomeResolver()
        now = datetime.now(timezone.utc)

        # Create open strat-024 Gold BUY trade: Entry 3850, SL 3845 ($5 risk), TP 3856 (1.2R), risk = $10
        trade = trade_journal_repository.create_trade(
            TradeJournalCreate(
                signalId=9924,
                strategyId="strat-024",
                symbol="XAU/USD",
                direction="BUY",
                timeframe="M15",
                marketSession="London",
                entryPrice=3850.00,
                stopLoss=3845.00,
                initialStopLoss=3845.00,
                takeProfit=3856.00,
                status="OPEN",
                tradeDate=now,
                confidence=88,
                notes="XAU/USD Velocity Scalp",
                initialMonetaryRisk=Decimal("10.00"),
                reasonForEntry="XAU/USD London-NY Velocity Scalp",
                fillPrice=3850.00,
                fillTime=now,
            )
        )

        # Step 1: Price reaches +0.75R (3853.75) -> MUST trigger +0.65R BE Lock & 50% scale-out
        with patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
             patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=_quote("XAU/USD", 3853.75)):
            resolver.resolve_signals()

        mid_trade = trade_journal_repository.get_trade(trade.id)
        assert mid_trade.status == "OPEN"
        assert mid_trade.stopLoss == 3850.00, f"Expected SL shifted to BE at 3850.00, got {mid_trade.stopLoss}"
        assert "BE_PROTECTED" in (mid_trade.notes or "")
        assert "TP1_SCALED_OUT_50" in (mid_trade.notes or "")
        assert "+0.65R" in (mid_trade.notes or "")

        # Step 2: Price reverses back to entry (3850.00) -> MUST close as BREAKEVEN with +0.33R banked!
        with patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
             patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=_quote("XAU/USD", 3850.00)):
            resolver.resolve_signals()

        closed_trade = trade_journal_repository.get_trade(trade.id)
        assert closed_trade.status == "CLOSED"
        assert closed_trade.result == "BREAKEVEN", f"Expected BREAKEVEN instead of LOSS, got {closed_trade.result}"
        assert closed_trade.realizedRMultiple == 0.33, f"Expected +0.33R banked (0.5*0.65R), got {closed_trade.realizedRMultiple}"
        assert closed_trade.profitLoss == 3.30
        print("strat-024 +0.65R BE lock & 50% scale-out in SignalOutcomeResolver verified!")
    finally:
        trade_journal_repository._storage = original_storage


def test_gold_notional_usd_l2_spoofing():
    # Gold @ $3,850/oz: 1,200 oz Ask wall = $4.62M USD notional, pulled down to 200 oz = $770K USD
    order_flow_engine._recent_dom_snapshots["XAUUSD"] = [(time.time() - 1.0, 1000000.0, 1200.0 * 3850.0)]
    is_spoof, note = order_flow_engine.detect_l2_spoofing(
        "XAU/USD", current_bid_liq=250.0, current_ask_liq=200.0, spot_price=3850.0
    )
    assert is_spoof is True, f"Expected Gold notional spoof detection, got {note}"
    assert "SPOOF_ASK_PULLED" in note
    assert "$4.6M" in note
    print(f"Gold Notional USD L2 Spoof Detection verified ({note})!")


def test_single_corridor_sequential_double_sweep():
    # Asian corridor (01:00 - 05:00): [1.3210, 1.3230]
    # Later bars sequentially sweep BOTH 1.3205 (below low) AND 1.3235 (above high), then close inside at 1.3220
    def _bar(hr: int, o: float, h: float, l: float, c: float) -> CandleBar:
        dt = datetime(2026, 11, 17, hr, 0, tzinfo=timezone.utc)
        return CandleBar(open=o, high=h, low=l, close=c, volume=1000.0, timestamp=int(dt.timestamp()), time=dt)

    candles = [
        _bar(1, 1.3215, 1.3230, 1.3210, 1.3220),
        _bar(5, 1.3220, 1.3228, 1.3212, 1.3225),
        _bar(8, 1.3225, 1.3228, 1.3204, 1.3222),   # Swept below Asian Low (1.3210 - 2p)
        _bar(10, 1.3222, 1.3236, 1.3218, 1.3220),  # Swept above Asian High (1.3230 + 2p), closed inside
    ]
    corridors = session_breakout_engine.compute_session_corridors("GBPUSD", candles, allow_benchmark=False)
    detected = SignalGenerationEngine._detect_single_corridor_double_sweep("GBPUSD", candles, corridors)
    assert detected is True, "Expected single-corridor sequential double-sweep detection to trigger"
    print("Single-corridor sequential double-sweep whipsaw detection verified!")


if __name__ == "__main__":
    test_strat_024_outcome_resolver_065r_breakeven_and_scaleout()
    test_gold_notional_usd_l2_spoofing()
    test_single_corridor_sequential_double_sweep()
    print("ALL QUICK FIXES v3.1 TESTS PASSED!")
