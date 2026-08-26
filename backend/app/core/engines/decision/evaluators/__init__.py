"""
Falcon Phase 7 — Technical Evaluators Package

Independent, single-responsibility technical evaluators.
Each evaluator consumes a DecisionContext and produces an EvaluatorResult containing
structured DecisionEvidence.

No evaluator makes BUY or SELL decisions, and no evaluator mutates the context.
"""
from abc import ABC, abstractmethod
from app.schemas.decision_context import DecisionContext
from app.schemas.evaluator_result import EvaluatorResult


class BaseEvaluator(ABC):
    """
    Abstract base class for all technical evaluators.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the evaluator."""
        pass

    @property
    @abstractmethod
    def weight(self) -> float:
        """Relative contribution weight (0.0 - 1.0) for this evaluator."""
        pass

    @abstractmethod
    def evaluate(self, context: DecisionContext) -> EvaluatorResult:
        """
        Evaluate the context and produce an EvaluatorResult.
        """
        pass
