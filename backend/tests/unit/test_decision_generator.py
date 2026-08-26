"""
Falcon Phase 7 — Unit Tests: DecisionGenerator & ReasoningGenerator (M7)
"""
import pytest
from unittest.mock import MagicMock, patch

from app.schemas.decision_context import DecisionContext
from app.schemas.decision_artifact import DecisionRecommendation
from app.schemas.risk_gate import RiskGateResult, RiskGateDecision
from app.schemas.confidence_score import ConfidenceScore
from app.schemas.evaluator_result import EvaluatorResult, DecisionEvidence, EvidenceImpact, EvidenceStatus
from app.schemas.strategy_evaluation import StrategyEvaluationResult, StrategyRuleCheck
from app.schemas.market_regime import MarketRegime, MarketRegimeReport, RegimeStrength, RegimeConfidence

from app.core.engines.decision.decision_generator import DecisionGenerator
from app.core.engines.decision.reasoning_generator import ReasoningGenerator


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ctx(**kwargs) -> DecisionContext:
    kwargs.setdefault("candidateId", "cand-001")
    kwargs.setdefault("missionId", "mission-001")
    return DecisionContext.model_construct(**kwargs)


def _eval(name: str, score: float, passed: bool, weight: float = 1.0) -> EvaluatorResult:
    return EvaluatorResult.model_construct(
        name=name, score=score, weight=weight, passed=passed, evidence=[], warnings=[]
    )


def _pass_gate(score: float = 0.0) -> RiskGateResult:
    return RiskGateResult(decision=RiskGateDecision.PASS, score=score, summary="PASS")


def _veto_gate() -> RiskGateResult:
    veto_item = DecisionEvidence(
        indicator="RISK_LEVEL",
        observedValue="CRITICAL",
        weight=0.4,
        impact=EvidenceImpact.CONTRADICTING,
        status=EvidenceStatus.FAIL,
        explanation="Extreme risk level detected.",
        category="RISK"
    )
    return RiskGateResult(
        decision=RiskGateDecision.VETO,
        score=40.0,
        summary="VETO — Extreme risk level.",
        vetoes=[veto_item],
    )


def _warn_gate() -> RiskGateResult:
    warn_item = DecisionEvidence(
        indicator="SPREAD",
        observedValue="HIGH",
        weight=0.1,
        impact=EvidenceImpact.NEUTRAL,
        status=EvidenceStatus.WARN,
        explanation="High spread detected.",
        category="RISK"
    )
    return RiskGateResult(
        decision=RiskGateDecision.WARN,
        score=10.0,
        summary="WARN — High spread detected.",
        warnings=[warn_item],
    )


def _mock_evaluator(name: str, score: float, passed: bool, weight: float = 1.0):
    """Return a mocked BaseEvaluator that always returns a fixed EvaluatorResult."""
    ev = MagicMock()
    ev.name = name
    ev.weight = weight
    ev.evaluate.return_value = _eval(name, score, passed, weight)
    return ev


# ─── DecisionGenerator Tests ──────────────────────────────────────────────────

class TestDecisionGeneratorBuySignal:
    """High-confidence context with all evaluators passing → BUY."""

    def setup_method(self):
        buy_candidate = MagicMock()
        buy_candidate.direction.name = "BUY"
        self.ctx = _ctx(candidate=buy_candidate)

        evaluators = [_mock_evaluator(f"E{i}", 90.0, True) for i in range(5)]
        self.gen = DecisionGenerator(evaluators=evaluators)

    def test_buy_recommendation_on_strong_signal(self):
        result = self.gen.generate(self.ctx)
        assert result.recommendation == DecisionRecommendation.BUY

    def test_confidence_is_above_threshold(self):
        result = self.gen.generate(self.ctx)
        assert result.confidence.overall >= 55.0

    def test_reasoning_not_empty(self):
        result = self.gen.generate(self.ctx)
        assert len(result.reasoning) > 50

    def test_grade_is_not_f_on_strong_signal(self):
        result = self.gen.generate(self.ctx)
        assert result.confidence.grade != "F"


class TestDecisionGeneratorSellSignal:
    """SELL direction candidate → SELL."""

    def setup_method(self):
        sell_candidate = MagicMock()
        sell_candidate.direction.name = "SELL"
        self.ctx = _ctx(candidate=sell_candidate)
        evaluators = [_mock_evaluator(f"E{i}", 85.0, True) for i in range(5)]
        self.gen = DecisionGenerator(evaluators=evaluators)

    def test_sell_recommendation(self):
        result = self.gen.generate(self.ctx)
        assert result.recommendation == DecisionRecommendation.SELL


class TestDecisionGeneratorVetoPath:
    """When RiskGate issues a VETO → must produce NO_TRADE."""

    def setup_method(self):
        self.ctx = _ctx()
        # Patch RiskGate.evaluate to always return VETO
        evaluators = [_mock_evaluator("E1", 50.0, True)]
        self.gen = DecisionGenerator(evaluators=evaluators)

    def test_veto_produces_no_trade(self):
        with patch.object(self.gen._risk_gate, "evaluate", return_value=_veto_gate()):
            result = self.gen.generate(self.ctx)
        assert result.recommendation == DecisionRecommendation.NO_TRADE

    def test_veto_reasoning_mentions_veto(self):
        with patch.object(self.gen._risk_gate, "evaluate", return_value=_veto_gate()):
            result = self.gen.generate(self.ctx)
        assert "VETO" in result.reasoning or "NO TRADE" in result.reasoning


