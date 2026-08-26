"""
Falcon Phase 7 — Range Reversal Strategy Evaluator
"""
from app.schemas.decision_context import DecisionContext
from app.schemas.strategy_evaluation import StrategyEvaluationResult, StrategyRuleCheck
from app.core.engines.decision.strategy_evaluators.base_strategy_evaluator import BaseStrategyEvaluator


class RangeReversalEvaluator(BaseStrategyEvaluator):
    
    @property
    def strategy_id(self) -> str:
        return "range_reversal_v1"

    @property
    def strategy_name(self) -> str:
        return "Range Reversal"

    def evaluate(self, context: DecisionContext) -> StrategyEvaluationResult:
        rules = []
        warnings = []
        score = 0.0

        # Rule 1: Regime should be RANGING
        regime_passed = False
        if context.regimeReport:
            regime_name = context.regimeReport.regime.value.upper()
            if regime_name == "RANGING":
                regime_passed = True
                score += 50.0
                rules.append(StrategyRuleCheck(
                    rule="Ranging Regime",
                    passed=True,
                    observed=f"Regime: {regime_name}",
                    required="Regime must be RANGING",
                    evidence="Market is in a range, suitable for mean reversion."
                ))
            else:
                rules.append(StrategyRuleCheck(
                    rule="Ranging Regime",
                    passed=False,
                    observed=f"Regime: {regime_name}",
                    required="Regime must be RANGING",
                    evidence="Market is not ranging."
                ))
        else:
            warnings.append("No regime report available.")
            rules.append(StrategyRuleCheck(
                rule="Ranging Regime",
                passed=False,
                observed="Unknown",
                required="Regime must be RANGING",
                evidence="Cannot confirm ranging market."
            ))

        # Rule 2: Volatility should not be extreme
        vol_passed = False
        volatility = context.volatility.upper() if context.volatility else "UNKNOWN"
        if volatility in ("LOW", "NORMAL"):
            vol_passed = True
            score += 50.0
            rules.append(StrategyRuleCheck(
                rule="Stable Volatility",
                passed=True,
                observed=f"Volatility: {volatility}",
                required="Volatility LOW or NORMAL",
                evidence="Stable volatility favors mean reversion."
            ))
        else:
            warnings.append("High volatility can blow through range boundaries.")
            rules.append(StrategyRuleCheck(
                rule="Stable Volatility",
                passed=False,
                observed=f"Volatility: {volatility}",
                required="Volatility LOW or NORMAL",
                evidence="Volatility is too high for range reversal."
            ))

        passed = regime_passed and vol_passed
        
        return self._make_result(passed, score, rules, warnings)
