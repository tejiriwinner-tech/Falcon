"""
Falcon Phase 7 — Confidence Engine (M4 / M5)

M4: Dynamic weighted confidence from evaluators + regime modifier.
M5: Full formula adding risk penalty, validation bonus, readiness bonus
    and returning a structured ConfidenceScore with letter grade.

Design:
  - Pure function: same inputs → same output.
  - No side effects, no I/O.

Usage:
    engine = ConfidenceEngine()

    # M4 simple path (used by DecisionEngine.generate_decisions)
    result = engine.calculate(evaluator_results, regime_report)

    # M5 full path (used by DecisionGenerator)
    score = engine.calculate_full(evaluator_results, risk_gate, validation, readiness, regime_report)
"""
from __future__ import annotations

import math
from typing import List, Optional, TYPE_CHECKING

from app.schemas.evaluator_result import EvaluatorResult
from app.schemas.market_regime import MarketRegimeReport, MarketRegime, RegimeStrength
from app.schemas.confidence_score import ConfidenceScore

if TYPE_CHECKING:
    from app.schemas.risk_gate import RiskGateResult
    from app.schemas.validation_result import ValidationResult
    from app.schemas.execution_readiness import ExecutionReadiness


class ConfidenceResult:
    """Immutable result of confidence calculation."""

    def __init__(
        self,
        raw_score: float,
        regime_modifier: float,
        final_score: float,
        breakdown: dict,
    ):
        self.raw_score = round(raw_score, 2)
        self.regime_modifier = round(regime_modifier, 4)
        self.final_score = round(final_score, 2)
        self.breakdown = breakdown

    def __repr__(self) -> str:
        return (
            f"ConfidenceResult(raw={self.raw_score}, "
            f"modifier={self.regime_modifier:+.4f}, "
            f"final={self.final_score})"
        )


# Regime modifiers: how much each regime type adjusts confidence
_REGIME_MODIFIERS: dict[str, float] = {
    MarketRegime.TRENDING_BULLISH.value: +0.05,   # +5%
    MarketRegime.TRENDING_BEARISH.value: +0.05,   # +5%
    MarketRegime.BREAKOUT.value: +0.08,           # +8%
    MarketRegime.REVERSAL.value: +0.03,           # +3%
    MarketRegime.RANGING.value: -0.10,            # −10%
    MarketRegime.HIGH_VOLATILITY.value: -0.05,    # −5%
    MarketRegime.UNCERTAIN.value: -0.15,          # −15%
}

# Regime strength multipliers applied to the modifier
_STRENGTH_MULTIPLIERS: dict[str, float] = {
    RegimeStrength.STRONG.value: 1.5,
    RegimeStrength.MODERATE.value: 1.0,
    RegimeStrength.WEAK.value: 0.5,
}


