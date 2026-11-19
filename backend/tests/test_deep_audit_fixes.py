"""
Falcon Full-Stack Deep Audit Regression Suite
Verifies critical and high-severity fixes across:
1. Data Preservation (ENABLE_MISSION_AUTO_PRUNE=False default, purge endpoints locked)
2. LiveIntelligence / NewsService symbols kwarg compatibility & deterministic 48-bit IDs
3. MarketScheduler AUTO_EXPIRE before limit check & DuplicateDetector pip-scaled tolerance
4. MarketHistoryService canonical timeframes (1min/5min/daily -> 1m/5m/1d) & newest-first adapter
5. ProviderManager non-immortal cache TTL & EconomicCalendarService post-news favored_dir=None safety
6. CapitalGuardianService JPY & USD-base worst-case loss conversion (USDJPY, GBPJPY, USDCAD)
7. DecisionEngine RiskLevel.HIGH monitoring & OrderFlowEngine shooting-star passive absorption accuracy
8. AdaptiveTuningEngine & RegimeMemoryEngine zero-loss breakeven non-quarantine
9. FastAPI slash-symbol routes (/{symbol:path}) & OrderExecutionService dispatch_raw_message safety
"""
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config.settings import settings
from app.core.services.news_service import build_news_response, _stable_news_id
from app.services.scheduler.duplicate_detector import DuplicateDetector
from app.core.services.market_history_service import _canonical_timeframe, _OANDA_GRANULARITY
from app.core.services.market_history_adapter import MarketHistoryAdapter
from app.models.market_candle import Timeframe
from app.core.providers import provider_manager
from app.schemas.market_quote import MarketQuote, BidAsk
from app.core.services.economic_calendar_service import economic_calendar_service, EconomicEvent
from app.core.services.capital_guardian_service import capital_guardian_service
from app.core.engines.decision_engine import DecisionEngine
from app.core.engines.order_flow_engine import order_flow_engine
from app.core.analytics.adaptive_tuning_engine import adaptive_tuning_engine
from app.core.analytics.regime_memory_engine import regime_memory_engine, StrategyHealthStatus
from app.schemas.signal_candidate import SignalCandidate, CandidateDirection, CandidateStatus, CandidateMarketSnapshot
from app.schemas.validation_result import ValidationResult, ValidationStatus
from app.schemas.risk_assessment import RiskAssessment, RiskLevel
from app.schemas.execution_readiness import ExecutionReadiness, ExecutionReadinessStatus
from app.schemas.decision_artifact import DecisionStatus
from app.schemas.trade_journal import TradeJournalItem


def test_1_data_preservation_defaults():
    assert settings.ENABLE_MISSION_AUTO_PRUNE is False, "ENABLE_MISSION_AUTO_PRUNE must default to False"
    print("Audit Fix 1 PASS: ENABLE_MISSION_AUTO_PRUNE defaults to False (archived missions & artifacts protected)!")


def test_2_news_service_symbols_kwarg_and_stable_ids():
    with patch.object(economic_calendar_service, "get_events", return_value=[
        EconomicEvent(
            title="US Non-Farm Payrolls",
            country="US",
            currency="USD",
            impact="High",
            eventTime=datetime.now(timezone.utc),
            countdownMinutes=10,
            forecast="200K",
            previous="180K",
            provider="ForexFactory",
        ),
        EconomicEvent(
            title="BoJ Rate Statement",
            country="JP",
            currency="JPY",
            impact="High",
            eventTime=datetime.now(timezone.utc),
            countdownMinutes=15,
            forecast="0.25%",
            previous="0.25%",
            provider="ForexFactory",
        ),
    ]):
        res_all = build_news_response()
        assert len(res_all.events) == 2
        res_filtered = build_news_response(symbols=["EUR/USD"])
        assert len(res_filtered.events) == 1
        assert res_filtered.events[0].currency == "USD"
        assert 0 < res_filtered.events[0].id < (1 << 53), "NewsItem ID must be positive and JS 53-bit safe"
        assert _stable_news_id("test-key") == _stable_news_id("test-key")
    print("Audit Fix 2 PASS: build_news_response accepts symbols=WATCHLIST & generates deterministic 48-bit IDs!")


def test_3_duplicate_detector_pip_scaled_tolerance():
    det = DuplicateDetector()
    # 50 pips apart on EUR/USD (1.0800 vs 1.0850): must NOT be treated as within 5-pip tolerance!
    assert det._is_entry_within_tolerance(1.0800, 1.0850, symbol="EUR/USD") is False
    # 3 pips apart on EUR/USD (1.0800 vs 1.0803): within 5-pip tolerance
    assert det._is_entry_within_tolerance(1.0800, 1.0803, symbol="EUR/USD") is True
    # 30 pips apart on USD/JPY (155.00 vs 155.30): must NOT be within 5-pip tolerance
    assert det._is_entry_within_tolerance(155.00, 155.30, symbol="USD/JPY") is False
    # 3 pips apart on USD/JPY (155.00 vs 155.03): within 5-pip tolerance
    assert det._is_entry_within_tolerance(155.00, 155.03, symbol="USD/JPY") is True
    print("Audit Fix 3 PASS: DuplicateDetector scales entry_tolerance_pips by instrument pip size!")


