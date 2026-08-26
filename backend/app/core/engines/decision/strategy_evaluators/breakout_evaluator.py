"""
Falcon Phase 7 — Breakout Strategy Evaluator
"""
from app.schemas.decision_context import DecisionContext
from app.schemas.strategy_evaluation import StrategyEvaluationResult, StrategyRuleCheck
from app.core.engines.decision.strategy_evaluators.base_strategy_evaluator import BaseStrategyEvaluator


class BreakoutEvaluator(BaseStrategyEvaluator):
    
    @property
    def strategy_id(self) -> str:
        return "breakout_v1"

    @property
    def strategy_name(self) -> str:
        return "Breakout"

    def evaluate(self, context: DecisionContext) -> StrategyEvaluationResult:
        rules = []
        warnings = []
        score = 0.0

        # Rule 1: High volatility supports breakouts
        volatility = context.volatility.upper() if context.volatility else "UNKNOWN"
        rule1_passed = volatility in ("HIGH", "EXPANDING")
        
        rules.append(StrategyRuleCheck(
            rule="Volatility Expansion",
            passed=rule1_passed,
            observed=f"Volatility: {volatility}",
            required="High or Expanding Volatility",
            evidence="Breakouts require volume and volatility to sustain."
        ))
        
        if rule1_passed:
            score += 50.0

        # Rule 2: Regime supports breakout
        if context.regimeReport:
            regime_name = context.regimeReport.regime.value.upper()
            if regime_name == "BREAKOUT":
                score += 50.0
                rules.append(StrategyRuleCheck(
                    rule="Breakout Regime",
                    passed=True,
                    observed=f"Regime: {regime_name}",
                    required="Regime should be BREAKOUT",
                    evidence="Market regime confirms breakout phase."
                ))
            else:
                warnings.append(f"Regime is {regime_name}, not ideal for pure breakout trading.")
                rules.append(StrategyRuleCheck(
                    rule="Breakout Regime",
                    passed=False,
                    observed=f"Regime: {regime_name}",
                    required="Regime should be BREAKOUT",
                    evidence="Regime does not confirm breakout."
                ))
        else:
            warnings.append("No regime report available.")

        # Breakout requires volatility to pass
        passed = rule1_passed
        
        return self._make_result(passed, score, rules, warnings)
