"""
Falcon Phase 7 — Trend Evaluator
"""
from app.schemas.decision_context import DecisionContext
from app.schemas.evaluator_result import EvaluatorResult, DecisionEvidence, EvidenceImpact, EvidenceStatus
from app.core.engines.decision.evaluators.__init__ import BaseEvaluator


class TrendEvaluator(BaseEvaluator):
    """
    Evaluates trend direction and strength relative to the candidate direction.
    """
    
    @property
    def name(self) -> str:
        return "TrendEvaluator"
        
    @property
    def weight(self) -> float:
        return 0.25

    def evaluate(self, context: DecisionContext) -> EvaluatorResult:
        evidence = []
        warnings = []
        score = 0.0
        passed = False
        
        # We need a candidate direction to evaluate against
        candidate_dir = context.candidateDirection.upper()
        if candidate_dir not in ("BUY", "SELL"):
            return EvaluatorResult(
                name=self.name,
                passed=False,
                score=0.0,
                weight=self.weight,
                evidence=[],
                warnings=[f"Cannot evaluate trend for non-directional candidate: {candidate_dir}"]
            )
            
        trend = context.trend.upper()
        
        if trend == "NEUTRAL":
            evidence.append(DecisionEvidence(
                indicator="TREND_DIRECTION",
                observedValue="NEUTRAL",
                weight=0.5,
                impact=EvidenceImpact.NEUTRAL,
                status=EvidenceStatus.WARN,
                explanation="Market trend is currently neutral, offering no directional advantage.",
                category="TREND"
            ))
            score = 40.0
            passed = False
        elif (candidate_dir == "BUY" and trend == "BULLISH") or (candidate_dir == "SELL" and trend == "BEARISH"):
            evidence.append(DecisionEvidence(
                indicator="TREND_DIRECTION",
                observedValue=trend,
                weight=1.0,
                impact=EvidenceImpact.SUPPORTING,
                status=EvidenceStatus.PASS,
                explanation=f"Price is trending {trend.lower()}, aligned with the {candidate_dir} direction.",
                category="TREND"
            ))
            score = 100.0
            passed = True
        else:
            evidence.append(DecisionEvidence(
                indicator="TREND_DIRECTION",
                observedValue=trend,
                weight=1.0,
                impact=EvidenceImpact.CONTRADICTING,
                status=EvidenceStatus.FAIL,
                explanation=f"Price is trending {trend.lower()}, contradicting the {candidate_dir} direction.",
                category="TREND"
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
