"""
Falcon Phase 7 — Reasoning Generator (M7)

Produces a deterministic, human-readable explanation of any trading decision.
Pure function — no side effects, no external calls.

The reasoning is assembled from:
  - The final decision and confidence grade
  - RiskGate warnings and vetoes
  - Top supporting and blocking EvaluatorResults
  - Market regime context
  - Strategy evaluation match (if available)
"""
from typing import List, Optional

from app.schemas.evaluator_result import EvaluatorResult
from app.schemas.risk_gate import RiskGateResult, RiskGateDecision
from app.schemas.strategy_evaluation import StrategyEvaluationResult
from app.schemas.confidence_score import ConfidenceScore
from app.schemas.decision_enums import DecisionRecommendation
from app.schemas.market_regime import MarketRegimeReport


class ReasoningGenerator:
    """
    Builds a structured, explainable reasoning narrative for a decision.

    Design rules:
      - Deterministic: identical inputs → identical output
      - No LLM, no external calls
      - Plain English sentences, suitable for the Falcon AI Intelligence panel
    """

    def generate(
        self,
        recommendation: DecisionRecommendation,
        confidence: ConfidenceScore,
        evaluator_results: List[EvaluatorResult],
        risk_gate: RiskGateResult,
        strategy_result: Optional[StrategyEvaluationResult] = None,
        regime_report: Optional[MarketRegimeReport] = None,
    ) -> str:
        """
        Produce a human-readable reasoning string.

        Args:
            recommendation:    The final decision (BUY, SELL, WAIT, etc.)
            confidence:        Full ConfidenceScore with grade and breakdown
            evaluator_results: All EvaluatorResults from the technical pipeline
            risk_gate:         The RiskGate outcome (PASS/WARN/VETO)
            strategy_result:   Optional best-matching strategy evaluation
            regime_report:     Optional current market regime

        Returns:
            A multi-sentence reasoning string.
        """
        lines: List[str] = []

        # ── Headline ────────────────────────────────────────────────────────
        action_map = {
            DecisionRecommendation.BUY: "BUY signal identified",
            DecisionRecommendation.SELL: "SELL signal identified",
            DecisionRecommendation.WAIT: "WAIT — conditions not yet optimal",
            DecisionRecommendation.MONITOR: "MONITOR — setup developing but not confirmed",
            DecisionRecommendation.NO_TRADE: "NO TRADE — pipeline has blocked this setup",
            DecisionRecommendation.AVOID: "AVOID — multiple high-severity risk factors detected",
        }
        headline = action_map.get(recommendation, str(recommendation))
        lines.append(
            f"{headline}. "
            f"Confidence: {confidence.overall:.1f}/100 (Grade {confidence.grade})."
        )

        # ── Market Regime ────────────────────────────────────────────────────
        if regime_report:
            regime_name = regime_report.regime.value.replace("_", " ").title()
            lines.append(
                f"Market regime is currently {regime_name} "
                f"({regime_report.strength.value.lower()} strength)."
            )

        # ── Technical Evaluators ─────────────────────────────────────────────
        passed_evals = [e for e in evaluator_results if e.passed]
        failed_evals = [e for e in evaluator_results if not e.passed]

        if passed_evals:
            top_passed = sorted(passed_evals, key=lambda e: e.score, reverse=True)[:3]
            names = ", ".join(e.name for e in top_passed)
            lines.append(f"Supporting signals: {names}.")

        if failed_evals:
            top_failed = sorted(failed_evals, key=lambda e: e.score)[:3]
            names = ", ".join(e.name for e in top_failed)
            lines.append(f"Conflicting signals: {names}.")

        # ── Risk Gate ────────────────────────────────────────────────────────
        if risk_gate.decision == RiskGateDecision.VETO:
            veto_names = ", ".join(v.indicator for v in risk_gate.vetoes)
            lines.append(
                f"Risk Gate VETOED this trade due to: {veto_names}. "
                f"Risk score: {risk_gate.score:.0f}/100."
            )
        elif risk_gate.decision == RiskGateDecision.WARN:
            warn_names = ", ".join(w.indicator for w in risk_gate.warnings)
            lines.append(
                f"Risk Gate issued warnings on: {warn_names}. "
                f"Proceed with caution."
            )
        else:
            lines.append("Risk Gate: PASS — no critical risk factors detected.")

        # ── Strategy ─────────────────────────────────────────────────────────
        if strategy_result:
            if strategy_result.passed:
                lines.append(
                    f"Strategy '{strategy_result.strategyName}' confirmed "
                    f"(score: {strategy_result.score:.0f}/100)."
                )
            else:
                lines.append(
                    f"Strategy '{strategy_result.strategyName}' did not fully qualify "
                    f"(score: {strategy_result.score:.0f}/100, "
                    f"failed rules: {', '.join(strategy_result.failedRules)})."
                )

        # ── Confidence Breakdown ─────────────────────────────────────────────
        lines.append(
            f"Confidence breakdown — Evaluators: {confidence.evaluatorContribution:.1f}, "
            f"Risk penalty: -{confidence.riskPenalty:.1f}, "
            f"Validation bonus: +{confidence.validationBonus:.1f}, "
            f"Readiness bonus: +{confidence.readinessBonus:.1f}."
        )

        return " ".join(lines)
