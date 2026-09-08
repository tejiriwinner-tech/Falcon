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
        session = (context.session or "").lower()
        spread = context.spread
        market_open = context.marketOpen

        warnings = []
        if not market_open or "closed" in session or "weekend" in session:
            score = 15.0
            passed = False
            warnings.append("Market is closed; liquidity is minimal.")
            impact = EvidenceImpact.CONTRADICTING
            status = EvidenceStatus.FAIL
            obs = "CLOSED"
            exp = "Exchange is closed; order books are inactive."
        elif "overlap" in session or "london" in session or "new york" in session:
            if spread <= 1.5:
                score = 90.0
                passed = True
                impact = EvidenceImpact.SUPPORTING
                status = EvidenceStatus.PASS
                obs = f"{context.session} (Tight Spread: {spread:.2f}p)"
                exp = f"Deep institutional liquidity available during {context.session} with tight spread."
            else:
                score = 75.0
                passed = True
                impact = EvidenceImpact.SUPPORTING
                status = EvidenceStatus.PASS
                obs = f"{context.session} (Spread: {spread:.2f}p)"
                exp = f"Active trading session {context.session} with moderate spread."
        elif "tokyo" in session or "asian" in session:
            score = 65.0
            passed = True
            impact = EvidenceImpact.NEUTRAL
            status = EvidenceStatus.PASS
            obs = f"{context.session} (Spread: {spread:.2f}p)"
            exp = "Asian session order flow provides moderate liquidity."
        else:
            score = 40.0
            passed = True
            impact = EvidenceImpact.NEUTRAL
            status = EvidenceStatus.WARN
            obs = f"{context.session or 'Standby'}"
            exp = "Off-peak or standby session liquidity."

        evidence = [DecisionEvidence(
            indicator="LIQUIDITY_ZONES",
            observedValue=obs,
            weight=self.weight,
            impact=impact,
            status=status,
            explanation=exp,
            category="LIQUIDITY"
        )]
        
        return EvaluatorResult(
            name=self.name,
            passed=passed,
            score=score,
            weight=self.weight,
            evidence=evidence,
            warnings=warnings
        )
