"""
Falcon V10 Unit Tests: Regime Memory & Diagnostics Engine (Pillar 2: Cognitive Learning).

Tests:
1. Forensic Diagnostics:
   - Institutional Liquidity Sweep: stop loss pierced by wick before directional reversal -> +35% ATR stop buffer expansion.
   - Off-Peak Momentum Stall: exit outside London/NY sessions during low volume -> session restriction to major sessions.
   - Macro News Volatility: exit within 15 minutes of high-impact macro news -> +15 minutes news blackout expansion.
   - Normal Stop Out: standard structural invalidation without anomaly.
   - Take Profit Hit: winning trade reinforces strategy parameters.
2. Dynamic Strategy Health Scoring:
   - BOOSTED state: win rate >= 60% and profit factor >= 1.8 -> 1.5x allocation.
   - QUARANTINED_PAPER state: win rate < 35% or >= 3 consecutive losses -> 0.0x allocation.
   - CAUTION state: 2 consecutive losses or sub-par metrics -> 0.5x allocation.
   - HEALTHY state: normal baseline operations -> 1.0x allocation.
   - Empty trade history baseline.
3. Memory Ledger & Aggregated Summary:
   - In-memory diagnostics recording and retrieval.
   - Aggregated root cause distribution, lessons ledger, and strategy scorecards.
4. Integration consistency with AdaptiveRuleTuningEngine & TradeJournal:
   - Syncing prescribed adaptations into effective stop multipliers (+0.35x).
   - Object-level compatibility with TradeJournalItem.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest

from app.core.analytics.adaptive_tuning_engine import AdaptiveRuleTuningEngine, adaptive_tuning_engine
from app.core.analytics.regime_memory_engine import RegimeMemoryEngine, regime_memory_engine
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.services.signal_outcome_resolver import signal_outcome_resolver
from app.schemas.regime_memory import (
    DynamicAdaptation,
    PostMortemDiagnostic,
    RootCauseType,
    StrategyHealthScore,
    StrategyHealthStatus,
)
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalItem


@pytest.fixture(autouse=True)
def clean_journal():
    from app.core.repository.trade_journal_repository import InMemoryTradeJournalStorage
    original_storage = trade_journal_repository._storage
    trade_journal_repository._storage = InMemoryTradeJournalStorage()
    trade_journal_repository.clear()
    yield
    trade_journal_repository.clear()
    trade_journal_repository._storage = original_storage


@pytest.fixture
def memory_engine() -> RegimeMemoryEngine:
    engine = RegimeMemoryEngine()
    engine.clear_memory()
    return engine


# ─────────────────────────────────────────────────────────────────────────────
# 1. Forensic Diagnostics: Liquidity Sweeps (+35% ATR Expansion)
# ─────────────────────────────────────────────────────────────────────────────

def test_liquidity_sweep_diagnostic_buy_trade(memory_engine: RegimeMemoryEngine):
    """
    BUY trade stopped out: low price pierced stop loss (trough < stop_loss),
    then reversed upward past entry price.
    Must diagnose INSTITUTIONAL_LIQUIDITY_SWEEP and prescribe atr_stop_multiplier_delta = +0.35.
    """
    trade = {
        "trade_id": "sweep_buy_01",
        "symbol": "EURUSD",
        "strategy_id": "trend_pullback",
        "direction": "BUY",
        "entry_price": 1.0850,
        "stop_loss": 1.0800,
        "take_profit": 1.0950,
        "exit_price": 1.0798,
        "result": "LOSS",
        "pnl": -52.0,
        "reason_for_exit": "Stop loss hit",
        "close_date": datetime(2026, 9, 28, 14, 30, tzinfo=timezone.utc),  # NY/London overlap
    }
    context = {
        "trough_price": 1.0795,       # Pierced 1.0800 stop loss by 5 pips
        "post_stop_price": 1.0890,    # Reversed back up above entry (1.0850)
        "reversal_direction": "UP",
    }

    diagnostic = memory_engine.diagnose_trade_outcome(trade_record=trade, market_context=context)

    assert diagnostic.root_cause == RootCauseType.INSTITUTIONAL_LIQUIDITY_SWEEP
    assert diagnostic.symbol == "EURUSD"
    assert diagnostic.strategy_id == "trend_pullback"
    assert diagnostic.outcome == "LOSS"
    assert diagnostic.prescribed_adaptation["atr_stop_multiplier_delta"] == 0.35
    assert diagnostic.prescribed_adaptation["action"] == "EXPAND_ATR_STOP_BUFFER"
    assert "liquidity sweep wick" in diagnostic.lesson_learned.lower()


def test_liquidity_sweep_diagnostic_sell_trade(memory_engine: RegimeMemoryEngine):
    """
    SELL trade stopped out: high price pierced stop loss (peak > stop_loss),
    then reversed downward below entry price.
    """
    trade = {
        "trade_id": "sweep_sell_01",
        "symbol": "XAUUSD",
        "strategy_id": "gold_breakout",
        "direction": "SELL",
        "entry_price": 2650.0,
        "stop_loss": 2660.0,
        "take_profit": 2620.0,
        "exit_price": 2660.5,
        "result": "LOSS",
        "pnl": -105.0,
        "reason_for_exit": "Stop loss hit",
        "close_date": datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc),
    }
    context = {
        "peak_price": 2662.0,         # Pierced 2660.0 stop loss
        "post_stop_price": 2635.0,    # Reversed back down below entry (2650.0)
        "reversal_direction": "DOWN",
    }

    diagnostic = memory_engine.diagnose_trade_outcome(trade_record=trade, market_context=context)

    assert diagnostic.root_cause == RootCauseType.INSTITUTIONAL_LIQUIDITY_SWEEP
    assert diagnostic.prescribed_adaptation["atr_stop_multiplier_delta"] == 0.35
    assert diagnostic.prescribed_adaptation["recommended_stop_buffer"] == 1.35


def test_liquidity_sweep_explicit_context_flag(memory_engine: RegimeMemoryEngine):
    """Explicit liquidity_sweep flag in market context triggers sweep diagnosis."""
    trade = {
        "trade_id": "sweep_flag_01",
        "symbol": "GBPUSD",
        "strategy_id": "cable_sniper",
        "result": "LOSS",
        "pnl": -35.0,
        "close_date": datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc),
    }
    context = {
        "liquidity_sweep": True,
        "swept_and_reversed": True,
    }

    diagnostic = memory_engine.diagnose_trade_outcome(trade_record=trade, market_context=context)
    assert diagnostic.root_cause == RootCauseType.INSTITUTIONAL_LIQUIDITY_SWEEP
    assert diagnostic.prescribed_adaptation["atr_stop_multiplier_delta"] == 0.35


# ─────────────────────────────────────────────────────────────────────────────
# 2. Forensic Diagnostics: Off-Peak Momentum Stall (Session Restriction)
# ─────────────────────────────────────────────────────────────────────────────

def test_off_peak_momentum_stall_diagnostic(memory_engine: RegimeMemoryEngine):
    """
    Trade closed during Asian dead hours (e.g. 23:30 UTC or 03:00 UTC) with low volume.
    Must diagnose OFF_PEAK_MOMENTUM_STALL and prescribe restrict_to_major_sessions = True.
    """
    trade = {
        "trade_id": "off_peak_01",
        "symbol": "EURUSD",
        "strategy_id": "session_scalp",
        "result": "LOSS",
        "pnl": -28.0,
        "reason_for_exit": "Momentum stalled in dead zone",
        # 23:30 UTC is outside London (07:00-16:00) and NY (12:00-21:00)
        "close_date": datetime(2026, 9, 28, 23, 30, tzinfo=timezone.utc),
    }
    context = {
        "low_volume": True,
        "volume_percentile": 15,
        "momentum_stalled": True,
    }

    diagnostic = memory_engine.diagnose_trade_outcome(trade_record=trade, market_context=context)

    assert diagnostic.root_cause == RootCauseType.OFF_PEAK_MOMENTUM_STALL
    assert diagnostic.prescribed_adaptation["restrict_to_major_sessions"] is True
    assert diagnostic.prescribed_adaptation["action"] == "RESTRICT_SESSION_WINDOW"
    assert "LONDON" in diagnostic.prescribed_adaptation["allowed_sessions"]
    assert "NEW_YORK" in diagnostic.prescribed_adaptation["allowed_sessions"]
    assert "off-peak" in diagnostic.lesson_learned.lower()


def test_off_peak_explicit_asian_session_string(memory_engine: RegimeMemoryEngine):
    """Explicit ASIAN session tag with low volume stall triggers session restriction."""
    trade = {
        "trade_id": "off_peak_02",
        "symbol": "USDJPY",
        "strategy_id": "yen_flow",
        "result": "LOSS",
        "pnl": -40.0,
        "market_session": "ASIAN",
        "close_date": datetime(2026, 9, 28, 2, 0, tzinfo=timezone.utc),
    }
    context = {"volume_ratio": 0.35}

    diagnostic = memory_engine.diagnose_trade_outcome(trade_record=trade, market_context=context)
    assert diagnostic.root_cause == RootCauseType.OFF_PEAK_MOMENTUM_STALL
    assert diagnostic.prescribed_adaptation["restrict_to_major_sessions"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 3. Forensic Diagnostics: Macro News Volatility (Blackout Expansion)
# ─────────────────────────────────────────────────────────────────────────────

def test_macro_news_volatility_diagnostic_minutes_delta(memory_engine: RegimeMemoryEngine):
    """
    Trade stopped out 8 minutes before high-impact CPI release.
    Must diagnose MACRO_NEWS_VOLATILITY and prescribe widen_news_blackout_minutes = 15.
    """
    trade = {
        "trade_id": "news_cpi_01",
        "symbol": "EURUSD",
        "strategy_id": "macro_rider",
        "result": "LOSS",
        "pnl": -75.0,
        "reason_for_exit": "Stop loss hit on erratic spread spike",
        "close_date": datetime(2026, 9, 28, 12, 22, tzinfo=timezone.utc),
    }
    context = {
        "news_event": "US CPI",
        "news_impact": "HIGH",
        "minutes_to_news": 8,  # Within 15 minutes window
    }

    diagnostic = memory_engine.diagnose_trade_outcome(trade_record=trade, market_context=context)

    assert diagnostic.root_cause == RootCauseType.MACRO_NEWS_VOLATILITY
    assert diagnostic.prescribed_adaptation["widen_news_blackout_minutes"] == 15
    assert diagnostic.prescribed_adaptation["action"] == "WIDEN_NEWS_BLACKOUT"
    assert "blackout window" in diagnostic.lesson_learned.lower()


def test_macro_news_volatility_explicit_timestamp(memory_engine: RegimeMemoryEngine):
    """Trade stopped out 10 minutes after scheduled FOMC interest rate decision."""
    close_time = datetime(2026, 9, 28, 18, 10, tzinfo=timezone.utc)
    news_time = datetime(2026, 9, 28, 18, 0, tzinfo=timezone.utc)

    trade = {
        "trade_id": "news_fomc_01",
        "symbol": "XAUUSD",
        "strategy_id": "gold_trend",
        "result": "LOSS",
        "pnl": -120.0,
        "close_date": close_time,
    }
    context = {
        "news_event": "FOMC Rate Decision",
        "news_time": news_time,
    }

    diagnostic = memory_engine.diagnose_trade_outcome(trade_record=trade, market_context=context)
    assert diagnostic.root_cause == RootCauseType.MACRO_NEWS_VOLATILITY
    assert diagnostic.prescribed_adaptation["widen_news_blackout_minutes"] == 15


# ─────────────────────────────────────────────────────────────────────────────
# 4. Forensic Diagnostics: Normal Stop Out & Winning Trade Hit
# ─────────────────────────────────────────────────────────────────────────────

def test_normal_stop_out_diagnostic(memory_engine: RegimeMemoryEngine):
    """
    Standard loss during London peak hours without sweep or macro news.
    Must diagnose NORMAL_STOP_OUT and keep risk parameters baseline.
    """
    trade = {
        "trade_id": "normal_loss_01",
        "symbol": "EURUSD",
        "strategy_id": "trend_pullback",
        "result": "LOSS",
        "pnl": -45.0,
        "reason_for_exit": "Clean structural break",
        "close_date": datetime(2026, 9, 28, 10, 15, tzinfo=timezone.utc),  # London peak
    }
    context = {
        "volume_percentile": 80,
    }

    diagnostic = memory_engine.diagnose_trade_outcome(trade_record=trade, market_context=context)

    assert diagnostic.root_cause == RootCauseType.NORMAL_STOP_OUT
    assert diagnostic.prescribed_adaptation["action"] == "MAINTAIN_CURRENT_RISK"
    assert diagnostic.prescribed_adaptation["atr_stop_multiplier_delta"] == 0.0


def test_take_profit_hit_diagnostic(memory_engine: RegimeMemoryEngine):
    """Winning trade reinforces strategy parameters."""
    trade = {
        "trade_id": "win_01",
        "symbol": "EURUSD",
        "strategy_id": "trend_pullback",
        "result": "WIN",
        "pnl": 95.0,
        "close_date": datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc),
    }

    diagnostic = memory_engine.diagnose_trade_outcome(trade_record=trade)

    assert diagnostic.root_cause == RootCauseType.TAKE_PROFIT_HIT
    assert diagnostic.outcome == "WIN"
    assert diagnostic.prescribed_adaptation["reinforce_strategy"] is True
    assert diagnostic.prescribed_adaptation["recommended_weight"] == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# 5. Dynamic Strategy Health Scoring
# ─────────────────────────────────────────────────────────────────────────────

def test_strategy_health_boosted_state(memory_engine: RegimeMemoryEngine):
    """
    Win rate >= 60% and profit factor >= 1.8 -> BOOSTED (1.5x allocation).
    """
    now = datetime.now(timezone.utc)
    # 7 wins ($100 each), 3 losses ($40 each) -> Gross Profit: $700, Gross Loss: $120 -> PF = 5.83, Win Rate = 70%
    trades = [
        {"result": "WIN", "pnl": 100.0, "close_date": now - timedelta(hours=1)},
        {"result": "WIN", "pnl": 100.0, "close_date": now - timedelta(hours=2)},
        {"result": "WIN", "pnl": 100.0, "close_date": now - timedelta(hours=3)},
        {"result": "LOSS", "pnl": -40.0, "close_date": now - timedelta(hours=4)},
        {"result": "WIN", "pnl": 100.0, "close_date": now - timedelta(hours=5)},
        {"result": "WIN", "pnl": 100.0, "close_date": now - timedelta(hours=6)},
        {"result": "LOSS", "pnl": -40.0, "close_date": now - timedelta(hours=7)},
        {"result": "WIN", "pnl": 100.0, "close_date": now - timedelta(hours=8)},
        {"result": "WIN", "pnl": 100.0, "close_date": now - timedelta(hours=9)},
        {"result": "LOSS", "pnl": -40.0, "close_date": now - timedelta(hours=10)},
    ]

    score = memory_engine.evaluate_strategy_health(strategy_id="elite_trend", trade_history=trades)

    assert score.strategy_id == "elite_trend"
    assert score.health_status == StrategyHealthStatus.BOOSTED
    assert score.recommended_weight == 1.5
    assert score.win_rate == 0.7
    assert score.profit_factor > 1.8
    assert score.consecutive_losses == 0


def test_strategy_health_quarantined_consecutive_losses(memory_engine: RegimeMemoryEngine):
    """
    3 consecutive losses -> QUARANTINED_PAPER (0.0x live allocation).
    """
    now = datetime.now(timezone.utc)
    trades = [
        {"result": "LOSS", "pnl": -50.0, "close_date": now - timedelta(hours=1)},
        {"result": "LOSS", "pnl": -50.0, "close_date": now - timedelta(hours=2)},
        {"result": "LOSS", "pnl": -50.0, "close_date": now - timedelta(hours=3)},
        {"result": "WIN", "pnl": 80.0, "close_date": now - timedelta(hours=4)},
        {"result": "WIN", "pnl": 80.0, "close_date": now - timedelta(hours=5)},
    ]

    score = memory_engine.evaluate_strategy_health(strategy_id="struggling_breakout", trade_history=trades)

    assert score.health_status == StrategyHealthStatus.QUARANTINED_PAPER
    assert score.recommended_weight == 0.0
    assert score.consecutive_losses == 3


def test_strategy_health_quarantined_low_win_rate(memory_engine: RegimeMemoryEngine):
    """
    Win rate < 35% across 5 trades -> QUARANTINED_PAPER (0.0x live allocation).
    """
    now = datetime.now(timezone.utc)
    # 1 win, 4 losses -> Win rate 20% (<35%)
    trades = [
        {"result": "WIN", "pnl": 60.0, "close_date": now - timedelta(hours=1)},
        {"result": "LOSS", "pnl": -40.0, "close_date": now - timedelta(hours=2)},
        {"result": "LOSS", "pnl": -40.0, "close_date": now - timedelta(hours=3)},
        {"result": "LOSS", "pnl": -40.0, "close_date": now - timedelta(hours=4)},
        {"result": "LOSS", "pnl": -40.0, "close_date": now - timedelta(hours=5)},
    ]

    score = memory_engine.evaluate_strategy_health(strategy_id="decaying_scalper", trade_history=trades)

    assert score.health_status == StrategyHealthStatus.QUARANTINED_PAPER
    assert score.recommended_weight == 0.0
    assert score.win_rate == 0.20


def test_strategy_health_caution_state(memory_engine: RegimeMemoryEngine):
    """
    2 consecutive losses -> CAUTION (0.5x allocation scale down).
    """
    now = datetime.now(timezone.utc)
    trades = [
        {"result": "LOSS", "pnl": -30.0, "close_date": now - timedelta(hours=1)},
        {"result": "LOSS", "pnl": -30.0, "close_date": now - timedelta(hours=2)},
        {"result": "WIN", "pnl": 50.0, "close_date": now - timedelta(hours=3)},
        {"result": "WIN", "pnl": 50.0, "close_date": now - timedelta(hours=4)},
    ]

    score = memory_engine.evaluate_strategy_health(strategy_id="cautionary_flow", trade_history=trades)

    assert score.health_status == StrategyHealthStatus.CAUTION
    assert score.recommended_weight == 0.5
    assert score.consecutive_losses == 2


def test_strategy_health_healthy_baseline(memory_engine: RegimeMemoryEngine):
    """
    Balanced metrics (win rate 50%, profit factor 1.25, 0 consecutive losses) -> HEALTHY (1.0x).
    """
    now = datetime.now(timezone.utc)
    trades = [
        {"result": "WIN", "pnl": 50.0, "close_date": now - timedelta(hours=1)},
        {"result": "LOSS", "pnl": -40.0, "close_date": now - timedelta(hours=2)},
        {"result": "WIN", "pnl": 50.0, "close_date": now - timedelta(hours=3)},
        {"result": "LOSS", "pnl": -40.0, "close_date": now - timedelta(hours=4)},
    ]

    score = memory_engine.evaluate_strategy_health(strategy_id="standard_trend", trade_history=trades)

    assert score.health_status == StrategyHealthStatus.HEALTHY
    assert score.recommended_weight == 1.0
    assert score.win_rate == 0.5
    assert score.consecutive_losses == 0


def test_strategy_health_empty_history(memory_engine: RegimeMemoryEngine):
    """Empty history defaults safely to HEALTHY baseline."""
    score = memory_engine.evaluate_strategy_health(strategy_id="new_strat", trade_history=[])
    assert score.health_status == StrategyHealthStatus.HEALTHY
    assert score.recommended_weight == 1.0
    assert score.total_trades == 0


# ─────────────────────────────────────────────────────────────────────────────
# 6. Memory Ledger & Aggregation Summary
# ─────────────────────────────────────────────────────────────────────────────

def test_memory_ledger_and_summary(memory_engine: RegimeMemoryEngine):
    """Verify recording diagnostics and generating aggregated summary."""
    trade1 = {
        "trade_id": "t1",
        "symbol": "EURUSD",
        "strategy_id": "strat_a",
        "result": "LOSS",
        "pnl": -50.0,
        "close_date": datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc),
    }
    context1 = {"liquidity_sweep": True}

    trade2 = {
        "trade_id": "t2",
        "symbol": "GBPUSD",
        "strategy_id": "strat_b",
        "result": "LOSS",
        "pnl": -60.0,
        "close_date": datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc),
    }
    context2 = {"macro_news_volatility": True}

    trade3 = {
        "trade_id": "t3",
        "symbol": "USDJPY",
        "strategy_id": "strat_a",
        "result": "WIN",
        "pnl": 120.0,
        "close_date": datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc),
    }

    # Record all 3
    memory_engine.diagnose_and_record(trade1, context1)
    memory_engine.diagnose_and_record(trade2, context2)
    memory_engine.diagnose_and_record(trade3)

    # Evaluate health for both strategies
    memory_engine.evaluate_strategy_health("strat_a", [trade1, trade3])
    memory_engine.evaluate_strategy_health(
        "strat_b",
        [trade2, {"result": "LOSS", "pnl": -50}, {"result": "LOSS", "pnl": -50}],
    )

    summary = memory_engine.get_memory_summary()

    assert summary["total_diagnostics"] == 3
    assert summary["root_cause_distribution"]["INSTITUTIONAL_LIQUIDITY_SWEEP"] == 1
    assert summary["root_cause_distribution"]["MACRO_NEWS_VOLATILITY"] == 1
    assert summary["root_cause_distribution"]["TAKE_PROFIT_HIT"] == 1
    assert len(summary["recent_lessons"]) == 3
    assert "strat_b" in summary["quarantined_strategies"]


# ─────────────────────────────────────────────────────────────────────────────
# 7. Integration with AdaptiveRuleTuningEngine & TradeJournal
# ─────────────────────────────────────────────────────────────────────────────

def test_sync_with_adaptive_tuning_engine(memory_engine: RegimeMemoryEngine):
    """
    Syncing with AdaptiveRuleTuningEngine applies the prescribed +0.35 stop delta
    to calculate the effective adaptive stop buffer (e.g. 1.0 + 0.35 = 1.35x).
    """
    strategy_id = "reversal_hunter"

    # Record a liquidity sweep diagnostic for this strategy
    trade = {
        "trade_id": "t_sweep_sync",
        "symbol": "EURUSD",
        "strategy_id": strategy_id,
        "result": "LOSS",
        "pnl": -50.0,
        "close_date": datetime.now(timezone.utc),
    }
    memory_engine.diagnose_and_record(trade, market_context={"liquidity_sweep": True})

    # Evaluate health
    memory_engine.evaluate_strategy_health(strategy_id, [trade])

    # Run sync
    sync_result = memory_engine.sync_with_adaptive_tuning_engine(strategy_id=strategy_id, symbol="EURUSD")

    assert sync_result["strategy_id"] == strategy_id
    assert sync_result["atr_stop_multiplier_delta"] == 0.35
    assert sync_result["effective_stop_multiplier"] >= 1.35
    assert "recovery_status" in sync_result


def test_trade_journal_item_compatibility(memory_engine: RegimeMemoryEngine):
    """Verify diagnose_trade_outcome directly accepts a TradeJournalItem model."""
    journal_item = TradeJournalItem(
        id=999,
        symbol="EURUSD",
        direction="BUY",
        entryPrice=1.0850,
        exitPrice=1.0790,
        stopLoss=1.0800,
        takeProfit=1.0950,
        timeframe="M15",
        marketSession="LONDON",
        tradeDate=datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc),
        closeDate=datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc),
        status="CLOSED",
        result="LOSS",
        profitLoss=-60.0,
        reasonForEntry="Order block retest",
        reasonForExit="Stop loss triggered on liquidity sweep",
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )

    diagnostic = memory_engine.diagnose_trade_outcome(
        trade_record=journal_item,
        market_context={"post_stop_price": 1.0880, "reversal_direction": "UP"},
    )

    assert diagnostic.trade_id == "999"
    assert diagnostic.symbol == "EURUSD"
    assert diagnostic.root_cause == RootCauseType.INSTITUTIONAL_LIQUIDITY_SWEEP
    assert diagnostic.prescribed_adaptation["atr_stop_multiplier_delta"] == 0.35


# ─────────────────────────────────────────────────────────────────────────────
# 8. Closed-Loop Diagnostics via SignalOutcomeResolver
# ─────────────────────────────────────────────────────────────────────────────

def test_signal_outcome_resolver_invokes_diagnose_and_record_on_sweep_loss(memory_engine: RegimeMemoryEngine):
    """
    Verify signal_outcome_resolver.resolve_trade_outcome:
    1. Invokes regime_memory_engine.diagnose_and_record().
    2. Directly populates reasonForExit and lessonLearned on trade.
    3. Prescribes +35% ATR stop buffer expansion for liquidity sweeps.
    """
    trade = TradeJournalItem(
        id=7771,
        symbol="EURUSD",
        direction="BUY",
        entryPrice=1.0850,
        exitPrice=1.0798,
        stopLoss=1.0800,
        takeProfit=1.0950,
        timeframe="M15",
        marketSession="LONDON",
        tradeDate=datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc),
        closeDate=datetime(2026, 9, 28, 14, 30, tzinfo=timezone.utc),
        status="CLOSED",
        result="LOSS",
        profitLoss=-52.0,
        reasonForEntry="Demand zone tap",
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )
    context = {
        "trough_price": 1.0795,
        "post_stop_price": 1.0890,
        "reversal_direction": "UP",
    }

    diag = signal_outcome_resolver.resolve_trade_outcome(trade=trade, market_context=context)

    assert diag.root_cause == RootCauseType.INSTITUTIONAL_LIQUIDITY_SWEEP
    assert diag.prescribed_adaptation["atr_stop_multiplier_delta"] == 0.35
    assert trade.reasonForExit == diag.rationale
    assert trade.lessonLearned == diag.lesson_learned
    assert "liquidity sweep wick" in trade.lessonLearned.lower()

    # Verify ledger recorded diagnostic
    assert memory_engine.get_memory_summary()["total_diagnostics"] >= 1


def test_signal_outcome_resolver_invokes_diagnose_and_record_on_win(memory_engine: RegimeMemoryEngine):
    """
    Verify signal_outcome_resolver.resolve_trade_outcome for a winning trade:
    1. Root cause diagnosed as TAKE_PROFIT_HIT.
    2. Directly populates reasonForExit and lessonLearned.
    3. Reinforces strategy baseline.
    """
    trade = TradeJournalItem(
        id=7772,
        symbol="GBPUSD",
        strategyId="cable_trend",
        direction="BUY",
        entryPrice=1.2800,
        exitPrice=1.2860,
        stopLoss=1.2770,
        takeProfit=1.2860,
        timeframe="M15",
        marketSession="LONDON",
        tradeDate=datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc),
        closeDate=datetime(2026, 9, 28, 10, 15, tzinfo=timezone.utc),
        status="CLOSED",
        result="WIN",
        profitLoss=60.0,
        reasonForEntry="Bullish order block",
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )

    diag = signal_outcome_resolver.resolve_trade_outcome(trade=trade)

    assert diag.root_cause == RootCauseType.TAKE_PROFIT_HIT
    assert diag.outcome == "WIN"
    assert trade.reasonForExit == diag.rationale
    assert trade.lessonLearned == diag.lesson_learned
    assert "conviction reinforced" in trade.lessonLearned.lower()


def test_signal_outcome_resolver_quarantines_underperforming_strategy(memory_engine: RegimeMemoryEngine):
    """
    Strategies with win rate < 35% or >= 3 consecutive losses are quarantined
    to paper evaluation mode (QUARANTINED_PAPER, weight = 0.0x).
    """
    now = datetime.now(timezone.utc)
    strat_id = "failing_scalp"

    # Pre-populate repository with 3 consecutive losses
    trade_journal_repository.clear()
    for i in range(3):
        trade_journal_repository.create_trade(TradeJournalCreate(
            strategyId=strat_id,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.0850,
            exitPrice=1.0800,
            stopLoss=1.0800,
            takeProfit=1.0950,
            timeframe="M15",
            marketSession="LONDON",
            tradeDate=now - timedelta(hours=4 - i),
            closeDate=now - timedelta(hours=3 - i),
            status="CLOSED",
            result="LOSS",
            profitLoss=-50.0,
            reasonForEntry="Scalp setup",
        ))

    # Fourth trade triggers outcome resolution
    last_trade = trade_journal_repository.list_trades()[0]
    signal_outcome_resolver.resolve_trade_outcome(trade=last_trade)

    # Verify strategy health is QUARANTINED_PAPER
    health_score = memory_engine._strategy_health_cache.get(strat_id)
    assert health_score is not None
    assert health_score.health_status == StrategyHealthStatus.QUARANTINED_PAPER
    assert health_score.recommended_weight == 0.0
    assert health_score.consecutive_losses >= 3

    # Verify AdaptiveRuleTuningEngine tuning profile reflects quarantine
    tuning_profile = adaptive_tuning_engine.get_strategy_tuning(strategy_id=strat_id)
    assert tuning_profile.recommended_weight == 0.0
    assert tuning_profile.health_status == "QUARANTINED_PAPER"


def test_signal_outcome_resolver_boosts_resilient_strategy(memory_engine: RegimeMemoryEngine):
    """
    Strategies with win rate >= 60% and PF >= 1.8 are boosted
    (BOOSTED, weight = 1.5x).
    """
    now = datetime.now(timezone.utc)
    strat_id = "resilient_sniper"

    # Pre-populate repository with 7 wins ($100 each) and 3 losses ($40 each) -> 70% win rate, PF = 5.83
    trade_journal_repository.clear()
    # Losses first
    for i in range(3):
        trade_journal_repository.create_trade(TradeJournalCreate(
            strategyId=strat_id,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.0850,
            exitPrice=1.0810,
            stopLoss=1.0810,
            takeProfit=1.0950,
            timeframe="M15",
            marketSession="LONDON",
            tradeDate=now - timedelta(hours=10 - i),
            closeDate=now - timedelta(hours=9 - i),
            status="CLOSED",
            result="LOSS",
            profitLoss=-40.0,
            reasonForEntry="Breakout setup",
        ))
    # Wins latest
    for i in range(7):
        trade_journal_repository.create_trade(TradeJournalCreate(
            strategyId=strat_id,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.0850,
            exitPrice=1.0950,
            stopLoss=1.0810,
            takeProfit=1.0950,
            timeframe="M15",
            marketSession="LONDON",
            tradeDate=now - timedelta(hours=7 - i),
            closeDate=now - timedelta(hours=6 - i),
            status="CLOSED",
            result="WIN",
            profitLoss=100.0,
            reasonForEntry="Breakout setup",
        ))

    last_trade = trade_journal_repository.list_trades()[0]
    signal_outcome_resolver.resolve_trade_outcome(trade=last_trade)

    health_score = memory_engine._strategy_health_cache.get(strat_id)
    assert health_score is not None
    assert health_score.health_status == StrategyHealthStatus.BOOSTED
    assert health_score.recommended_weight == 1.5
    assert health_score.win_rate >= 0.60
    assert health_score.profit_factor >= 1.8

    tuning_profile = adaptive_tuning_engine.get_strategy_tuning(strategy_id=strat_id)
    assert tuning_profile.recommended_weight == 1.5
    assert tuning_profile.health_status == "BOOSTED"


def test_loss_recovery_progression_and_ceiling_maintained(memory_engine: RegimeMemoryEngine):
    """
    Verify loss-recovery progression across streak:
    - 1 loss = 2.0x target (RECOVERY_2X)
    - 2 losses = 4.0x target (RECOVERY_4X)
    - hard $20.00 ceiling = RECOVERY_LOCKED when accumulated streak loss >= $20.00
    - immediate reset on win = 1.0x target (BASELINE, $0.00 streak loss).
    """
    now = datetime.now(timezone.utc)
    strat_id = "recovery_progression_strat"
    trade_journal_repository.clear()

    # Step 1: 1 Loss of $6.00 -> 2.0x target
    trade_1 = trade_journal_repository.create_trade(TradeJournalCreate(
        strategyId=strat_id,
        symbol="EURUSD",
        direction="BUY",
        entryPrice=1.0850,
        stopLoss=1.0790,
        takeProfit=1.0950,
        timeframe="M15",
        marketSession="LONDON",
        tradeDate=now - timedelta(hours=3),
        closeDate=now - timedelta(hours=2),
        status="CLOSED",
        result="LOSS",
        profitLoss=-6.00,
        reasonForEntry="Order block tap",
    ))
    signal_outcome_resolver.resolve_trade_outcome(trade=trade_1)

    metrics_1 = adaptive_tuning_engine.get_loss_recovery_metrics(strategy_id=strat_id)
    assert metrics_1.consecutive_losses == 1
    assert metrics_1.profit_recovery_multiplier == 2.0
    assert metrics_1.recovery_status == "RECOVERY_2X"
    assert metrics_1.accumulated_streak_loss == Decimal("6.00")

    # Step 2: Second consecutive loss of $7.00 -> 4.0x target
    trade_2 = trade_journal_repository.create_trade(TradeJournalCreate(
        strategyId=strat_id,
        symbol="EURUSD",
        direction="SELL",
        entryPrice=1.0800,
        stopLoss=1.0870,
        takeProfit=1.0700,
        timeframe="M15",
        marketSession="LONDON",
        tradeDate=now - timedelta(hours=2),
        closeDate=now - timedelta(hours=1),
        status="CLOSED",
        result="LOSS",
        profitLoss=-7.00,
        reasonForEntry="Rejection block",
    ))
    signal_outcome_resolver.resolve_trade_outcome(trade=trade_2)

    metrics_2 = adaptive_tuning_engine.get_loss_recovery_metrics(strategy_id=strat_id)
    assert metrics_2.consecutive_losses == 2
    assert metrics_2.profit_recovery_multiplier == 4.0
    assert metrics_2.recovery_status == "RECOVERY_4X"
    assert metrics_2.accumulated_streak_loss == Decimal("13.00")

    # Step 3: Third loss pushing past $20.00 ceiling ($13 + $8 = $21 > $20)
    trade_3 = trade_journal_repository.create_trade(TradeJournalCreate(
        strategyId=strat_id,
        symbol="EURUSD",
        direction="BUY",
        entryPrice=1.0800,
        stopLoss=1.0720,
        takeProfit=1.0900,
        timeframe="M15",
        marketSession="LONDON",
        tradeDate=now - timedelta(minutes=50),
        closeDate=now - timedelta(minutes=30),
        status="CLOSED",
        result="LOSS",
        profitLoss=-8.00,
        reasonForEntry="Breakout",
    ))
    signal_outcome_resolver.resolve_trade_outcome(trade=trade_3)

    metrics_3 = adaptive_tuning_engine.get_loss_recovery_metrics(strategy_id=strat_id)
    assert metrics_3.accumulated_streak_loss >= Decimal("20.00")
    assert metrics_3.recovery_status == "RECOVERY_LOCKED"

    # Step 4: Subsequent win immediately resets multiplier to 1.0x and streak loss to $0.00
    trade_win = trade_journal_repository.create_trade(TradeJournalCreate(
        strategyId=strat_id,
        symbol="EURUSD",
        direction="BUY",
        entryPrice=1.0800,
        stopLoss=1.0750,
        takeProfit=1.0950,
        timeframe="M15",
        marketSession="LONDON",
        tradeDate=now - timedelta(minutes=20),
        closeDate=now - timedelta(minutes=5),
        status="CLOSED",
        result="WIN",
        profitLoss=25.00,
        reasonForEntry="Recovery trade execution",
    ))
    signal_outcome_resolver.resolve_trade_outcome(trade=trade_win)

    metrics_win = adaptive_tuning_engine.get_loss_recovery_metrics(strategy_id=strat_id)
    assert metrics_win.consecutive_losses == 0
    assert metrics_win.profit_recovery_multiplier == 1.0
    assert metrics_win.recovery_status == "BASELINE"
    assert metrics_win.accumulated_streak_loss == Decimal("0.00")


def test_signal_outcome_resolver_execute_resolve_signals_end_to_end(memory_engine: RegimeMemoryEngine):
    """
    Test that resolve_signals() automatically scans active open trades,
    detects breach / simulated exit, diagnoses root cause via regime memory engine,
    and updates reasonForExit and lessonLearned in the repository.
    """
    now = datetime.now(timezone.utc)
    trade_journal_repository.clear()

    # Create an active open trade
    created_trade = trade_journal_repository.create_trade(TradeJournalCreate(
        signalId=9001,
        strategyId="smc_breaker",
        symbol="EURUSD",
        direction="BUY",
        entryPrice=1.0850,
        stopLoss=1.0800,
        takeProfit=1.0950,
        fillPrice=1.0850,
        fillTime=now - timedelta(minutes=20),
        timeframe="M15",
        marketSession="LONDON",
        tradeDate=now - timedelta(minutes=20),
        status="OPEN",
        result="OPEN",
        reasonForEntry="Institutional order block tap",
    ))

    # Run resolve_signals with force_simulate=True
    summary = signal_outcome_resolver.resolve_signals(force_simulate=True)
    assert summary.resolvedCount >= 1

    # Fetch updated trade from repository
    updated = trade_journal_repository.get_trade(created_trade.id)
    assert updated is not None
    assert updated.status == "CLOSED"
    assert updated.reasonForExit is not None and len(updated.reasonForExit) > 0
    assert updated.lessonLearned is not None and len(updated.lessonLearned) > 0

    # Verify diagnostic was recorded in memory ledger
    assert memory_engine.get_memory_summary()["total_diagnostics"] >= 1

