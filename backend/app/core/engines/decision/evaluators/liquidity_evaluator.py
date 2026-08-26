"""
Falcon Phase 7 — Liquidity Evaluator
"""
from app.schemas.decision_context import DecisionContext
from app.schemas.evaluator_result import EvaluatorResult, DecisionEvidence, EvidenceImpact, EvidenceStatus
from app.core.engines.decision.evaluators.__init__ import BaseEvaluator


class LiquidityEvaluator(BaseEvaluator):
    """
    Evaluates liquidity sweeps and order block proximity.
    """
    
    @property
    def name(self) -> str:
        return "LiquidityEvaluator"
        
    @property
    def weight(self) -> float:
        return 0.15

    def evaluate(self, context: DecisionContext) -> EvaluatorResult:
        # Default placeholder similar to structure until explicit liquidity data is in MarketState
        evidence = [DecisionEvidence(
            indicator="LIQUIDITY_ZONES",
            observedValue="UNKNOWN",
            weight=0.5,
            impact=EvidenceImpact.NEUTRAL,
            status=EvidenceStatus.WARN,
            explanation="Liquidity sweep and order block data not fully available in context.",
            category="LIQUIDITY"
        )]
        
        return EvaluatorResult(
            name=self.name,
            passed=True,
            score=50.0,
            weight=self.weight,
            evidence=evidence,
            warnings=[]
        )
