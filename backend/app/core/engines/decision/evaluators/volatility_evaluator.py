"""
Falcon Phase 7 — Volatility Evaluator
"""
from app.schemas.decision_context import DecisionContext
from app.schemas.evaluator_result import EvaluatorResult, DecisionEvidence, EvidenceImpact, EvidenceStatus
from app.core.engines.decision.evaluators.__init__ import BaseEvaluator


class VolatilityEvaluator(BaseEvaluator):
    """
    Evaluates market volatility.
    """
    
    @property
    def name(self) -> str:
        return "VolatilityEvaluator"
        
    @property
    def weight(self) -> float:
        return 0.10

    def evaluate(self, context: DecisionContext) -> EvaluatorResult:
        evidence = []
        warnings = []
        
        volatility = context.volatility.upper()
        
        if volatility == "HIGH":
            evidence.append(DecisionEvidence(
                indicator="VOLATILITY",
                observedValue="HIGH",
                weight=0.8,
                impact=EvidenceImpact.NEUTRAL,
                status=EvidenceStatus.WARN,
                explanation="Market volatility is high. Exercise caution with position sizing.",
                category="VOLATILITY"
            ))
            score = 60.0
            passed = True
        elif volatility == "LOW":
            evidence.append(DecisionEvidence(
                indicator="VOLATILITY",
                observedValue="LOW",
                weight=1.0,
                impact=EvidenceImpact.CONTRADICTING,
                status=EvidenceStatus.FAIL,
                explanation="Market volatility is too low for most breakout strategies.",
                category="VOLATILITY"
            ))
            score = 20.0
            passed = False
            warnings.append("Low volatility conditions.")
        else:
            evidence.append(DecisionEvidence(
                indicator="VOLATILITY",
                observedValue="MODERATE",
                weight=1.0,
                impact=EvidenceImpact.SUPPORTING,
                status=EvidenceStatus.PASS,
                explanation="Market volatility is moderate and suitable for trading.",
                category="VOLATILITY"
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
