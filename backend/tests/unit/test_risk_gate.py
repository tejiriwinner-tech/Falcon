"""
Falcon Phase 7 — Unit Tests: RiskGate (M4) + ConfidenceScore Full Formula (M5)
"""
import pytest
from app.schemas.decision_context import DecisionContext
from app.schemas.risk_gate import RiskGateDecision
from app.core.engines.decision.risk_gate import RiskGate
from app.core.engines.decision.confidence_engine import ConfidenceEngine
from app.schemas.evaluator_result import EvaluatorResult
from app.schemas.confidence_score import ConfidenceScore


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_context(**kwargs) -> DecisionContext:
    """Build a minimal DecisionContext for testing."""
    kwargs.setdefault("candidateId", "cand-001")
    kwargs.setdefault("missionId", "mission-001")
    kwargs.setdefault("candidateDirection", "BUY")
    kwargs.setdefault("spread", 0.5)
    kwargs.setdefault("newsImpact", "Low")
    kwargs.setdefault("dataAgeSeconds", 5)
    kwargs.setdefault("marketOpen", True)
    return DecisionContext.model_construct(**kwargs)


def _make_eval_result(name="A", score=80.0, weight=1.0, passed=True) -> EvaluatorResult:
    return EvaluatorResult.model_construct(
        name=name, score=score, weight=weight, passed=passed, evidence=[], warnings=[]
    )


# ─── RiskGate Tests ───────────────────────────────────────────────────────────

class TestRiskGatePass:
    def setup_method(self):
        self.gate = RiskGate()

    def test_clean_context_passes(self):
        ctx = _make_context()
        result = self.gate.evaluate(ctx)
        assert result.decision == RiskGateDecision.PASS
        assert len(result.vetoes) == 0
        assert len(result.warnings) == 0
        assert result.score == 0.0
        assert "PASS" in result.summary

    def test_score_zero_on_pass(self):
        ctx = _make_context(spread=0.3, newsImpact="Low", dataAgeSeconds=10)
        result = self.gate.evaluate(ctx)
        assert result.score == 0.0


class TestRiskGateVeto:
    def setup_method(self):
        self.gate = RiskGate()

    def _make_mock_risk(self, level: str):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.level = level
        r.riskLevel = level
        return r

    def _make_mock_validation(self, status: str):
        from unittest.mock import MagicMock
        v = MagicMock()
        v.status = status
        v.validationStatus = status
        return v

    def _make_mock_readiness(self, status: str):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.status = status
        return r

    def test_extreme_risk_causes_veto(self):
        ctx = _make_context(risk=self._make_mock_risk("EXTREME"))
        result = self.gate.evaluate(ctx)
        assert result.decision == RiskGateDecision.VETO
        assert any(v.indicator == "RISK_LEVEL" for v in result.vetoes)
        assert result.score >= 40.0

    def test_failed_validation_causes_veto(self):
        ctx = _make_context(validation=self._make_mock_validation("FAILED"))
        result = self.gate.evaluate(ctx)
        assert result.decision == RiskGateDecision.VETO
        assert any(v.indicator == "VALIDATION_STATUS" for v in result.vetoes)

    def test_blocked_execution_causes_veto(self):
        ctx = _make_context(readiness=self._make_mock_readiness("BLOCKED"))
        result = self.gate.evaluate(ctx)
        assert result.decision == RiskGateDecision.VETO
        assert any(v.indicator == "EXECUTION_STATUS" for v in result.vetoes)

    def test_multiple_vetoes_accumulate_score(self):
        ctx = _make_context(
            risk=self._make_mock_risk("EXTREME"),
            validation=self._make_mock_validation("FAILED"),
        )
        result = self.gate.evaluate(ctx)
        assert result.decision == RiskGateDecision.VETO
        assert len(result.vetoes) == 2
        assert result.score == 70.0  # 40 + 30

    def test_veto_summary_contains_veto(self):
        ctx = _make_context(risk=self._make_mock_risk("EXTREME"))
        result = self.gate.evaluate(ctx)
        assert "VETO" in result.summary


class TestRiskGateWarnings:
    def setup_method(self):
        self.gate = RiskGate()

    def _make_mock_risk(self, level: str):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.level = level
        r.riskLevel = level
        return r

    def test_high_news_causes_warning(self):
        ctx = _make_context(newsImpact="HIGH")
        result = self.gate.evaluate(ctx)
        assert result.decision == RiskGateDecision.WARN
        assert any(w.indicator == "NEWS_IMPACT" for w in result.warnings)

    def test_high_spread_causes_warning(self):
        ctx = _make_context(spread=5.0)
        result = self.gate.evaluate(ctx)
        assert result.decision == RiskGateDecision.WARN
        assert any(w.indicator == "SPREAD" for w in result.warnings)

    def test_stale_data_causes_warning(self):
        ctx = _make_context(dataAgeSeconds=120)
        result = self.gate.evaluate(ctx)
        assert result.decision == RiskGateDecision.WARN
        assert any(w.indicator == "DATA_AGE" for w in result.warnings)

    def test_medium_risk_causes_warning(self):
        ctx = _make_context(risk=self._make_mock_risk("MEDIUM"))
        result = self.gate.evaluate(ctx)
        assert result.decision == RiskGateDecision.WARN
        assert any(w.indicator == "RISK_LEVEL" for w in result.warnings)

    def test_score_capped_at_100(self):
        ctx = _make_context(
            risk=self._make_mock_risk("EXTREME"),
            newsImpact="HIGH",
            spread=10.0,
            dataAgeSeconds=300,
        )
        result = self.gate.evaluate(ctx)
        assert result.score <= 100.0


