"""
Falcon Phase 7 — Unit Tests: Technical Evaluators (Milestone 2)

Tests the independent technical evaluators:
  - TrendEvaluator
  - StructureEvaluator
  - MomentumEvaluator
  - LiquidityEvaluator
  - SessionEvaluator
  - SpreadEvaluator
  - VolatilityEvaluator
"""
import pytest
from app.schemas.decision_context import DecisionContext
from app.schemas.evaluator_result import EvidenceImpact, EvidenceStatus
from app.core.engines.decision.evaluators.trend_evaluator import TrendEvaluator
from app.core.engines.decision.evaluators.structure_evaluator import StructureEvaluator
from app.core.engines.decision.evaluators.momentum_evaluator import MomentumEvaluator
from app.core.engines.decision.evaluators.liquidity_evaluator import LiquidityEvaluator
from app.core.engines.decision.evaluators.session_evaluator import SessionEvaluator
from app.core.engines.decision.evaluators.spread_evaluator import SpreadEvaluator
from app.core.engines.decision.evaluators.volatility_evaluator import VolatilityEvaluator


def _make_context(candidate_dir="WAIT", **kwargs):
    """Helper to construct a DecisionContext for testing evaluators."""
    kwargs.setdefault("candidateId", "cand-001")
    kwargs.setdefault("missionId", "mission-001")
    kwargs.setdefault("candidateDirection", candidate_dir)
    return DecisionContext.model_construct(**kwargs)


class TestTrendEvaluator:
    def setup_method(self):
        self.evaluator = TrendEvaluator()

    def test_bullish_alignment(self):
        ctx = _make_context(candidate_dir="BUY", trend="BULLISH")
        result = self.evaluator.evaluate(ctx)
        
        assert result.passed is True
        assert result.score == 100.0
        assert len(result.evidence) == 1
        assert result.evidence[0].impact == EvidenceImpact.SUPPORTING
        assert result.evidence[0].status == EvidenceStatus.PASS
        assert "aligned with the BUY direction" in result.evidence[0].explanation

    def test_bearish_alignment(self):
        ctx = _make_context(candidate_dir="SELL", trend="BEARISH")
        result = self.evaluator.evaluate(ctx)
        
        assert result.passed is True
        assert result.score == 100.0
        assert result.evidence[0].impact == EvidenceImpact.SUPPORTING

    def test_contradicting_trend(self):
        ctx = _make_context(candidate_dir="BUY", trend="BEARISH")
        result = self.evaluator.evaluate(ctx)
        
        assert result.passed is False
        assert result.score == 0.0
        assert result.evidence[0].impact == EvidenceImpact.CONTRADICTING
        assert result.evidence[0].status == EvidenceStatus.FAIL

    def test_neutral_trend(self):
        ctx = _make_context(candidate_dir="BUY", trend="NEUTRAL")
        result = self.evaluator.evaluate(ctx)
        
        assert result.passed is False
        assert result.score == 40.0
        assert result.evidence[0].impact == EvidenceImpact.NEUTRAL
        assert result.evidence[0].status == EvidenceStatus.WARN

    def test_no_direction(self):
        ctx = _make_context(candidate_dir="WAIT", trend="BULLISH")
        result = self.evaluator.evaluate(ctx)
        
        assert result.passed is False
        assert result.score == 0.0
        assert len(result.warnings) == 1


class TestMomentumEvaluator:
    def setup_method(self):
        self.evaluator = MomentumEvaluator()

    def test_strong_momentum(self):
        ctx = _make_context(candidate_dir="BUY", candidateConfidence=85.0)
        result = self.evaluator.evaluate(ctx)
        assert result.passed is True
        assert result.score == 100.0
        assert result.evidence[0].status == EvidenceStatus.PASS

    def test_weak_momentum(self):
        ctx = _make_context(candidate_dir="SELL", candidateConfidence=45.0)
        result = self.evaluator.evaluate(ctx)
        assert result.passed is False
        assert result.score == 40.0
        assert result.evidence[0].status == EvidenceStatus.WARN

    def test_poor_momentum(self):
        ctx = _make_context(candidate_dir="BUY", candidateConfidence=20.0)
        result = self.evaluator.evaluate(ctx)
        assert result.passed is False
        assert result.score == 0.0
        assert result.evidence[0].status == EvidenceStatus.FAIL


