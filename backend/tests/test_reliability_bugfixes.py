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
from datetime import datetime, time as dt_time, timedelta, timezone
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
from app.core.services.market_history_service import PriceBar
from app.core.services.signal_authorization_service import get_rollover_window_utc
from app.core.services.signal_outcome_resolver import SignalOutcomeResolver
from app.schemas.market_quote import BidAsk, MarketQuote, MarketStatus, QuoteStatus
from app.schemas.market_state import MarketPrice, MarketState
from app.schemas.signal_candidate import CandidateDirection, CandidateStatus
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


def test_7_strat029_frankfurt_preopen_0645_to_0659_utc():
    """Edge Case 1: strat-029 MUST pass Session Match at 06:50 UTC even when _derive_session() is 'Tokyo / Asian'."""
    engine = SignalGenerationEngine()
    s29 = next(s for s in strategy_engine.get_strategies() if s.id == "strat-029").model_copy(deep=True)
    s29.status = StrategyStatus.ACTIVE
    bars = _make_bars(1.0950, +0.0002, count=50)

    t_0650 = datetime(2026, 11, 18, 6, 50, 0, tzinfo=timezone.utc)
    t_0640 = datetime(2026, 11, 18, 6, 40, 0, tzinfo=timezone.utc)

    for dt_check, expected_pass in [(t_0650, True), (t_0640, False)]:
        m_state = MarketState(
            timestamp=dt_check,
            session="Tokyo / Asian",
            volatility="Moderate",
            marketSentimentLabel="Bullish",
            overallMarketConfidence=85,
            dataAgeSeconds=5,
            prices={"EURUSD": MarketPrice(symbol="EURUSD", currentPrice=1.1050, bid=1.10494, ask=1.10500, spread=0.00006, timestamp=dt_check, provider="oanda")},
            indicators={},
            calendar=[],
        )
        with patch("app.core.services.market_history_service.market_history_service.get_bars", return_value=bars):
            cand = engine.generate_candidates(market_state=m_state, strategies=[s29], as_of=dt_check)[0]
        sess_c = next(c for c in cand.conditions if c.title == "Session Match")
        assert sess_c.passed is expected_pass, f"At {dt_check.strftime('%H:%M')} UTC expected Session Match={expected_pass}, got {sess_c.passed} ({sess_c.description})"
    print("Polish 1 PASS: strat-029 06:45-06:59 UTC Frankfurt pre-open killzone parity verified!")


def test_8_moderate_spread_spike_blocks_generated_and_prints_pips():
    """Edge Case 2: 1.2x spread spike (1.65p vs 1.4p limit) must cap readiness <= 74, block GENERATED, and print '1.65 pips'."""
    engine = SignalGenerationEngine()
    s25 = next(s for s in strategy_engine.get_strategies() if s.id == "strat-025").model_copy(deep=True)
    s25.status = StrategyStatus.ACTIVE
    t_lon = datetime(2026, 11, 18, 9, 0, 0, tzinfo=timezone.utc)
    bars = _make_bars(1.3100, +0.0003, count=50, vol=500.0)
    cur_px = bars[-1].close

    m_state = MarketState(
        timestamp=t_lon,
        session="London",
        volatility="Moderate",
        marketSentimentLabel="Bullish",
        overallMarketConfidence=85,
        dataAgeSeconds=5,
        prices={"GBPUSD": MarketPrice(symbol="GBPUSD", currentPrice=cur_px, bid=cur_px - 0.000165, ask=cur_px, spread=0.000165, timestamp=t_lon, provider="oanda")},
        indicators={},
        calendar=[],
    )
    with patch("app.core.services.market_history_service.market_history_service.get_bars", return_value=bars):
        cand = engine.generate_candidates(market_state=m_state, strategies=[s25], as_of=t_lon)[0]

    assert cand.readinessScore <= 74, f"Expected readiness <= 74 on 1.65p spread spike, got {cand.readinessScore}"
    assert cand.status != CandidateStatus.GENERATED, f"Moderate spread spike should not be GENERATED (got {cand.status})"
    assert any("1.65 pips" in r.description for r in cand.reasons), f"Expected formatted '1.65 pips' in reasons, got: {[r.description for r in cand.reasons]}"
    print("Polish 2 PASS: Moderate 1.2x spread spike blocked from GENERATED & displays formatted '1.65 pips'!")


