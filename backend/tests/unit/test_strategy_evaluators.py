"""
Falcon Phase 7 — Strategy Evaluators Unit Tests (M6)
"""
import pytest
from unittest.mock import MagicMock

from app.schemas.decision_context import DecisionContext
from app.schemas.market_regime import MarketRegimeReport, MarketRegime, RegimeStrength, RegimeConfidence
from app.core.engines.decision.strategy_evaluators.trend_pullback_evaluator import TrendPullbackEvaluator
from app.core.engines.decision.strategy_evaluators.breakout_evaluator import BreakoutEvaluator
from app.core.engines.decision.strategy_evaluators.range_reversal_evaluator import RangeReversalEvaluator
from app.core.engines.decision.strategy_evaluators.liquidity_sweep_evaluator import LiquiditySweepEvaluator


def _make_context(direction: str, trend: str, regime: str, volatility: str) -> DecisionContext:
    mock_candidate = MagicMock()
    mock_candidate.direction.name = direction
    
    mock_regime = None
    if regime:
        mock_regime = MarketRegimeReport.model_construct(
            regime=MarketRegime(regime),
            strength=RegimeStrength.MODERATE,
            confidence=RegimeConfidence.HIGH
        )

    return DecisionContext.model_construct(
        candidateId="test-cand",
        missionId="test-miss",
        candidate=mock_candidate,
        trend=trend,
        regimeReport=mock_regime,
        volatility=volatility
    )


class TestTrendPullbackEvaluator:
    def setup_method(self):
        self.evaluator = TrendPullbackEvaluator()

    def test_pass_on_bullish_alignment(self):
        ctx = _make_context(direction="BUY", trend="BULLISH", regime="TRENDING_BULLISH", volatility="NORMAL")
        result = self.evaluator.evaluate(ctx)
        assert result.passed is True
        assert result.score == 100.0

    def test_fail_on_counter_trend(self):
        ctx = _make_context(direction="BUY", trend="BEARISH", regime="TRENDING_BEARISH", volatility="NORMAL")
        result = self.evaluator.evaluate(ctx)
        assert result.passed is False
        assert "Direction Alignment" in result.failedRules


class TestBreakoutEvaluator:
    def setup_method(self):
        self.evaluator = BreakoutEvaluator()

    def test_pass_on_high_vol_and_breakout_regime(self):
        ctx = _make_context(direction="BUY", trend="SIDEWAYS", regime="BREAKOUT", volatility="HIGH")
        result = self.evaluator.evaluate(ctx)
        assert result.passed is True
        assert result.score == 100.0

    def test_fail_on_low_vol(self):
        ctx = _make_context(direction="BUY", trend="SIDEWAYS", regime="BREAKOUT", volatility="LOW")
        result = self.evaluator.evaluate(ctx)
        assert result.passed is False
        assert "Volatility Expansion" in result.failedRules


class TestRangeReversalEvaluator:
    def setup_method(self):
        self.evaluator = RangeReversalEvaluator()

    def test_pass_on_ranging_and_normal_vol(self):
        ctx = _make_context(direction="BUY", trend="SIDEWAYS", regime="RANGING", volatility="NORMAL")
        result = self.evaluator.evaluate(ctx)
        assert result.passed is True
        assert result.score == 100.0

    def test_fail_on_trending_regime(self):
        ctx = _make_context(direction="BUY", trend="BULLISH", regime="TRENDING_BULLISH", volatility="NORMAL")
        result = self.evaluator.evaluate(ctx)
        assert result.passed is False
        assert "Ranging Regime" in result.failedRules


class TestLiquiditySweepEvaluator:
    def setup_method(self):
        self.evaluator = LiquiditySweepEvaluator()

    def test_pass_on_reversal_regime_and_high_vol(self):
        ctx = _make_context(direction="SELL", trend="BULLISH", regime="REVERSAL", volatility="HIGH")
        result = self.evaluator.evaluate(ctx)
        assert result.passed is True
        assert result.score == 100.0
