"""
Falcon Phase 7 — Strategy Evaluator Registry (M6)
"""
from typing import Dict, Optional

from app.core.engines.decision.strategy_evaluators.base_strategy_evaluator import BaseStrategyEvaluator


class StrategyEvaluatorRegistry:
    """Registry pattern for strategy evaluators."""
    
    _evaluators: Dict[str, BaseStrategyEvaluator] = {}

    @classmethod
    def register(cls, evaluator: BaseStrategyEvaluator) -> None:
        """Register a new strategy evaluator."""
        cls._evaluators[evaluator.strategy_id] = evaluator

    @classmethod
    def get(cls, strategy_id: str) -> Optional[BaseStrategyEvaluator]:
        """Get a strategy evaluator by ID."""
        return cls._evaluators.get(strategy_id)

    @classmethod
    def clear(cls) -> None:
        """Clear the registry (useful for testing)."""
        cls._evaluators.clear()
