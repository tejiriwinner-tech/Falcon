"""
Falcon Phase 7 — Unit Tests: ConfidenceEngine (Milestone 4)

Validates the dynamic confidence calculator against deterministic inputs.
"""
import pytest
from app.core.engines.decision.confidence_engine import ConfidenceEngine, ConfidenceResult
from app.schemas.evaluator_result import EvaluatorResult


def _make_result(name: str, score: float, weight: float, passed: bool = True) -> EvaluatorResult:
    return EvaluatorResult.model_construct(
        name=name,
        score=score,
        weight=weight,
        passed=passed,
        evidence=[],
        warnings=[]
    )


class TestConfidenceEngineEmpty:
    def setup_method(self):
        self.engine = ConfidenceEngine()

    def test_empty_list_returns_zero(self):
        result = self.engine.calculate([])
        assert result.final_score == 0.0
        assert result.raw_score == 0.0

    def test_zero_total_weight_returns_zero(self):
        results = [_make_result("A", 90.0, 0.0), _make_result("B", 80.0, 0.0)]
        result = self.engine.calculate(results)
        assert result.final_score == 0.0


class TestConfidenceEngineCalculation:
    def setup_method(self):
        self.engine = ConfidenceEngine()

    def test_single_perfect_evaluator(self):
        results = [_make_result("TrendEvaluator", 100.0, 1.0)]
        result = self.engine.calculate(results)
        assert result.raw_score == 100.0
        assert result.final_score == 100.0

    def test_single_zero_evaluator(self):
        results = [_make_result("TrendEvaluator", 0.0, 1.0)]
        result = self.engine.calculate(results)
        assert result.raw_score == 0.0
        assert result.final_score == 0.0

    def test_weighted_average_correct(self):
        # 80 * 0.6 + 40 * 0.4 = 48 + 16 = 64, / 1.0 = 64
        results = [
            _make_result("A", 80.0, 0.6),
            _make_result("B", 40.0, 0.4),
        ]
        result = self.engine.calculate(results)
        assert result.raw_score == pytest.approx(64.0, abs=0.01)
        assert result.final_score == pytest.approx(64.0, abs=0.01)

    def test_breakdown_contains_all_evaluators(self):
        results = [
            _make_result("TrendEvaluator", 90.0, 0.25),
            _make_result("MomentumEvaluator", 70.0, 0.15),
        ]
        result = self.engine.calculate(results)
        assert "TrendEvaluator" in result.breakdown
        assert "MomentumEvaluator" in result.breakdown

    def test_clamped_to_100(self):
        # Even with a regime modifier of +50%, should not exceed 100
        results = [_make_result("A", 100.0, 1.0)]
        result = self.engine.calculate(results)
        assert result.final_score <= 100.0

    def test_clamped_to_zero(self):
        results = [_make_result("A", 0.0, 1.0)]
        result = self.engine.calculate(results)
        assert result.final_score >= 0.0


class TestConfidenceEngineRegimeModifier:
    def setup_method(self):
        self.engine = ConfidenceEngine()

    def test_no_regime_no_modifier(self):
        results = [_make_result("A", 60.0, 1.0)]
        result = self.engine.calculate(results, regime_report=None)
        assert result.regime_modifier == 0.0
        assert result.final_score == pytest.approx(60.0, abs=0.01)

    def test_trending_bullish_boosts_confidence(self):
        from app.schemas.market_regime import MarketRegimeReport, MarketRegime, RegimeStrength, RegimeConfidence
        regime = MarketRegimeReport.model_construct(
            regime=MarketRegime.TRENDING_BULLISH,
            strength=RegimeStrength.STRONG,
            confidence=RegimeConfidence.HIGH,
        )
        results = [_make_result("A", 80.0, 1.0)]
        result = self.engine.calculate(results, regime_report=regime)
        # modifier = +0.05 * 1.5 = +0.075, final = 80 * 1.075 = 86
        assert result.regime_modifier == pytest.approx(0.075, abs=0.001)
        assert result.final_score == pytest.approx(86.0, abs=0.1)

    def test_uncertain_regime_reduces_confidence(self):
        from app.schemas.market_regime import MarketRegimeReport, MarketRegime, RegimeStrength, RegimeConfidence
        regime = MarketRegimeReport.model_construct(
            regime=MarketRegime.UNCERTAIN,
            strength=RegimeStrength.STRONG,
            confidence=RegimeConfidence.LOW,
        )
        results = [_make_result("A", 80.0, 1.0)]
        result = self.engine.calculate(results, regime_report=regime)
        # modifier = -0.15 * 1.5 = -0.225, final = 80 * 0.775 = 62
        assert result.regime_modifier == pytest.approx(-0.225, abs=0.001)
        assert result.final_score == pytest.approx(62.0, abs=0.1)

    def test_ranging_regime_reduces_confidence(self):
        from app.schemas.market_regime import MarketRegimeReport, MarketRegime, RegimeStrength, RegimeConfidence
        regime = MarketRegimeReport.model_construct(
            regime=MarketRegime.RANGING,
            strength=RegimeStrength.MODERATE,
            confidence=RegimeConfidence.MEDIUM,
        )
        results = [_make_result("A", 70.0, 1.0)]
        result = self.engine.calculate(results, regime_report=regime)
        # modifier = -0.10 * 1.0 = -0.10, final = 70 * 0.90 = 63
        assert result.regime_modifier == pytest.approx(-0.10, abs=0.001)
        assert result.final_score == pytest.approx(63.0, abs=0.1)


class TestLegacyCalculateFromScores:
    """Validates the backward-compatible helper used by DecisionEngine v1."""

    def setup_method(self):
        self.engine = ConfidenceEngine()

    def test_known_values(self):
        # Default weights: candidate=0.30, validation=0.25, risk=0.25, execution=0.20
        # 0.30*80 + 0.25*75 + 0.25*80 + 0.20*90 = 24 + 18.75 + 20 + 18 = 80.75
        score = self.engine.calculate_from_scores(
            candidate_confidence=80.0,
            validation_score=75.0,
            risk_confidence=80.0,
            execution_score=90.0,
        )
        assert score == pytest.approx(80.75, abs=0.01)

    def test_always_clamped(self):
        score = self.engine.calculate_from_scores(200.0, 200.0, 200.0, 200.0)
        assert score == 100.0

    def test_zero_inputs(self):
        score = self.engine.calculate_from_scores(0.0, 0.0, 0.0, 0.0)
        assert score == 0.0

    def test_custom_weights(self):
        # 1.0 weight on candidate only
        score = self.engine.calculate_from_scores(
            candidate_confidence=60.0,
            validation_score=0.0,
            risk_confidence=0.0,
            execution_score=0.0,
            weights={"candidate": 1.0, "validation": 0.0, "risk": 0.0, "execution": 0.0},
        )
        assert score == pytest.approx(60.0, abs=0.01)
