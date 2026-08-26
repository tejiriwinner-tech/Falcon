"""
Falcon Phase 7 — Structure Evaluator
"""
from app.schemas.decision_context import DecisionContext
from app.schemas.evaluator_result import EvaluatorResult, DecisionEvidence, EvidenceImpact, EvidenceStatus
from app.core.engines.decision.evaluators.__init__ import BaseEvaluator


class StructureEvaluator(BaseEvaluator):
    """
    Evaluates market structure (BOS/CHoCH) relative to the candidate direction.
    """
    
    @property
    def name(self) -> str:
        return "StructureEvaluator"
        
    @property
    def weight(self) -> float:
        return 0.20

    def evaluate(self, context: DecisionContext) -> EvaluatorResult:
        evidence = []
        warnings = []
        
        # Currently, context doesn't expose detailed BOS/CHoCH structures 
        # (they are buried in indicator responses if at all in MarketState).
        # We will use candidate's own confidence as a proxy or just default to neutral 
        # until MarketState provides `structure` explicitly, but we can look for it in marketState.
        
        # Let's check if the candidate has any structure-related confidence
        candidate_dir = context.candidateDirection.upper()
        if candidate_dir not in ("BUY", "SELL"):
            return EvaluatorResult(
                name=self.name,
                passed=False,
                score=0.0,
                weight=self.weight,
                evidence=[],
                warnings=[f"Cannot evaluate structure for non-directional candidate: {candidate_dir}"]
            )

        # Basic default behavior
        evidence.append(DecisionEvidence(
            indicator="MARKET_STRUCTURE",
            observedValue="UNKNOWN",
            weight=0.5,
            impact=EvidenceImpact.NEUTRAL,
            status=EvidenceStatus.WARN,
            explanation="Detailed market structure data (BOS/CHoCH) not fully available in context.",
            category="STRUCTURE"
        ))
        
        return EvaluatorResult(
            name=self.name,
            passed=True,  # Default to true so it doesn't block
            score=50.0,   # Neutral score
            weight=self.weight,
            evidence=evidence,
            warnings=warnings
        )
