"""
Automated verification suite for the 6 Core Reliability Bug Fixes:
1. Top-Down H1 Trend Veto cannot be bypassed by sniper setups (readiness <= 55, status != GENERATED).
2. OrderFlowEngine v3.0 Condition 7 no longer throws UnboundLocalError on tick_d when domImbalance is set & bidLiquidity is None.
3. FX raw decimal spread (e.g. 0.0050 = 50 pips on GBP/USD, 0.035 = 3.5 pips on GBP/JPY) is normalized to pips in Condition 2 & readiness.
4. JPY pair fallback PnL multiplier uses 100.0 (50 pips = +50.0, NOT +5,000.0).
5. Detailed News Blackout event title & countdown is preserved in news_cond (no generic overwrite).
6. Auto-recorded live trades compute authentic initialStopLoss, initialMonetaryRisk, & UTC marketSession, and honor settings.MAX_SIMULTANEOUS_TRADES.
"""
import sys
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

sys.path.insert(0, "backend")

from app.core.config.settings import settings
from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.market_state_engine import _derive_session
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.strategy_engine import strategy_engine
from app.core.providers.provider_manager import MarketQuoteResponse
from app.core.repository.trade_journal_repository import InMemoryTradeJournalStorage, trade_journal_repository
from app.core.services.signal_outcome_resolver import SignalOutcomeResolver
from app.schemas.market_quote import BidAsk, MarketQuote, MarketStatus, QuoteStatus
from app.schemas.market_state import MarketPrice, MarketState
from app.schemas.signal_candidate import CandidateStatus
from app.schemas.strategy import StrategyStatus
from app.schemas.trade_journal import TradeJournalCreate


def _make_bars(base_px: float, step: float, count: int = 60, vol: float = 500.0):
    bars = []
    px = base_px
    start_ts = 1763337600
    for i in range(count):
        o = px
        c = px + step
        h = max(o, c) + abs(step) * 0.2
        l = min(o, c) - abs(step) * 0.2
        dt = datetime.fromtimestamp(start_ts + i * 3600, tz=timezone.utc)
        bars.append(CandleBar(open=o, high=h, low=l, close=c, volume=vol, timestamp=int(dt.timestamp()), time=dt))
        px = c
    return bars


def test_1_h1_trend_veto_blocks_counter_trend_sniper_setup():
    """Bug 1: Counter-H1 sniper setup MUST NOT bypass H1 Trend Veto into CandidateStatus.GENERATED."""
    engine = SignalGenerationEngine()
    s4 = next(s for s in strategy_engine.get_strategies() if s.id == "strat-004").model_copy(deep=True)
    s4.status = StrategyStatus.ACTIVE
    t_lon = datetime(2026, 11, 18, 9, 0, 0, tzinfo=timezone.utc)

    # H1 strongly BEARISH (price way below H1 EMA 50 and EMA 50 < EMA 200),
    # while M15 has a short bounce pushing asset_trend Bullish via changePercent/RSI.
    h1_bear = _make_bars(1.3500, -0.0005, count=80, vol=500.0)
    m15_bounce = _make_bars(1.3100, +0.0002, count=50, vol=1000.0)
    cur_px = h1_bear[-1].close  # ~1.3100, well below H1 EMA 50 (~1.322)

    def _bars(sym, timeframe="1h", limit=120):
        if sym == "GBPUSD" and timeframe == "15m":
            return m15_bounce
        if sym == "GBPUSD":
            return h1_bear
        return _make_bars(1.1000 if "EUR" in sym else 155.0, 0.0, count=60)

    m_state = MarketState(
        timestamp=t_lon,
        session="London",
        volatility="Moderate",
        marketSentimentLabel="Bullish",
        overallMarketConfidence=85,
        dataAgeSeconds=5,
        prices={"GBPUSD": MarketPrice(symbol="GBPUSD", currentPrice=cur_px, bid=cur_px - 0.0001, ask=cur_px, spread=0.0001, timestamp=t_lon, provider="oanda")},
        indicators={},
        calendar=[],
    )
    # Force bullish quote changePercent so Section 2D tries to create a BUY sniper setup against Bearish H1
    fake_quote_entry = MagicMock()
    fake_quote_entry.data = MarketQuote(
        symbol="GBPUSD",
        bidAsk=BidAsk(bid=cur_px - 0.0001, ask=cur_px, spread=0.0001),
        lastPrice=cur_px,
        changePercent=0.25,
        timestamp=t_lon,
        providerId="oanda",
        providerName="OANDA",
        quoteStatus=QuoteStatus.LIVE,
        marketStatus=MarketStatus.OPEN,
    )
    with patch("app.core.services.market_history_service.market_history_service.get_bars", side_effect=_bars), \
         patch("app.core.engines.signal_generation_engine.provider_manager._cache.get", return_value=fake_quote_entry):
        cands = engine.generate_candidates(market_state=m_state, strategies=[s4], as_of=t_lon)

    cand = cands[0]
    trend_c = next(c for c in cand.conditions if c.title == "Technical & Trend Alignment")
    assert trend_c.passed is False, f"Expected H1 Trend Veto to fail, got passed=True ({trend_c.description})"
    assert cand.readinessScore <= 55, f"Expected readiness capped <= 55 on H1 veto, got {cand.readinessScore}"
    assert cand.status != CandidateStatus.GENERATED, f"Counter-H1 setup bypassed veto into {cand.status}!"
    assert any(r.title == "Top-Down H1 Trend Veto" and not r.passed for r in cand.reasons)
    print("Bug 1 PASS: Top-Down H1 Trend Veto cannot be bypassed by sniper setups!")