def test_9_no_double_2pip_buffer_and_dst_rollover():
    """Edge Case 4A & 4C: Apex FX scalp stops are not double-padded by 2 pips, and rollover is DST-aware."""
    engine = SignalGenerationEngine()
    # Pre-buffered swing_low = 1.3188 (exact 12p stop below 1.3200, inside 8-18p band)
    ep, sl, tp = engine._calculate_trade_levels(
        direction=CandidateDirection.BUY,
        current_price=1.32000,
        atr=0.0020,
        symbol="GBP/USD",
        pattern_details={"swing_low": 1.31880},
        rr=1.25,
        is_scalp=True,
        strategy_id="strat-025",
    )
    assert sl == 1.31880, f"Expected exact 1.31880 (no double 2-pip padding), got {sl}"

    # DST-aware rollover window
    winter_start, winter_end = get_rollover_window_utc(datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc))
    summer_start, summer_end = get_rollover_window_utc(datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc))
    assert (winter_start, winter_end) == (dt_time(21, 50), dt_time(22, 30)), f"Winter EST mismatch: {winter_start}-{winter_end}"
    assert (summer_start, summer_end) == (dt_time(20, 50), dt_time(21, 30)), f"Summer EDT mismatch: {summer_start}-{summer_end}"
    print("Polish 4A & 4C PASS: Exact Apex FX stop buffer (no double 2p pad) & DST rollover window verified!")


