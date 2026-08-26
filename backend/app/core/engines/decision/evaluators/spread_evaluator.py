"""
Falcon Phase 7 — Spread Evaluator
"""
from app.schemas.decision_context import DecisionContext
from app.schemas.evaluator_result import EvaluatorResult, DecisionEvidence, EvidenceImpact, EvidenceStatus
from app.core.engines.decision.evaluators.__init__ import BaseEvaluator


class SpreadEvaluator(BaseEvaluator):
    """
    Evaluates spread conditions.
    """
    
    @property
    def name(self) -> str:
        return "SpreadEvaluator"
        
    @property
    def weight(self) -> float:
        return 0.05

    def evaluate(self, context: DecisionContext) -> EvaluatorResult:
        evidence = []
        warnings = []
        
        spread = context.spread
        
        # A simple check: if spread is unusually high, penalize.
        # In a real implementation, this would compare against a symbol-specific average or max.
        max_acceptable_spread = 2.0  # Just a placeholder arbitrary threshold
        
        if spread <= 0:
            evidence.append(DecisionEvidence(
                indicator="SPREAD",
                observedValue="0.0",
                weight=0.0,
                impact=EvidenceImpact.NEUTRAL,
                status=EvidenceStatus.WARN,
                explanation="Spread data is unavailable or zero.",
                category="SPREAD"
            ))
            score = 50.0
            passed = True
        elif spread > max_acceptable_spread:
            evidence.append(DecisionEvidence(
                indicator="SPREAD",
                observedValue=f"{spread:.1f}",
                weight=1.0,
                impact=EvidenceImpact.CONTRADICTING,
                status=EvidenceStatus.FAIL,
                explanation=f"Spread ({spread:.1f}) is exceptionally high.",
                category="SPREAD"
            ))
            score = 0.0
            passed = False
            warnings.append(f"High spread detected: {spread:.1f}")
        else:
            evidence.append(DecisionEvidence(
                indicator="SPREAD",
                observedValue=f"{spread:.1f}",
                weight=1.0,
                impact=EvidenceImpact.SUPPORTING,
                status=EvidenceStatus.PASS,
                explanation=f"Spread ({spread:.1f}) is within acceptable limits.",
                category="SPREAD"
            ))
            score = 100.0
            passed = True
            
        return EvaluatorResult(
            name=self.name,
            passed=passed,
            score=score,
            weight=self.weight,
            evidence=evidence,
            warnings=warnings
        )