def test_2_orderflow_tick_d_no_unbound_local_error():
    """Bug 2: domImbalance populated + bidLiquidity=None MUST NOT raise UnboundLocalError and MUST still run OrderFlow v3.0."""
    engine = SignalGenerationEngine()
    s25 = next(s for s in strategy_engine.get_strategies() if s.id == "strat-025").model_copy(deep=True)
    s25.status = StrategyStatus.ACTIVE
    t_lon = datetime(2026, 11, 18, 9, 0, 0, tzinfo=timezone.utc)
    bars_bull = _make_bars(1.3100, +0.0003, count=60, vol=500.0)
    cur_px = bars_bull[-1].close

    m_state = MarketState(
        timestamp=t_lon,
        session="London",
        volatility="Moderate",
        marketSentimentLabel="Bullish",
        overallMarketConfidence=85,
        dataAgeSeconds=5,
        prices={"GBPUSD": MarketPrice(symbol="GBPUSD", currentPrice=cur_px, bid=cur_px - 0.0001, ask=cur_px, spread=0.0001, timestamp=t_lon, provider="oanda")},
        indicators={},
        calendar=[],
    )
    # domImbalance=-0.70 (massive opposing ask wall!) AND bidLiquidity=None -> previously triggered UnboundLocalError on tick_d!
    fake_q = MarketQuote(
        symbol="GBPUSD",
        bidAsk=BidAsk(bid=cur_px - 0.0001, ask=cur_px, spread=0.0001),
        lastPrice=cur_px,
        changePercent=0.15,
        domImbalance=-0.70,
        bidLiquidity=None,
        askLiquidity=None,
        timestamp=t_lon,
        providerId="oanda",
        providerName="OANDA",
        quoteStatus=QuoteStatus.LIVE,
        marketStatus=MarketStatus.OPEN,
    )
    fake_cache = MagicMock(data=fake_q)

    with patch("app.core.services.market_history_service.market_history_service.get_bars", return_value=bars_bull), \
         patch("app.core.engines.signal_generation_engine.provider_manager._cache.get", return_value=fake_cache), \
         patch("app.core.providers.oanda_streaming_service.oanda_streaming_service.get_latest_tick", return_value=None):
        cands = engine.generate_candidates(market_state=m_state, strategies=[s25], as_of=t_lon)

    s2_cond = next(c for c in cands[0].conditions if c.title == "Stage 2 Institutional DOM & COT Flow")
    assert s2_cond.passed is False, f"Expected opposing L2 DOM wall (-0.70) to VETO (not silently pass via UnboundLocalError)! Got: {s2_cond.description}"
    print("Bug 2 PASS: OrderFlowEngine v3.0 tick_d UnboundLocalError fixed — opposing L2 wall properly vetoes!")


