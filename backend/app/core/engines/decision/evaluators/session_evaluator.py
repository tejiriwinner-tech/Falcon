"""
Falcon Phase 7 — Session Evaluator
"""
from app.schemas.decision_context import DecisionContext
from app.schemas.evaluator_result import EvaluatorResult, DecisionEvidence, EvidenceImpact, EvidenceStatus
from app.core.engines.decision.evaluators.__init__ import BaseEvaluator


class SessionEvaluator(BaseEvaluator):
    """
    Evaluates if the current trading session is suitable for the strategy.
    """
    
    @property
    def name(self) -> str:
        return "SessionEvaluator"
        
    @property
    def weight(self) -> float:
        return 0.10

    def evaluate(self, context: DecisionContext) -> EvaluatorResult:
        evidence = []
        warnings = []
        
        current_session = context.session
        preferred = context.preferredSessions
        
        if not context.marketOpen:
            evidence.append(DecisionEvidence(
                indicator="MARKET_SESSION",
                observedValue="CLOSED",
                weight=1.0,
                impact=EvidenceImpact.CONTRADICTING,
                status=EvidenceStatus.FAIL,
                explanation="The market is currently closed.",
                category="SESSION"
            ))
            return EvaluatorResult(
                name=self.name,
                passed=False,
                score=0.0,
                weight=self.weight,
                evidence=evidence,
                warnings=["Market is closed."]
            )
            
        if not preferred:
            # If strategy has no preference, session is neutral
            evidence.append(DecisionEvidence(
                indicator="MARKET_SESSION",
                observedValue=current_session,
                weight=0.0,
                impact=EvidenceImpact.NEUTRAL,
                status=EvidenceStatus.PASS,
                explanation=f"Trading in {current_session} session (no strategy preference).",
                category="SESSION"
            ))
            score = 100.0
            passed = True
        elif current_session in preferred:
            evidence.append(DecisionEvidence(
                indicator="MARKET_SESSION",
                observedValue=current_session,
                weight=1.0,
                impact=EvidenceImpact.SUPPORTING,
                status=EvidenceStatus.PASS,
                explanation=f"Trading in preferred {current_session} session.",
                category="SESSION"
            ))
            score = 100.0
            passed = True
        else:
            evidence.append(DecisionEvidence(
                indicator="MARKET_SESSION",
                observedValue=current_session,
                weight=1.0,
                impact=EvidenceImpact.CONTRADICTING,
                status=EvidenceStatus.FAIL,
                explanation=f"Trading in {current_session} session, which is not preferred ({', '.join(preferred)}).",
                category="SESSION"
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