class ConfidenceEngine:
    """
    Dynamically calculates trading decision confidence from evaluator results.

    Algorithm:
        1. Weighted sum:  sum(e.score * e.weight) / sum(e.weight)
        2. Regime modifier: regime_base_modifier * strength_multiplier
        3. Final: clamp(raw_score * (1 + modifier), 0, 100)
    """

    def calculate(
        self,
        evaluator_results: List[EvaluatorResult],
        regime_report: Optional[MarketRegimeReport] = None,
    ) -> ConfidenceResult:
        """
        Calculate final confidence from evaluator results + optional regime context.

        Args:
            evaluator_results: Ordered list of EvaluatorResult from the evaluation layer.
            regime_report:     The dominant MarketRegimeReport from the pipeline (optional).

        Returns:
            ConfidenceResult with raw_score, regime_modifier, final_score, and breakdown dict.
        """
        if not evaluator_results:
            return ConfidenceResult(
                raw_score=0.0,
                regime_modifier=0.0,
                final_score=0.0,
                breakdown={},
            )

        # ── Step 1: Weighted Average ──────────────────────────────────────────
        total_weight = sum(e.weight for e in evaluator_results)
        if total_weight == 0.0:
            return ConfidenceResult(
                raw_score=0.0,
                regime_modifier=0.0,
                final_score=0.0,
                breakdown={},
            )

        weighted_sum = sum(e.score * e.weight for e in evaluator_results)
        raw_score = weighted_sum / total_weight

        breakdown = {
            e.name: {
                "score": round(e.score, 2),
                "weight": round(e.weight, 4),
                "contribution": round((e.score * e.weight) / total_weight, 2),
                "passed": e.passed,
            }
            for e in evaluator_results
        }

        # ── Step 2: Regime Modifier ───────────────────────────────────────────
        regime_modifier = 0.0
        if regime_report is not None:
            base_mod = _REGIME_MODIFIERS.get(regime_report.regime.value, 0.0)
            strength_mult = _STRENGTH_MULTIPLIERS.get(
                regime_report.strength.value, 1.0
            )
            regime_modifier = base_mod * strength_mult

        # ── Step 3: Apply Modifier & Clamp ───────────────────────────────────
        adjusted = raw_score * (1.0 + regime_modifier)
        final_score = max(0.0, min(100.0, adjusted))

        return ConfidenceResult(
            raw_score=raw_score,
            regime_modifier=regime_modifier,
            final_score=final_score,
            breakdown=breakdown,
        )

    def calculate_from_scores(
        self,
        candidate_confidence: float,
        validation_score: float,
        risk_confidence: float,
        execution_score: float,
        weights: Optional[dict] = None,
    ) -> float:
        """
        Legacy-compatible convenience method. Replaces the hardcoded
        weighted formula in decision_engine.py.

        Default weights match original implicit weighting in DecisionEngine v1.
        """
        default_weights = weights or {
            "candidate": 0.30,
            "validation": 0.25,
            "risk": 0.25,
            "execution": 0.20,
        }
        w_c = default_weights.get("candidate", 0.30)
        w_v = default_weights.get("validation", 0.25)
        w_r = default_weights.get("risk", 0.25)
        w_e = default_weights.get("execution", 0.20)

        total_w = w_c + w_v + w_r + w_e
        if total_w == 0:
            return 0.0

        raw = (
            candidate_confidence * w_c
            + validation_score * w_v
            + risk_confidence * w_r
            + execution_score * w_e
        ) / total_w

        return round(max(0.0, min(100.0, raw)), 2)

    def calculate_full(
        self,
        evaluator_results: List[EvaluatorResult],
        risk_gate: "RiskGateResult",
        validation: Optional["ValidationResult"] = None,
        readiness: Optional["ExecutionReadiness"] = None,
        regime_report: Optional[MarketRegimeReport] = None,
    ) -> ConfidenceScore:
        """
        M5 full formula — returns a structured ConfidenceScore.

        Formula (from implementation_plan.md):
            raw           = Σ(evaluator.score × evaluator.weight)       [0–100]
            risk_penalty  = risk_gate.score × 0.20                      [0–20]
            val_bonus     = validation.validationScore × 0.10           [0–10]
            ready_bonus   = readiness.overallReadinessScore × 0.05      [0–5]
            regime_mod    = raw × regime_modifier                       [varies]
            final         = clamp(raw - risk_penalty + val_bonus + ready_bonus + regime_mod, 0, 100)
        """
        # Step 1: evaluator weighted average
        base_result = self.calculate(evaluator_results, regime_report=None)
        raw = base_result.raw_score
        evaluator_breakdown = {k: v["contribution"] for k, v in base_result.breakdown.items()}

        # Step 2: regime modifier on the raw score
        regime_modifier = 0.0
        if regime_report is not None:
            base_mod = _REGIME_MODIFIERS.get(regime_report.regime.value, 0.0)
            strength_mult = _STRENGTH_MULTIPLIERS.get(regime_report.strength.value, 1.0)
            regime_modifier = base_mod * strength_mult
        regime_adj = raw * regime_modifier

        # Step 3: risk penalty
        risk_penalty = round(risk_gate.score * 0.20, 2)

        # Step 4: validation bonus
        val_score = 0.0
        if validation is not None:
            val_score = float(getattr(validation, "validationScore", 0.0) or 0.0)
        val_bonus = round(val_score * 0.10, 2)

        # Step 5: readiness bonus
        ready_score = 0.0
        if readiness is not None:
            ready_score = float(getattr(readiness, "overallReadinessScore", 0.0) or 0.0)
        ready_bonus = round(ready_score * 0.05, 2)

        # Step 6: combine and clamp
        final = max(0.0, min(100.0, raw - risk_penalty + val_bonus + ready_bonus + regime_adj))
        final = round(final, 2)

        return ConfidenceScore(
            overall=final,
            evaluatorContribution=round(raw, 2),
            riskPenalty=risk_penalty,
            validationBonus=val_bonus,
            readinessBonus=ready_bonus,
            regimeModifier=round(regime_modifier, 4),
            breakdown=evaluator_breakdown,
            grade=ConfidenceScore.grade_from_score(final),
        )
