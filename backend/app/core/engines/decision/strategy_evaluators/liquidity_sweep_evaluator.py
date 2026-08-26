"""
Falcon Phase 7 — Liquidity Sweep Strategy Evaluator
"""
from app.schemas.decision_context import DecisionContext
from app.schemas.strategy_evaluation import StrategyEvaluationResult, StrategyRuleCheck
from app.core.engines.decision.strategy_evaluators.base_strategy_evaluator import BaseStrategyEvaluator


class LiquiditySweepEvaluator(BaseStrategyEvaluator):
    
    @property
    def strategy_id(self) -> str:
        return "liquidity_sweep_v1"

    @property
    def strategy_name(self) -> str:
        return "Liquidity Sweep"

    def evaluate(self, context: DecisionContext) -> StrategyEvaluationResult:
        rules = []
        warnings = []
        score = 0.0

        # Rule 1: We want a reversal regime, but can also work in ranges
        regime_passed = False
        if context.regimeReport:
            regime_name = context.regimeReport.regime.value.upper()
            if regime_name in ("REVERSAL", "RANGING", "HIGH_VOLATILITY"):
                regime_passed = True
                score += 50.0
                rules.append(StrategyRuleCheck(
                    rule="Favorable Regime",
                    passed=True,
                    observed=f"Regime: {regime_name}",
                    required="REVERSAL, RANGING, or HIGH_VOLATILITY",
                    evidence="Regime supports liquidity grabs."
                ))
            else:
                warnings.append("Trending regime makes fading sweeps risky.")
                rules.append(StrategyRuleCheck(
                    rule="Favorable Regime",
                    passed=False,
                    observed=f"Regime: {regime_name}",
                    required="Not strongly trending",
                    evidence="Sweeps often fail in strong trends."
                ))
        else:
            warnings.append("No regime report to confirm market state.")

        # Rule 2: Direction vs Trend (sweeps often counter-trend)
        # Not strictly blocking, but adds to score if we have clear momentum divergence.
        # Since we don't have direct momentum divergence in context yet, we'll just check if
        # it's at least not fighting a very strong trend.
        volatility = context.volatility.upper() if context.volatility else "UNKNOWN"
        vol_passed = False
        if volatility in ("HIGH", "EXPANDING", "NORMAL"):
            vol_passed = True
            score += 50.0
            rules.append(StrategyRuleCheck(
                rule="Sufficient Volatility",
                passed=True,
                observed=f"Volatility: {volatility}",
                required="At least NORMAL volatility",
                evidence="Sweeps require volatility to reach stops."
            ))
        else:
            rules.append(StrategyRuleCheck(
                rule="Sufficient Volatility",
                passed=False,
                observed=f"Volatility: {volatility}",
                required="At least NORMAL volatility",
                evidence="Low volatility means weak sweeps."
            ))

        passed = regime_passed and vol_passed
        
        return self._make_result(passed, score, rules, warnings)