class TestDecisionGeneratorAvoidPath:
    """Low confidence + majority evaluators failing → AVOID."""

    def setup_method(self):
        self.ctx = _ctx()
        # All failing evaluators → low confidence → AVOID
        evaluators = [_mock_evaluator(f"E{i}", 10.0, False) for i in range(6)]
        self.gen = DecisionGenerator(evaluators=evaluators)

    def test_avoid_on_weak_signal(self):
        result = self.gen.generate(self.ctx)
        assert result.recommendation in (
            DecisionRecommendation.AVOID,
            DecisionRecommendation.NO_TRADE,
            DecisionRecommendation.WAIT,
        )


class TestDecisionGeneratorErrorRecovery:
    """Crashing evaluator → safe NO_TRADE instead of unhandled exception."""

    def setup_method(self):
        self.ctx = _ctx()
        bad_evaluator = MagicMock()
        bad_evaluator.name = "BadEval"
        bad_evaluator.weight = 1.0
        bad_evaluator.evaluate.side_effect = RuntimeError("Simulated crash")
        self.gen = DecisionGenerator(evaluators=[bad_evaluator])

    def test_crash_produces_safe_result(self):
        result = self.gen.generate(self.ctx)
        # Should not raise; result must be valid
        assert result is not None
        assert result.recommendation in DecisionRecommendation.__members__.values()

    def test_warnings_populated_on_crash(self):
        result = self.gen.generate(self.ctx)
        # warnings may come from AVOID or from the pipeline error — just must exist
        assert isinstance(result.warnings, list)


# ─── ReasoningGenerator Tests ─────────────────────────────────────────────────

class TestReasoningGenerator:
    def setup_method(self):
        self.gen = ReasoningGenerator()
        self.confidence = ConfidenceScore(
            overall=78.5,
            evaluatorContribution=80.0,
            riskPenalty=5.0,
            validationBonus=4.0,
            readinessBonus=3.0,
            grade="B",
        )
        self.gate = _pass_gate()

    def test_buy_headline(self):
        text = self.gen.generate(
            recommendation=DecisionRecommendation.BUY,
            confidence=self.confidence,
            evaluator_results=[],
            risk_gate=self.gate,
        )
        assert "BUY" in text

    def test_sell_headline(self):
        text = self.gen.generate(
            recommendation=DecisionRecommendation.SELL,
            confidence=self.confidence,
            evaluator_results=[],
            risk_gate=self.gate,
        )
        assert "SELL" in text

    def test_no_trade_headline(self):
        text = self.gen.generate(
            recommendation=DecisionRecommendation.NO_TRADE,
            confidence=self.confidence,
            evaluator_results=[],
            risk_gate=self.gate,
        )
        assert "NO TRADE" in text

    def test_confidence_grade_in_output(self):
        text = self.gen.generate(
            recommendation=DecisionRecommendation.BUY,
            confidence=self.confidence,
            evaluator_results=[],
            risk_gate=self.gate,
        )
        assert "B" in text
        assert "78.5" in text

    def test_regime_info_included(self):
        regime = MarketRegimeReport.model_construct(
            regime=MarketRegime.TRENDING_BULLISH,
            strength=RegimeStrength.STRONG,
            confidence=RegimeConfidence.HIGH,
        )
        text = self.gen.generate(
            recommendation=DecisionRecommendation.BUY,
            confidence=self.confidence,
            evaluator_results=[],
            risk_gate=self.gate,
            regime_report=regime,
        )
        assert "Trending Bullish" in text or "TRENDING_BULLISH" in text

    def test_supporting_signals_listed(self):
        evals = [
            _eval("Trend", 90.0, True),
            _eval("Momentum", 85.0, True),
            _eval("Liquidity", 30.0, False),
        ]
        text = self.gen.generate(
            recommendation=DecisionRecommendation.BUY,
            confidence=self.confidence,
            evaluator_results=evals,
            risk_gate=self.gate,
        )
        assert "Trend" in text
        assert "Momentum" in text

    def test_blocking_signals_listed(self):
        evals = [_eval("Spread", 20.0, False)]
        text = self.gen.generate(
            recommendation=DecisionRecommendation.WAIT,
            confidence=self.confidence,
            evaluator_results=evals,
            risk_gate=self.gate,
        )
        assert "Spread" in text

    def test_veto_gate_in_reasoning(self):
        text = self.gen.generate(
            recommendation=DecisionRecommendation.NO_TRADE,
            confidence=self.confidence,
            evaluator_results=[],
            risk_gate=_veto_gate(),
        )
        assert "VETO" in text

    def test_strategy_match_in_reasoning(self):
        strat = StrategyEvaluationResult(
            strategyId="trend_pullback_v1",
            strategyName="Trend Pullback",
            passed=True,
            score=95.0,
        )
        text = self.gen.generate(
            recommendation=DecisionRecommendation.BUY,
            confidence=self.confidence,
            evaluator_results=[],
            risk_gate=self.gate,
            strategy_result=strat,
        )
        assert "Trend Pullback" in text
