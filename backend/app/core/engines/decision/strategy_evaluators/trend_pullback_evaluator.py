"""
Falcon Phase 7 — Trend Pullback Strategy Evaluator
"""
from app.schemas.decision_context import DecisionContext
from app.schemas.strategy_evaluation import StrategyEvaluationResult, StrategyRuleCheck
from app.core.engines.decision.strategy_evaluators.base_strategy_evaluator import BaseStrategyEvaluator


class TrendPullbackEvaluator(BaseStrategyEvaluator):
    
    @property
    def strategy_id(self) -> str:
        return "trend_pullback_v1"

    @property
    def strategy_name(self) -> str:
        return "Trend Pullback"

    def evaluate(self, context: DecisionContext) -> StrategyEvaluationResult:
        rules = []
        warnings = []
        score = 0.0

        # Rule 1: Trade direction aligns with trend
        direction = getattr(context.candidate.direction, "name", str(context.candidate.direction)).upper() if context.candidate else "UNKNOWN"
        trend = context.trend.upper() if context.trend else "UNKNOWN"
        
        rule1_passed = False
        if direction in ("BUY", "LONG") and trend == "BULLISH":
            rule1_passed = True
        elif direction in ("SELL", "SHORT") and trend == "BEARISH":
            rule1_passed = True
            
        rules.append(StrategyRuleCheck(
            rule="Direction Alignment",
            passed=rule1_passed,
            observed=f"Direction: {direction}, Trend: {trend}",
            required="Direction must match Trend",
            evidence="Trend alignment is mandatory for trend pullback strategies."
        ))
        
        if rule1_passed:
            score += 60.0

        # Rule 2: Regime should ideally be trending
        if context.regimeReport:
            regime_name = context.regimeReport.regime.value.upper()
            if "TRENDING" in regime_name:
                score += 40.0
                rules.append(StrategyRuleCheck(
                    rule="Trending Regime",
                    passed=True,
                    observed=f"Regime: {regime_name}",
                    required="Regime should be trending",
                    evidence="Strong trending regime supports pullback continuation."
                ))
            else:
                score += 20.0 # Partial score for non-trending but passed alignment
                warnings.append("Regime is not strongly trending; pullback may fail or turn into range.")
                rules.append(StrategyRuleCheck(
                    rule="Trending Regime",
                    passed=False,
                    observed=f"Regime: {regime_name}",
                    required="Regime should be trending",
                    evidence="Regime does not strongly support trend continuation."
                ))
        else:
            warnings.append("No regime report available to confirm trend strength.")

        passed = rule1_passed
        
        return self._make_result(passed, score, rules, warnings)