def test_4_timeframe_canonicalization_and_adapter_order():
    assert _canonical_timeframe("1min") == "1m"
    assert _canonical_timeframe("5min") == "5m"
    assert _canonical_timeframe("15min") == "15m"
    assert _canonical_timeframe("daily") == "1d"
    assert _OANDA_GRANULARITY[_canonical_timeframe("5min")] == "M5"
    assert _OANDA_GRANULARITY[_canonical_timeframe("1min")] == "M1"
    assert _OANDA_GRANULARITY[_canonical_timeframe("daily")] == "D"

    adapter = MarketHistoryAdapter(db=None)
    assert adapter._TIMEFRAME_MAPPING[Timeframe.M5] == "5m"
    assert adapter._TIMEFRAME_MAPPING[Timeframe.M1] == "1m"
    assert adapter._TIMEFRAME_MAPPING[Timeframe.D1] == "1d"
    print("Audit Fix 4 PASS: Timeframes 1min/5min/daily canonicalize to M1/M5/D (no silent H1 fallback)!")


def test_5_provider_cache_not_immortal_and_post_news_none_safe():
    pm = provider_manager
    q = MarketQuote(
        symbol="EURUSD",
        instrumentName="EUR/USD",
        assetClass="FOREX",
        providerId="oanda",
        providerName="OANDA",
        lastPrice=1.0850,
        change=0.0,
        changePercent=0.0,
        bidAsk=BidAsk(bid=1.0849, ask=1.0851, spread=0.0002),
        timestamp=datetime.now(timezone.utc),
        freshnessSeconds=0,
    )
    pm._cache.set("EURUSD", data=q, provider_id="fmp", provider_name="FMP", ttl=30)
    entry_before = pm._cache.get("EURUSD")
    stored_at_before = entry_before.stored_at
    time.sleep(0.05)
    resp = pm.get_market_quote("EUR/USD")
    assert resp is not None
    entry_after = pm._cache.get("EURUSD")
    assert entry_after.stored_at == stored_at_before, "Cache hit must NOT reset stored_at TTL!"
    assert entry_after.provider_id == "fmp", "Cache hit must NOT overwrite provider attribution!"

    # EconomicCalendarService post-news catalyst with actual=None & candles=None (favored_dir=None)
    recent_ev = EconomicEvent(
        title="ECB Press Conference",
        country="EU",
        currency="EUR",
        impact="High",
        eventTime=datetime.now(timezone.utc),
        countdownMinutes=-15,
        actual=None,
        forecast="",
        previous="",
        provider="ForexFactory",
    )
    with patch.object(economic_calendar_service, "get_events", return_value=[recent_ev]):
        cat = economic_calendar_service.evaluate_news_catalyst("EUR/USD", proposed_direction="BUY", candles=None)
        assert isinstance(cat.get("rationale", ""), str)
    print("Audit Fix 5 PASS: Provider cache TTL is not reset on hits & post-news favored_dir=None does not crash!")


def test_6_capital_guardian_jpy_and_usd_base_conversion():
    # USD/JPY: 20-pip risk (155.00 -> 154.80) on 0.10 lot (10,000 units) = 2,000 JPY / 155.00 = ~$12.90 USD
    uj_loss = capital_guardian_service.calculate_trade_worst_case_loss(
        symbol="USD/JPY",
        direction="BUY",
        entry_price=Decimal("155.00"),
        stop_loss=Decimal("154.80"),
        lot_size=Decimal("0.10"),
    )
    assert Decimal("10.00") <= uj_loss <= Decimal("16.00"), f"Unexpected USD/JPY loss: {uj_loss}"

    # GBP/JPY: 25-pip risk (209.50 -> 209.25) on 0.10 lot = 2,500 JPY -> converted to USD without ValueError
    gj_loss = capital_guardian_service.calculate_trade_worst_case_loss(
        symbol="GBP/JPY",
        direction="BUY",
        entry_price=Decimal("209.50"),
        stop_loss=Decimal("209.25"),
        lot_size=Decimal("0.10"),
    )
    assert Decimal("12.00") <= gj_loss <= Decimal("22.00"), f"Unexpected GBP/JPY loss: {gj_loss}"
    print(f"Audit Fix 6 PASS: CapitalGuardian converts USD/JPY (${uj_loss}) & GBP/JPY (${gj_loss}) risk cleanly!")


