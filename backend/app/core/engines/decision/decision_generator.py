"""
Falcon Phase 7 — Decision Generator (M7)

The Decision Generator is the final integration stage of the Decision Intelligence Engine.

It wires together:
  1. DecisionContext          → fully built by ContextBuilder
  2. Technical Evaluators     → 7 independent evaluators run concurrently
  3. RiskGate                 → veto / warn / pass gate
  4. ConfidenceEngine         → weighted confidence formula
  5. ReasoningGenerator       → human-readable explanation
  6. Strategy Evaluator       → optional strategy match

And produces a single GeneratedDecision.

Design rules:
  - Pure function: generate() has no side effects and makes no network calls.
  - Deterministic: identical inputs → identical outputs.
  - All errors are caught and produce a safe NO_TRADE result with reasoning.
  - Does NOT mutate the context.
"""
import logging
from typing import List, Optional

from app.schemas.decision_context import DecisionContext
from app.schemas.evaluator_result import EvaluatorResult
from app.schemas.generated_decision import GeneratedDecision
from app.schemas.decision_enums import DecisionRecommendation
from app.schemas.risk_gate import RiskGateDecision

from app.core.engines.decision.risk_gate import RiskGate
from app.core.engines.decision.confidence_engine import ConfidenceEngine
from app.core.engines.decision.reasoning_generator import ReasoningGenerator
from app.core.engines.decision.evaluators import BaseEvaluator
from app.core.engines.decision.evaluators.trend_evaluator import TrendEvaluator
from app.core.engines.decision.evaluators.structure_evaluator import StructureEvaluator
from app.core.engines.decision.evaluators.momentum_evaluator import MomentumEvaluator
from app.core.engines.decision.evaluators.liquidity_evaluator import LiquidityEvaluator
from app.core.engines.decision.evaluators.session_evaluator import SessionEvaluator
from app.core.engines.decision.evaluators.spread_evaluator import SpreadEvaluator
from app.core.engines.decision.evaluators.volatility_evaluator import VolatilityEvaluator
from app.core.engines.decision.strategy_evaluators.base_strategy_evaluator import BaseStrategyEvaluator

logger = logging.getLogger(__name__)

# Minimum overall confidence to recommend an active trade (BUY or SELL)
_ACTIVE_TRADE_THRESHOLD = 55.0
# If risk gate issues warnings and confidence is below this, degrade to MONITOR
_WARN_CONFIDENCE_THRESHOLD = 65.0


def _build_default_evaluators() -> List[BaseEvaluator]:
    """Return the standard set of 7 technical evaluators."""
    return [
        TrendEvaluator(),
        StructureEvaluator(),
        MomentumEvaluator(),
        LiquidityEvaluator(),
        SessionEvaluator(),
        SpreadEvaluator(),
        VolatilityEvaluator(),
    ]