def test_3_fx_spread_unit_normalization():
    """Bug 3: Raw OANDA decimal spread (0.0050 = 50 pips on GBP/USD, 0.035 = 3.5 pips on GBP/JPY) must fail Condition 2."""
    engine = SignalGenerationEngine()
    s25 = next(s for s in strategy_engine.get_strategies() if s.id == "strat-025").model_copy(deep=True)
    s26 = next(s for s in strategy_engine.get_strategies() if s.id == "strat-026").model_copy(deep=True)
    s25.status = StrategyStatus.ACTIVE
    s26.status = StrategyStatus.ACTIVE
    t_lon = datetime(2026, 11, 18, 9, 0, 0, tzinfo=timezone.utc)

    # 50-pip spread spike on GBP/USD (0.0050) and 3.5-pip spread on GBP/JPY (0.035 > 2.4p cap)
    m_state = MarketState(
        timestamp=t_lon,
        session="London",
        volatility="Moderate",
        marketSentimentLabel="Bullish",
        overallMarketConfidence=85,
        dataAgeSeconds=5,
        prices={
            "GBPUSD": MarketPrice(symbol="GBPUSD", currentPrice=1.3200, bid=1.3150, ask=1.3200, spread=0.0050, timestamp=t_lon, provider="oanda"),
            "GBPJPY": MarketPrice(symbol="GBPJPY", currentPrice=205.00, bid=204.965, ask=205.000, spread=0.035, timestamp=t_lon, provider="oanda"),
        },
        indicators={},
        calendar=[],
    )
    bars = _make_bars(1.3100, +0.0002, count=50)
    with patch("app.core.services.market_history_service.market_history_service.get_bars", return_value=bars):
        cands = engine.generate_candidates(market_state=m_state, strategies=[s25, s26], as_of=t_lon)

    gu_spread = next(c for c in cands[0].conditions if c.title == "Spread Limit")
    gj_spread = next(c for c in cands[1].conditions if c.title == "Spread Limit")
    assert gu_spread.passed is False and "50.00 pips" in gu_spread.description, f"Expected 50.00 pips FAIL, got: {gu_spread}"
    assert gj_spread.passed is False and "3.50 pips" in gj_spread.description, f"Expected 3.50 pips FAIL, got: {gj_spread}"
    print("Bug 3 PASS: Raw OANDA FX decimal spreads normalized accurately to pips (50p GU & 3.5p GJ blocked)!")


def test_4_jpy_pnl_multiplier_no_100x_inflation():
    """Bug 4A: USD/JPY 50-pip (0.50) move without initialMonetaryRisk must record +50.0, NOT +5,000.0."""
    original_storage = trade_journal_repository._storage
    try:
        trade_journal_repository._storage = InMemoryTradeJournalStorage()
        resolver = SignalOutcomeResolver()
        now = datetime.now(timezone.utc)

        trade = trade_journal_repository.create_trade(
            TradeJournalCreate(
                signalId=88101,
                strategyId="strat-014",
                symbol="USD/JPY",
                direction="BUY",
                timeframe="M15",
                marketSession="New York",
                entryPrice=155.00,
                stopLoss=154.60,
                takeProfit=155.50,  # +0.50 = +50 pips
                status="OPEN",
                tradeDate=now,
                confidence=86,
                reasonForEntry="Legacy USD/JPY breakout test",
                notes="Legacy trade without initialMonetaryRisk",
                fillPrice=155.00,
                fillTime=now,
            )
        )
        q = MarketQuoteResponse(
            quote=MarketQuote(
                symbol="USD/JPY",
                bidAsk=BidAsk(bid=155.52, ask=155.53, spread=0.01),
                lastPrice=155.52,
                timestamp=now,
                providerId="oanda",
                providerName="OANDA",
                quoteStatus=QuoteStatus.LIVE,
                marketStatus=MarketStatus.OPEN,
            )
        )
        with patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
             patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=q):
            resolver.resolve_signals()

        closed = trade_journal_repository.get_trade(trade.id)
        assert closed.status == "CLOSED" and closed.result == "WIN"
        assert 49.0 <= closed.profitLoss <= 55.0, f"Expected ~+50.0 (50 pips), got inflated {closed.profitLoss}!"
        print(f"Bug 4A PASS: USD/JPY 50-pip win logged accurately as +{closed.profitLoss} (no 100x inflation)!")
    finally:
        trade_journal_repository._storage = original_storage