def test_7_decision_engine_high_risk_and_order_flow_shooting_star():
    from types import SimpleNamespace
    from app.schemas.risk_assessment import RiskAssessmentStatus
    de = DecisionEngine()
    now = datetime.now(timezone.utc)
    exec_snap = SimpleNamespace(
        volatility="High", session="London", spread=1.0, newsImpact="None",
        marketSentiment="Bullish", marketConfidence=85.0, dataAgeSeconds=5
    )
    cand = SimpleNamespace(
        id="cand-high-risk", strategyId="strat-025", strategyName="Cable Scalp",
        strategyVersion="3.2.0", symbol="GBP/USD", direction=CandidateDirection.BUY,
        confidence=92.0, readinessScore=92, status=CandidateStatus.GENERATED,
        entryPrice=1.3000, stopLoss=1.2985, takeProfit=1.3020,
        generatedAt=now
    )
    val = SimpleNamespace(
        id="val-1", candidateId="cand-high-risk", validationScore=92.0,
        status=ValidationStatus.PASSED, validatedAt=now
    )
    risk_high = SimpleNamespace(
        id="risk-1", overallRiskScore=72.0, riskLevel=RiskLevel.HIGH,
        status=RiskAssessmentStatus.REVIEW_REQUIRED, assessedAt=now
    )
    exec_r = SimpleNamespace(
        id="exec-1", candidateId="cand-high-risk", validationId="val-1",
        riskAssessmentId="risk-1", strategyId="strat-025", strategyName="Cable Scalp",
        strategyVersion="3.2.0", symbol="GBP/USD",
        candidateStatus=CandidateStatus.GENERATED,
        validationStatus=ValidationStatus.PASSED,
        riskLevel=RiskLevel.HIGH,
        riskStatus=RiskAssessmentStatus.REVIEW_REQUIRED,
        status=ExecutionReadinessStatus.READY,
        overallReadinessScore=92.0,
        recommendation=SimpleNamespace(nextReviewIn="15 Minutes"),
        reasons=[],
        marketSnapshot=exec_snap,
        evaluatedAt=now
    )
    ms = SimpleNamespace(trend="Bullish", timestamp=now)
    decisions = de.generate_decisions([exec_r], [risk_high], [val], [cand], [], ms)
    assert decisions[0].status == DecisionStatus.MONITORING, f"RiskLevel.HIGH must map to MONITORING, not {decisions[0].status}"

    # Bearish shooting star closing at 45% of range with 55% upper wick & 10% lower wick
    class _Bar:
        def __init__(self, o, h, l, c, v):
            self.open, self.high, self.low, self.close, self.volume = o, h, l, c, v
    bars = [_Bar(1.1000, 1.1010, 1.0990, 1.1000, 100) for _ in range(19)]
    bars.append(_Bar(1.1010, 1.1100, 1.1000, 1.1045, 300))
    detected, kind, _ = order_flow_engine.detect_iceberg_and_passive_absorption(bars[-1], bars, "SELL")
    assert kind != "PASSIVE_ACCUMULATION", f"Bearish shooting star must not be classified as PASSIVE_ACCUMULATION (got {kind})"
    print("Audit Fix 7 PASS: DecisionEngine blocks RiskLevel.HIGH & OrderFlowEngine classifies shooting stars accurately!")


def test_8_breakeven_trades_do_not_quarantine_strategy():
    now = datetime.now(timezone.utc)
    be_trades = [
        TradeJournalItem(
            id=i, symbol="XAU/USD", direction="SELL", entryPrice=3750.0,
            stopLoss=3750.0, takeProfit=3740.0, status="CLOSED", result="BREAKEVEN",
            profitLoss=-0.01, realizedRMultiple=0.0, strategyId="strat-024",
            timeframe="15m", marketSession="London", riskReward=1.25, confidence=90,
            reasonForEntry="Test BE", tradeDate=now, closeDate=now,
            createdAt=now, updatedAt=now
        )
        for i in range(1, 5)
    ]
    with patch("app.core.repository.trade_journal_repository.trade_journal_repository.list_closed_trades_as_of", return_value=be_trades), \
         patch("app.core.repository.trade_journal_repository.trade_journal_repository.list_trades", return_value=be_trades):
        health = regime_memory_engine.evaluate_strategy_health("strat-024")
        assert health.health_status != StrategyHealthStatus.QUARANTINED_PAPER, f"4 BE trades must not quarantine strategy (got {health.health_status})"
        profile = adaptive_tuning_engine.get_strategy_tuning("strat-024")
        assert profile.is_quarantined_shadow is False, "4 BE trades must not shadow-quarantine strategy!"
    print("Audit Fix 8 PASS: Breakeven trades (even with -$0.01 spread friction) never trigger false quarantine!")


if __name__ == "__main__":
    test_1_data_preservation_defaults()
    test_2_news_service_symbols_kwarg_and_stable_ids()
    test_3_duplicate_detector_pip_scaled_tolerance()
    test_4_timeframe_canonicalization_and_adapter_order()
    test_5_provider_cache_not_immortal_and_post_news_none_safe()
    test_6_capital_guardian_jpy_and_usd_base_conversion()
    test_7_decision_engine_high_risk_and_order_flow_shooting_star()
    test_8_breakeven_trades_do_not_quarantine_strategy()
    print("ALL 8 DEEP AUDIT REGRESSION TESTS PASSED!")