# ─── ConfidenceScore Full Formula Tests (M5) ─────────────────────────────────

class TestConfidenceScoreGrade:
    def test_grade_a_plus(self):
        assert ConfidenceScore.grade_from_score(95.0) == "A+"

    def test_grade_a(self):
        assert ConfidenceScore.grade_from_score(85.0) == "A"

    def test_grade_b(self):
        assert ConfidenceScore.grade_from_score(75.0) == "B"

    def test_grade_c(self):
        assert ConfidenceScore.grade_from_score(62.0) == "C"

    def test_grade_d(self):
        assert ConfidenceScore.grade_from_score(48.0) == "D"

    def test_grade_f(self):
        assert ConfidenceScore.grade_from_score(30.0) == "F"


class TestConfidenceEngineFullFormula:
    def setup_method(self):
        self.engine = ConfidenceEngine()

    def _make_pass_gate(self, score: float = 0.0):
        from app.schemas.risk_gate import RiskGateResult, RiskGateDecision
        return RiskGateResult(decision=RiskGateDecision.PASS, score=score, summary="PASS")

    def _make_validation(self, val_score: float):
        from app.schemas.validation_result import ValidationResult
        return ValidationResult.model_construct(validationScore=val_score)

    def _make_readiness(self, ready_score: float):
        from app.schemas.execution_readiness import ExecutionReadiness
        return ExecutionReadiness.model_construct(overallReadinessScore=ready_score)

    def test_perfect_signal_no_risk(self):
        """100% evaluators, 0 risk → should score near 100+bonuses."""
        evals = [_make_eval_result("A", 100.0, 1.0)]
        gate = self._make_pass_gate(score=0.0)
        val = self._make_validation(100.0)
        ready = self._make_readiness(100.0)
        score = self.engine.calculate_full(evals, gate, val, ready)
        # raw=100, penalty=0, val_bonus=10, ready_bonus=5 → clamp(115, 0, 100) = 100
        assert score.overall == 100.0
        assert score.grade == "A+"

    def test_risk_penalty_reduces_score(self):
        """80 raw, risk score=50 → penalty=10 → final=70."""
        evals = [_make_eval_result("A", 80.0, 1.0)]
        gate = self._make_pass_gate(score=50.0)  # penalty = 50 * 0.20 = 10
        score = self.engine.calculate_full(evals, gate)
        assert score.evaluatorContribution == pytest.approx(80.0, abs=0.1)
        assert score.riskPenalty == pytest.approx(10.0, abs=0.1)
        assert score.overall == pytest.approx(70.0, abs=0.1)

    def test_validation_bonus_added(self):
        """60 raw + val_score=80 → bonus=8 → final=68."""
        evals = [_make_eval_result("A", 60.0, 1.0)]
        gate = self._make_pass_gate(score=0.0)
        val = self._make_validation(80.0)  # bonus = 80 * 0.10 = 8
        score = self.engine.calculate_full(evals, gate, validation=val)
        assert score.validationBonus == pytest.approx(8.0, abs=0.1)
        assert score.overall == pytest.approx(68.0, abs=0.1)

    def test_readiness_bonus_added(self):
        """60 raw + ready_score=100 → bonus=5 → final=65."""
        evals = [_make_eval_result("A", 60.0, 1.0)]
        gate = self._make_pass_gate(score=0.0)
        ready = self._make_readiness(100.0)  # bonus = 100 * 0.05 = 5
        score = self.engine.calculate_full(evals, gate, readiness=ready)
        assert score.readinessBonus == pytest.approx(5.0, abs=0.1)
        assert score.overall == pytest.approx(65.0, abs=0.1)

    def test_clamp_prevents_below_zero(self):
        evals = [_make_eval_result("A", 0.0, 1.0)]
        gate = self._make_pass_gate(score=100.0)  # max penalty = 20
        score = self.engine.calculate_full(evals, gate)
        assert score.overall >= 0.0

    def test_breakdown_populated(self):
        evals = [
            _make_eval_result("Trend", 90.0, 0.25),
            _make_eval_result("Momentum", 70.0, 0.15),
        ]
        gate = self._make_pass_gate(score=0.0)
        score = self.engine.calculate_full(evals, gate)
        assert "Trend" in score.breakdown
        assert "Momentum" in score.breakdown

    def test_grade_reflects_final_score(self):
        evals = [_make_eval_result("A", 50.0, 1.0)]
        gate = self._make_pass_gate(score=0.0)
        score = self.engine.calculate_full(evals, gate)
        assert score.grade == ConfidenceScore.grade_from_score(score.overall)