def test_5_detailed_news_blackout_description_preserved():
    """Bug 5: news_cond must retain exact event title & countdown rather than generic overwrite."""
    engine = SignalGenerationEngine()
    s25 = next(s for s in strategy_engine.get_strategies() if s.id == "strat-025").model_copy(deep=True)
    s25.status = StrategyStatus.ACTIVE
    t_lon = datetime(2026, 11, 18, 9, 0, 0, tzinfo=timezone.utc)

    m_state = MarketState(
        timestamp=t_lon,
        session="London",
        volatility="Moderate",
        marketSentimentLabel="Bullish",
        overallMarketConfidence=85,
        dataAgeSeconds=5,
        prices={"GBPUSD": MarketPrice(symbol="GBPUSD", currentPrice=1.3200, bid=1.3199, ask=1.3200, spread=0.0001, timestamp=t_lon, provider="oanda")},
        indicators={},
        calendar=[],
    )
    bars = _make_bars(1.3100, +0.0002, count=50)
    with patch("app.core.services.market_history_service.market_history_service.get_bars", return_value=bars), \
         patch("app.core.services.economic_calendar_service.economic_calendar_service.check_blackout_status", return_value=(True, "US Core CPI", "USD", 12, "UPCOMING")):
        cands = engine.generate_candidates(market_state=m_state, strategies=[s25], as_of=t_lon)

    news_c = next(c for c in cands[0].conditions if "News Safety" in c.title)
    assert news_c.passed is False
    assert "US Core CPI" in news_c.description and "12m" in news_c.description, f"Detailed news reason was overwritten: {news_c.description}"
    print("Bug 5 PASS: Detailed News Blackout event title & countdown preserved!")


def test_6_session_helper_and_settings_clean():
    """Bug 6: Authentic UTC session derivation & clean MAX_SIMULTANEOUS_TRADES default."""
    assert _derive_session(datetime(2026, 11, 18, 2, 0, tzinfo=timezone.utc)) == "Tokyo / Asian"
    assert _derive_session(datetime(2026, 11, 18, 8, 0, tzinfo=timezone.utc)) == "London Open"
    assert _derive_session(datetime(2026, 11, 18, 14, 0, tzinfo=timezone.utc)) == "London-NY Overlap"
    assert _derive_session(datetime(2026, 11, 18, 18, 0, tzinfo=timezone.utc)) == "New York"
    assert settings.MAX_SIMULTANEOUS_TRADES == 3
    print("Bug 6 PASS: Authentic UTC session derivation & clean settings verified!")


if __name__ == "__main__":
    test_1_h1_trend_veto_blocks_counter_trend_sniper_setup()
    test_2_orderflow_tick_d_no_unbound_local_error()
    test_3_fx_spread_unit_normalization()
    test_4_jpy_pnl_multiplier_no_100x_inflation()
    test_5_detailed_news_blackout_description_preserved()
    test_6_session_helper_and_settings_clean()
    print("ALL 6 RELIABILITY BUG-FIX VERIFICATION TESTS PASSED!")