class DecisionGenerator:
    """
    Orchestrates the full Decision Intelligence pipeline and produces
    a GeneratedDecision from any DecisionContext.
    """

    def __init__(
        self,
        evaluators: Optional[List[BaseEvaluator]] = None,
        strategy_evaluator: Optional[BaseStrategyEvaluator] = None,
    ):
        self._evaluators: List[BaseEvaluator] = evaluators or _build_default_evaluators()
        self._risk_gate = RiskGate()
        self._confidence_engine = ConfidenceEngine()
        self._reasoning_generator = ReasoningGenerator()
        self._strategy_evaluator = strategy_evaluator

    # ── Public API ──────────────────────────────────────────────────────────

    def generate(self, context: DecisionContext) -> GeneratedDecision:
        """
        Run the full Decision Intelligence pipeline and produce a GeneratedDecision.

        Pipeline:
          1. Run all technical evaluators
          2. Evaluate risk gate
          3. Evaluate strategy (optional)
          4. Calculate confidence
          5. Map to final recommendation
          6. Generate reasoning

        Args:
            context: A fully-built DecisionContext

        Returns:
            GeneratedDecision with recommendation, confidence, and reasoning.
        """
        try:
            return self._generate_internal(context)
        except Exception as exc:
            logger.exception("DecisionGenerator failed for candidate %s", context.candidateId)
            return self._safe_no_trade(context, reason=str(exc))

    # ── Internal Pipeline ────────────────────────────────────────────────────

    def _generate_internal(self, context: DecisionContext) -> GeneratedDecision:
        # Step 1: Run all technical evaluators
        eval_results: List[EvaluatorResult] = []
        for evaluator in self._evaluators:
            try:
                result = evaluator.evaluate(context)
                eval_results.append(result)
            except Exception as exc:
                logger.warning("Evaluator %s failed: %s", evaluator.name, exc)
                # Produce a neutral failing result rather than crashing
                eval_results.append(EvaluatorResult.model_construct(
                    name=evaluator.name,
                    score=0.0,
                    weight=evaluator.weight,
                    passed=False,
                    evidence=[],
                    warnings=[f"Evaluator error: {exc}"],
                ))

        # Step 2: Risk Gate
        risk_gate_result = self._risk_gate.evaluate(context)

        # Step 3: Optional strategy evaluation
        strategy_result = None
        if self._strategy_evaluator:
            try:
                strategy_result = self._strategy_evaluator.evaluate(context)
            except Exception as exc:
                logger.warning("StrategyEvaluator failed: %s", exc)

        # Step 4: Calculate confidence
        confidence = self._confidence_engine.calculate_full(
            evaluator_results=eval_results,
            risk_gate=risk_gate_result,
            validation=context.validation,
            readiness=context.readiness,
        )

        # Step 5: Map to recommendation
        recommendation, warnings = self._map_recommendation(
            context, eval_results, risk_gate_result, confidence.overall, strategy_result
        )

        # Step 6: Generate reasoning
        reasoning = self._reasoning_generator.generate(
            recommendation=recommendation,
            confidence=confidence,
            evaluator_results=eval_results,
            risk_gate=risk_gate_result,
            strategy_result=strategy_result,
            regime_report=context.regimeReport,
        )

        return GeneratedDecision(
            recommendation=recommendation,
            confidence=confidence,
            reasoning=reasoning,
            warnings=warnings,
        )

    def _map_recommendation(
        self,
        context: DecisionContext,
        eval_results: List[EvaluatorResult],
        risk_gate_result,
        overall_confidence: float,
        strategy_result,
    ):
        """
        Deterministically map pipeline results to a DecisionRecommendation.

        Priority order (top-to-bottom wins):
          1. VETO            → NO_TRADE (insufficient data: also NO_TRADE)
          2. Low confidence  → AVOID (< threshold with multiple failing evaluators)
          3. WARN + low conf → MONITOR
          4. Direction       → BUY or SELL
          5. Fallback        → WAIT
        """
        warnings: List[str] = []

        # Insufficient data
        if not eval_results:
            return DecisionRecommendation.NO_TRADE, ["No evaluator results available."]

        # Risk VETO → always NO_TRADE
        if risk_gate_result.decision == RiskGateDecision.VETO:
            warnings.append(risk_gate_result.summary)
            return DecisionRecommendation.NO_TRADE, warnings

        # Collect risk gate warnings
        for w in risk_gate_result.warnings:
            warnings.append(w.explanation)

        # High-confidence negative → AVOID
        failed_count = sum(1 for e in eval_results if not e.passed)
        total_count = len(eval_results)
        fail_ratio = failed_count / total_count if total_count else 1.0

        if overall_confidence < _ACTIVE_TRADE_THRESHOLD and fail_ratio > 0.5:
            return DecisionRecommendation.AVOID, warnings

        # WARN + low confidence → MONITOR
        if (
            risk_gate_result.decision == RiskGateDecision.WARN
            and overall_confidence < _WARN_CONFIDENCE_THRESHOLD
        ):
            return DecisionRecommendation.MONITOR, warnings

        # Not enough confidence for active trade → WAIT
        if overall_confidence < _ACTIVE_TRADE_THRESHOLD:
            return DecisionRecommendation.WAIT, warnings

        # Active trade: resolve direction from context
        direction = "BUY"
        if context.candidate:
            raw_dir = getattr(context.candidate.direction, "name", str(context.candidate.direction)).upper()
            if "SELL" in raw_dir or "SHORT" in raw_dir:
                direction = "SELL"

        if direction == "SELL":
            return DecisionRecommendation.SELL, warnings
        return DecisionRecommendation.BUY, warnings

    def _safe_no_trade(self, context: DecisionContext, reason: str) -> GeneratedDecision:
        """Return a safe NO_TRADE decision when the pipeline crashes."""
        from app.schemas.confidence_score import ConfidenceScore
        safe_confidence = ConfidenceScore(
            overall=0.0,
            evaluatorContribution=0.0,
            riskPenalty=0.0,
            validationBonus=0.0,
            readinessBonus=0.0,
            grade="F",
        )
        return GeneratedDecision(
            recommendation=DecisionRecommendation.NO_TRADE,
            confidence=safe_confidence,
            reasoning=f"Decision pipeline failed: {reason}. Defaulting to NO_TRADE for safety.",
            warnings=[f"Pipeline error: {reason}"],
        )
