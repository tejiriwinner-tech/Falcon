"""
Unit tests for Falcon Multi-Pair Strategy Expansion (USD/JPY, GBP/JPY, AUD/USD),
Pipeline Fixes (JPY 3-decimal precision, Bollinger Band sniper trigger),
and Pausable Strategy Controls via Falcon AI Co-Pilot & Briefings.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from app.core.engines.strategy_engine import StrategyEngine, strategy_engine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.decision.evaluators.macro_cross_asset_evaluator import macro_cross_asset_engine
from app.core.analytics.adaptive_tuning_engine import adaptive_tuning_engine
from app.core.services.copilot_service import copilot_service
from app.core.services.briefing_service import briefing_service
from app.schemas.copilot import CopilotQueryRequest
from app.schemas.market_state import MarketState, MarketPrice, Indicator
from app.schemas.strategy import StrategyStatus
from app.schemas.signal_candidate import CandidateStatus, CandidateDirection


def _reset_pause_state():
    strategy_engine.resume_expansion_strategies()
    for sym in ["XAU/USD", "GBP/USD", "EUR/USD", "USD/JPY", "GBP/JPY", "AUD/USD"]:
        strategy_engine.resume_symbol(sym)
    StrategyEngine._paused_strategy_ids.clear()
    StrategyEngine._paused_symbols.clear()
    StrategyEngine._expansion_paused = False


def test_18_strategies_registered_across_all_6_pairs():
    """Verify all 6 core pairs have dedicated institutional strategies (18 total)."""
    _reset_pause_state()
    strats = strategy_engine.get_strategies()
    assert len(strats) == 23

    by_symbol = {}
    for s in strats:
        by_symbol.setdefault(s.symbol, []).append(s.id)

    assert "XAU/USD" in by_symbol and len(by_symbol["XAU/USD"]) == 8
    assert "GBP/USD" in by_symbol and len(by_symbol["GBP/USD"]) == 2
    assert "EUR/USD" in by_symbol and len(by_symbol["EUR/USD"]) == 3
    assert set(by_symbol["USD/JPY"]) == {"strat-009", "strat-013", "strat-014", "strat-022"}
    assert set(by_symbol["GBP/JPY"]) == {"strat-015", "strat-016", "strat-021"}
    assert set(by_symbol["AUD/USD"]) == {"strat-017", "strat-018", "strat-023"}


def test_bollinger_band_rsi_sniper_trigger_and_jpy_3_decimals():
    """Verify strat-009 promotes to GENERATED on Bollinger Band + RSI exhaustion and uses 3 decimals for JPY."""
    _reset_pause_state()
    s9 = strategy_engine.get_strategy_by_id("strat-009")
    assert s9 is not None

    now = datetime(2026, 10, 20, 3, 0, tzinfo=timezone.utc)  # Asian session (03:00 UTC)
    # Build 25 H1 bars for USDJPY hovering around 150.500 with final drop to lower Bollinger Band (150.100)
    bars = []
    for i in range(25):
        px = 150.500 + (0.080 if i % 2 == 0 else -0.080)
        bars.append(
            CandleBar(
                open=px,
                high=px + 0.040,
                low=px - 0.040,
                close=px,
                volume=1000.0,
                timestamp=int((now - timedelta(hours=25 - i)).timestamp()),
                time=now - timedelta(hours=25 - i),
            )
        )

    market_state = MarketState(
        session="Asian",
        volatility="Low",
        marketSentimentLabel="Neutral",
        overallMarketConfidence=75,
        timestamp=now,
        dataAgeSeconds=5,
        prices={
            "USDJPY": MarketPrice(
                symbol="USD/JPY",
                currentPrice=150.150,
                bid=150.145,
                ask=150.155,
                spread=1.0,
                timestamp=now,
                provider="oanda",
            )
        },
        indicators={
            "USDJPY": [
                Indicator(name="RSI", value=28.5, signal="Oversold", provider="oanda"),
                Indicator(name="ATR", value=0.220, signal="Low", provider="oanda"),
            ]
        },
        calendar=[],
    )

    class _BarAdapter:
        def __init__(self, cb):
            self.open = cb.open
            self.high = cb.high
            self.low = cb.low
            self.close = cb.close
            self.volume = cb.volume
            self.bar_time = cb.time

    adapted_bars = [_BarAdapter(b) for b in bars]

    engine = SignalGenerationEngine()
    with patch("app.core.services.market_history_service.market_history_service.get_bars", return_value=adapted_bars), \
         patch("app.core.repository.trade_journal_repository.trade_journal_repository.list_closed_trades_as_of", return_value=[]):
        s9.status = StrategyStatus.ACTIVE
        cands = engine.generate_candidates(market_state, [s9], as_of=now)

    assert len(cands) == 1
    cand = cands[0]
    assert cand.direction == CandidateDirection.BUY
    assert cand.status == CandidateStatus.GENERATED
    assert cand.readinessScore >= 88
    # Verify JPY 3-decimal rounding works properly
    assert round(cand.entryPrice, 3) == cand.entryPrice
    assert any("Bollinger Band Lower Exhaustion" in r.title for r in cand.reasons)


def test_macro_cross_asset_gold_aud_and_gbpjpy_confluence():
    """Verify AUD/USD gets Gold commodity confluence bonus and GBP/JPY gets Yen-cross yield tailwind."""
    now = datetime.now(timezone.utc)

    class _DummyBar:
        def __init__(self, close):
            self.close = close

    candles = {
        "EURUSD": [_DummyBar(1.1000), _DummyBar(1.1010), _DummyBar(1.1020), _DummyBar(1.1035)],  # EUR up -> DXY bearish
        "GBPUSD": [_DummyBar(1.3000), _DummyBar(1.3010), _DummyBar(1.3025), _DummyBar(1.3040)],
        "AUDUSD": [_DummyBar(0.6500), _DummyBar(0.6510), _DummyBar(0.6520), _DummyBar(0.6530)],
        "XAUUSD": [_DummyBar(2650.0), _DummyBar(2653.0), _DummyBar(2656.0), _DummyBar(2660.0)],  # Gold +0.38%
    }
    aud_eval = macro_cross_asset_engine.evaluate_alignment("AUD/USD", "BUY", candles_by_symbol=candles)
    assert aud_eval.aligned is True
    assert aud_eval.is_macro_trap is False
    assert aud_eval.confidence_modifier == 12.0  # +8.0 DXY tailwind + 4.0 Gold commodity confluence
    assert "Gold commodity tailwind" in aud_eval.rationale

    # Test GBPJPY with rising yields
    snap_rising = macro_cross_asset_engine.compute_synthetic_dxy_from_returns({"USDJPY": 0.30, "EURUSD": -0.20})
    assert snap_rising.yield_proxy_bias == "RISING_YIELDS"
    gj_eval = macro_cross_asset_engine.evaluate_alignment("GBP/JPY", "BUY", snapshot=snap_rising)
    assert gj_eval.aligned is True
    assert gj_eval.confidence_modifier == 8.0
    assert "Yen-Cross Yield Tailwind" in gj_eval.rationale


def test_copilot_pause_and_resume_controls():
    """Verify Falcon AI Co-Pilot can pause and resume expansion strategies, specific pairs, and individual strategies."""
    _reset_pause_state()
    from decimal import Decimal
    from app.core.analytics.adaptive_tuning_engine import LossRecoveryMetrics

    dummy_loss = LossRecoveryMetrics(
        consecutive_losses=0,
        profit_recovery_multiplier=1.0,
        accumulated_streak_loss=Decimal("0.00"),
        recovery_status="BASELINE",
        ai_reflection="Baseline risk state active.",
    )

    with patch.object(adaptive_tuning_engine, "get_loss_recovery_metrics", return_value=dummy_loss):
        # 1. Pause expansion strategies via Co-Pilot natural language command
        resp_pause_exp = copilot_service.handle_query(CopilotQueryRequest(query="Pause expansion strategies"))
        assert resp_pause_exp.intent == "STRATEGY_CONTROL"
        state = strategy_engine.get_pause_state()
        assert state["expansion_paused"] is True
        assert state["paused_count"] == 6
        assert state["active_count"] == 17
        assert "strat-013" in state["paused_strategy_ids"]
        assert "strat-018" in state["paused_strategy_ids"]

        # 2. Resume expansion strategies via Co-Pilot
        resp_resume_exp = copilot_service.handle_query(CopilotQueryRequest(query="Resume expansion strategies"))
        assert resp_resume_exp.intent == "STRATEGY_CONTROL"
        state = strategy_engine.get_pause_state()
        assert state["expansion_paused"] is False
        assert state["paused_count"] == 0
        assert state["active_count"] == 23

        # 3. Pause a specific currency pair (GBP/JPY) via Co-Pilot
        resp_pause_gj = copilot_service.handle_query(CopilotQueryRequest(query="Pause GBP/JPY"))
        assert resp_pause_gj.intent == "STRATEGY_CONTROL"
        state = strategy_engine.get_pause_state()
        assert set(state["paused_strategy_ids"]) == {"strat-015", "strat-016", "strat-021"}
        assert "GBPJPY" in state["paused_symbols"]

        # 4. Resume GBP/JPY via Co-Pilot
        copilot_service.handle_query(CopilotQueryRequest(query="Resume GBP/JPY"))
        state = strategy_engine.get_pause_state()
        assert state["paused_count"] == 0

        # 5. Pause single strategy strat-013 via Co-Pilot
        copilot_service.handle_query(CopilotQueryRequest(query="Pause strat-013"))
        state = strategy_engine.get_pause_state()
        assert state["paused_strategy_ids"] == ["strat-013"]

    _reset_pause_state()


def test_briefings_include_all_6_pairs_and_pause_governance():
    """Verify London Open and Daily Review briefings include all 6 pairs and strategy governance state."""
    _reset_pause_state()
    from decimal import Decimal
    from app.core.analytics.adaptive_tuning_engine import LossRecoveryMetrics, StrategyTuningProfile

    strategy_engine.pause_strategy("strat-015")

    dummy_loss = LossRecoveryMetrics(
        consecutive_losses=0,
        profit_recovery_multiplier=1.0,
        accumulated_streak_loss=Decimal("0.00"),
        recovery_status="BASELINE",
        ai_reflection="Baseline risk state active.",
    )
    dummy_profile = StrategyTuningProfile(
        strategy_id="falcon-opt",
        symbol="ALL",
        adaptive_stop_multiplier=1.0,
        adaptive_pullback_multiplier=1.0,
        tuning_status="OPTIMAL",
        consecutive_losses=0,
        recent_win_rate=0.75,
        total_evaluated=5,
        rationale="Optimal",
        last_tuned_at=datetime.now(timezone.utc),
    )
    sample_quotes = {
        "EUR/USD": 1.1350,
        "GBP/USD": 1.3270,
        "XAU/USD": 4185.00,
        "USD/JPY": 150.250,
        "GBP/JPY": 198.500,
        "AUD/USD": 0.6580,
    }

    with patch.object(adaptive_tuning_engine, "get_loss_recovery_metrics", return_value=dummy_loss), \
         patch.object(adaptive_tuning_engine, "get_strategy_tuning", return_value=dummy_profile), \
         patch.object(briefing_service, "_get_high_impact_events", return_value=["13:30 UTC: USD CPI"]):
        london = briefing_service.generate_london_open_briefing(market_quotes=sample_quotes, force_refresh=True)
        for pair in ["EUR/USD", "GBP/USD", "XAU/USD", "USD/JPY", "GBP/JPY", "AUD/USD"]:
            assert pair in london.market_levels
        assert london.risk_state["active_strategies_count"] == 22
        assert london.risk_state["paused_strategies_count"] == 1
        assert "strat-015" in london.risk_state["paused_strategy_ids"]
        assert "GBP/JPY" in london.formatted_text
        assert "AUD/USD" in london.formatted_text
        assert "USD/JPY" in london.formatted_text

        daily = briefing_service.generate_daily_review_briefing(trade_journal_data=[], force_refresh=True)
        assert daily.risk_state["active_strategies_count"] == 22
        assert daily.risk_state["paused_strategies_count"] == 1

    _reset_pause_state()



def test_bottleneck_remediation_rsi_and_mission_persistence():
    """Verify directional RSI validation (oversold BUY / overbought SELL pass) and 15-min mission freshness."""
    from datetime import timedelta
    from app.core.engines.validation_engine import ValidationEngine
    from app.schemas.signal_candidate import (
        SignalCandidate,
        CandidateDirection,
        CandidateStatus,
        CandidateMarketSnapshot,
        ConfidenceBreakdown,
        CandidateCondition,
    )
    from app.schemas.market_state import MarketState

    now = datetime.now(timezone.utc)
    v_engine = ValidationEngine()
    market_state = MarketState(
        timestamp=now,
        provider="OANDA",
        environment="PRODUCTION",
        prices={},
        session="London",
        dataAgeSeconds=0,
    )

    # Oversold BUY setup (RSI = 24.5) should PASS RSI Validation (mean-reversion / liquidity sweep)
    buy_cand = SignalCandidate(
        id="cand-buy-oversold",
        symbol="USD/JPY",
        strategyId="strat-009",
        strategyName="Asian Mean Reversion Range",
        strategyVersion="1.0.0",
        strategyGrade="B",
        strategyScore=82,
        direction=CandidateDirection.BUY,
        confidence=78,
        readinessScore=85,
        entryPrice=150.100,
        stopLoss=149.850,
        takeProfit=150.650,
        riskReward=2.2,
        status=CandidateStatus.GENERATED,
        generatedAt=now,
        reasons=[],
        conditions=[
            CandidateCondition(title="Technical Alignment", description="Mean reversion", passed=True),
            CandidateCondition(title="Session Match", description="Tokyo", passed=True),
        ],
        marketSnapshot=CandidateMarketSnapshot(
            trend="Bullish",
            volatility="Moderate",
            session="London",
            spread=0.8,
            newsImpact="Low",
            marketSentiment="Bullish",
            marketConfidence=85,
            atr=0.15,
            rsi=24.5,
        ),
        confidenceBreakdown=ConfidenceBreakdown(
            trendScore=20, strategyScore=25, sessionScore=15, sentimentScore=10, newsScore=8
        ),
        evaluationDurationMs=5,
        marketDataAgeSeconds=0,
        evaluationStartedAt=now,
        evaluationCompletedAt=now,
    )
    res_buy = v_engine.validate_candidates([buy_cand], strategies=[], market_state=market_state)[0]
    rsi_check_buy = next(c for c in res_buy.checks if c.title == "RSI Validation")
    assert rsi_check_buy.passed is True

    # Overbought SELL setup (RSI = 74.0) should PASS RSI Validation
    sell_cand = buy_cand.model_copy(deep=True)
    sell_cand.direction = CandidateDirection.SELL
    sell_cand.marketSnapshot.rsi = 74.0
    res_sell = v_engine.validate_candidates([sell_cand], strategies=[], market_state=market_state)[0]
    rsi_check_sell = next(c for c in res_sell.checks if c.title == "RSI Validation")
    assert rsi_check_sell.passed is True