def test_10_m1_replay_catches_missed_intrapoll_be_spike_and_enforces_conservative_ambiguity():
    """M1 Bar High/Low Replay: catches missed +0.65R spike between polls, ignores pre-entry bars, and enforces conservative same-bar SL."""
    original_storage = trade_journal_repository._storage
    try:
        trade_journal_repository._storage = InMemoryTradeJournalStorage()
        resolver = SignalOutcomeResolver()
        t_fill = datetime(2026, 11, 18, 9, 0, 0, tzinfo=timezone.utc)

        # Case A: strat-025 BUY @ 1.3200, SL 1.3190 (10p), TP 1.32125.
        # Live quote sits back at entry (1.3200), but M1 bar at 09:02 spiked cleanly to 1.32085 (+0.80R after half-spread)!
        t1 = trade_journal_repository.create_trade(
            TradeJournalCreate(
                signalId=77101,
                strategyId="strat-025",
                symbol="GBP/USD",
                direction="BUY",
                timeframe="M15",
                marketSession="London",
                entryPrice=1.32000,
                stopLoss=1.31900,
                initialStopLoss=1.31900,
                initialMonetaryRisk=Decimal("10.00"),
                takeProfit=1.32125,
                status="OPEN",
                tradeDate=t_fill,
                confidence=88,
                reasonForEntry="Apex Cable Scalp M1 replay test",
                notes="M1 replay BE test",
                fillPrice=1.32000,
                fillTime=t_fill,
            )
        )
        m1_bars_be = [
            # Pre-entry bar at 08:58 (MUST BE IGNORED even though it touched TP!)
            PriceBar("GBPUSD", "1m", t_fill - timedelta(minutes=2), 1.3200, 1.3250, 1.3150, 1.3200, 100.0, "OANDA"),
            # Post-fill bar at 09:02: spikes cleanly to +0.80R without touching SL -> locks +0.65R BE!
            PriceBar("GBPUSD", "1m", t_fill + timedelta(minutes=2), 1.3201, 1.32085, 1.32005, 1.3205, 150.0, "OANDA"),
            # Post-fill bar at 09:03: retraces back to entry -> closes cleanly as BREAKEVEN (+0.33R banked)!
            PriceBar("GBPUSD", "1m", t_fill + timedelta(minutes=3), 1.3205, 1.3205, 1.31995, 1.3200, 120.0, "OANDA"),
        ]
        q_at_entry = MarketQuoteResponse(
            quote=MarketQuote(
                symbol="GBP/USD",
                bidAsk=BidAsk(bid=1.32000, ask=1.32010, spread=0.00010),
                lastPrice=1.32000,
                timestamp=t_fill + timedelta(minutes=4),
                providerId="oanda",
                providerName="OANDA",
                quoteStatus=QuoteStatus.LIVE,
                marketStatus=MarketStatus.OPEN,
            )
        )
        with patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
             patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=q_at_entry), \
             patch.object(resolver, "_fetch_recent_m1_bars", return_value=m1_bars_be):
            resolver.resolve_signals()

        c1 = trade_journal_repository.get_trade(t1.id)
        assert c1.status == "CLOSED" and c1.result == "BREAKEVEN", f"Expected BREAKEVEN from M1 BE lock + retrace, got {c1.status}/{c1.result}"
        assert c1.realizedRMultiple == 0.33 and c1.profitLoss == 3.30, f"Expected +0.33R/$3.30 banked, got {c1.realizedRMultiple}/{c1.profitLoss}"

        # Case B: Conservative Same-Bar Ambiguity — single M1 bar touches BOTH initial SL and TP -> MUST resolve as LOSS!
        t2 = trade_journal_repository.create_trade(
            TradeJournalCreate(
                signalId=77102,
                strategyId="strat-025",
                symbol="GBP/USD",
                direction="BUY",
                timeframe="M15",
                marketSession="London",
                entryPrice=1.32000,
                stopLoss=1.31900,
                initialStopLoss=1.31900,
                initialMonetaryRisk=Decimal("10.00"),
                takeProfit=1.32125,
                status="OPEN",
                tradeDate=t_fill,
                confidence=88,
                reasonForEntry="Conservative same-bar test",
                notes="Ambiguous bar test",
                fillPrice=1.32000,
                fillTime=t_fill,
            )
        )
        m1_bars_ambig = [
            PriceBar("GBPUSD", "1m", t_fill + timedelta(minutes=1), 1.3200, 1.3220, 1.3185, 1.3205, 500.0, "OANDA"),
        ]
        with patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
             patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=q_at_entry), \
             patch.object(resolver, "_fetch_recent_m1_bars", return_value=m1_bars_ambig):
            resolver.resolve_signals()

        c2 = trade_journal_repository.get_trade(t2.id)
        assert c2.status == "CLOSED" and c2.result == "LOSS", f"Expected conservative LOSS on ambiguous bar, got {c2.status}/{c2.result}"
        assert c2.realizedRMultiple == -1.0 and c2.profitLoss == -10.0
        print("M1 Replay PASS: Missed intra-poll +0.65R BE spike caught (+0.33R banked), pre-entry bars ignored, & ambiguous same-bar resolves conservatively as LOSS!")
    finally:
        trade_journal_repository._storage = original_storage


if __name__ == "__main__":
    test_1_h1_trend_veto_blocks_counter_trend_sniper_setup()
    test_2_orderflow_tick_d_no_unbound_local_error()
    test_3_fx_spread_unit_normalization()
    test_4_jpy_pnl_multiplier_no_100x_inflation()
    test_5_detailed_news_blackout_description_preserved()
    test_6_session_helper_and_settings_clean()
    test_7_strat029_frankfurt_preopen_0645_to_0659_utc()
    test_8_moderate_spread_spike_blocks_generated_and_prints_pips()
    test_9_no_double_2pip_buffer_and_dst_rollover()
    test_10_m1_replay_catches_missed_intrapoll_be_spike_and_enforces_conservative_ambiguity()
    print("ALL 10 RELIABILITY, POLISH & M1 REPLAY VERIFICATION TESTS PASSED!")
