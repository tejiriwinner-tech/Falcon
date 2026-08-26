"""
Falcon Phase 7 — Base Strategy Evaluator (M6)

Abstract base class for Strategy Evaluators.
"""
from abc import ABC, abstractmethod
from typing import List

from app.schemas.decision_context import DecisionContext
from app.schemas.strategy_evaluation import StrategyEvaluationResult, StrategyRuleCheck


class BaseStrategyEvaluator(ABC):
    """
    Abstract base class for all specific strategy evaluators.
    """

    @property
    @abstractmethod
    def strategy_id(self) -> str:
        """The ID of the strategy this evaluates (e.g. 'trend_pullback')."""
        pass

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Human-readable name of the strategy."""
        pass

    @abstractmethod
    def evaluate(self, context: DecisionContext) -> StrategyEvaluationResult:
        """
        Evaluate the context against this strategy's rules.
        """
        pass

    def _make_result(
        self,
        passed: bool,
        score: float,
        checked_rules: List[StrategyRuleCheck],
        warnings: List[str] = None
    ) -> StrategyEvaluationResult:
        """Helper to construct the evaluation result."""
        failed_rules = [r.rule for r in checked_rules if not r.passed]
        
        return StrategyEvaluationResult(
            strategyId=self.strategy_id,
            strategyName=self.strategy_name,
            passed=passed,
            score=round(score, 2),
            checkedRules=checked_rules,
            failedRules=failed_rules,
            warnings=warnings or [],
        )