class TestSessionEvaluator:
    def setup_method(self):
        self.evaluator = SessionEvaluator()

    def test_market_closed(self):
        ctx = _make_context(marketOpen=False, session="London", preferredSessions=["London"])
        result = self.evaluator.evaluate(ctx)
        assert result.passed is False
        assert result.score == 0.0
        assert result.evidence[0].observedValue == "CLOSED"
        assert result.evidence[0].status == EvidenceStatus.FAIL

    def test_preferred_session(self):
        ctx = _make_context(marketOpen=True, session="London", preferredSessions=["London", "New York"])
        result = self.evaluator.evaluate(ctx)
        assert result.passed is True
        assert result.score == 100.0
        assert result.evidence[0].status == EvidenceStatus.PASS

    def test_non_preferred_session(self):
        ctx = _make_context(marketOpen=True, session="Asian", preferredSessions=["London", "New York"])
        result = self.evaluator.evaluate(ctx)
        assert result.passed is False
        assert result.score == 0.0
        assert result.evidence[0].status == EvidenceStatus.FAIL

    def test_no_preference(self):
        ctx = _make_context(marketOpen=True, session="Asian", preferredSessions=[])
        result = self.evaluator.evaluate(ctx)
        assert result.passed is True
        assert result.score == 100.0
        assert result.evidence[0].impact == EvidenceImpact.NEUTRAL


class TestSpreadEvaluator:
    def setup_method(self):
        self.evaluator = SpreadEvaluator()

    def test_good_spread(self):
        ctx = _make_context(spread=0.8)
        result = self.evaluator.evaluate(ctx)
        assert result.passed is True
        assert result.score == 100.0

    def test_high_spread(self):
        ctx = _make_context(spread=3.5)
        result = self.evaluator.evaluate(ctx)
        assert result.passed is False
        assert result.score == 0.0
        assert result.evidence[0].status == EvidenceStatus.FAIL

    def test_zero_spread(self):
        ctx = _make_context(spread=0.0)
        result = self.evaluator.evaluate(ctx)
        assert result.passed is True
        assert result.score == 50.0
        assert result.evidence[0].status == EvidenceStatus.WARN


class TestVolatilityEvaluator:
    def setup_method(self):
        self.evaluator = VolatilityEvaluator()

    def test_moderate_volatility(self):
        ctx = _make_context(volatility="Moderate")
        result = self.evaluator.evaluate(ctx)
        assert result.passed is True
        assert result.score == 100.0

    def test_high_volatility(self):
        ctx = _make_context(volatility="High")
        result = self.evaluator.evaluate(ctx)
        assert result.passed is True
        assert result.score == 60.0
        assert result.evidence[0].status == EvidenceStatus.WARN

    def test_low_volatility(self):
        ctx = _make_context(volatility="Low")
        result = self.evaluator.evaluate(ctx)
        assert result.passed is False
        assert result.score == 20.0
        assert result.evidence[0].status == EvidenceStatus.FAIL


class TestPlaceholders:
    def test_structure_evaluator(self):
        evaluator = StructureEvaluator()
        ctx = _make_context(candidate_dir="BUY")
        res = evaluator.evaluate(ctx)
        assert res.passed is True
        assert res.score == 50.0

    def test_liquidity_evaluator(self):
        evaluator = LiquidityEvaluator()
        ctx = _make_context()
        res = evaluator.evaluate(ctx)
        assert res.passed is True
        assert res.score == 50.0
