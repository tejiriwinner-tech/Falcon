"""
Falcon Phase 7 — Momentum Evaluator
"""
from app.schemas.decision_context import DecisionContext
from app.schemas.evaluator_result import EvaluatorResult, DecisionEvidence, EvidenceImpact, EvidenceStatus
from app.core.engines.decision.evaluators.__init__ import BaseEvaluator


class MomentumEvaluator(BaseEvaluator):
    """
    Evaluates market momentum (e.g., RSI, MACD proxy via candidate confidence).
    """
    
    @property
    def name(self) -> str:
        return "MomentumEvaluator"
        
    @property
    def weight(self) -> float:
        return 0.15

    def evaluate(self, context: DecisionContext) -> EvaluatorResult:
        evidence = []
        warnings = []
        
        candidate_dir = context.candidateDirection.upper()
        if candidate_dir not in ("BUY", "SELL"):
            return EvaluatorResult(
                name=self.name,
                passed=False,
                score=0.0,
                weight=self.weight,
                evidence=[],
                warnings=[f"Cannot evaluate momentum for non-directional candidate: {candidate_dir}"]
            )

        # Using candidate's confidence as a proxy for momentum strength if explicit indicators are missing
        # In the future, this should pull RSI/MACD from context.marketState.indicators if available
        conf = context.candidateConfidence
        
        if conf >= 80:
            evidence.append(DecisionEvidence(
                indicator="MOMENTUM_STRENGTH",
                observedValue=f"HIGH ({conf:.1f})",
                weight=1.0,
                impact=EvidenceImpact.SUPPORTING,
                status=EvidenceStatus.PASS,
                explanation=f"Strong momentum aligns with the {candidate_dir} direction.",
                category="MOMENTUM"
            ))
            score = 100.0
            passed = True
        elif conf >= 60:
            evidence.append(DecisionEvidence(
                indicator="MOMENTUM_STRENGTH",
                observedValue=f"MODERATE ({conf:.1f})",
                weight=0.8,
                impact=EvidenceImpact.SUPPORTING,
                status=EvidenceStatus.PASS,
                explanation=f"Moderate momentum supports the {candidate_dir} direction.",
                category="MOMENTUM"
            ))
            score = 75.0
            passed = True
        elif conf >= 40:
            evidence.append(DecisionEvidence(
                indicator="MOMENTUM_STRENGTH",
                observedValue=f"WEAK ({conf:.1f})",
                weight=0.5,
                impact=EvidenceImpact.NEUTRAL,
                status=EvidenceStatus.WARN,
                explanation="Momentum is weak, offering little directional support.",
                category="MOMENTUM"
            ))
            score = 40.0
            passed = False
        else:
            evidence.append(DecisionEvidence(
                indicator="MOMENTUM_STRENGTH",
                observedValue=f"POOR ({conf:.1f})",
                weight=1.0,
                impact=EvidenceImpact.CONTRADICTING,
                status=EvidenceStatus.FAIL,
                explanation="Momentum contradicts the candidate direction.",
                category="MOMENTUM"
            ))
            score = 0.0
            passed = False
            
        return EvaluatorResult(
            name=self.name,
            passed=passed,
            score=score,
            weight=self.weight,
            evidence=evidence,
            warnings=warnings
        )
