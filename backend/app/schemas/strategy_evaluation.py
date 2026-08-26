"""
Falcon Phase 7 — Strategy Evaluation Schema (M6)

Structured output for Strategy Evaluators.
"""
from typing import List
from pydantic import BaseModel, Field


class StrategyRuleCheck(BaseModel):
    """Result of a single strategy rule evaluation."""
    rule: str
    passed: bool
    observed: str
    required: str
    evidence: str


class StrategyEvaluationResult(BaseModel):
    """
    Immutable result of evaluating a candidate against a specific strategy.
    
    Fields:
        strategyId:     ID of the strategy (e.g. 'trend_pullback_v1')
        strategyName:   Human readable name of the strategy
        passed:         True if all mandatory rules passed
        score:          0-100 score of how well the setup fits the strategy
        checkedRules:   List of all evaluated rules
        failedRules:    List of rule names that failed
        warnings:       Non-blocking warnings
    """
    strategyId: str
    strategyName: str
    passed: bool
    score: float = Field(ge=0.0, le=100.0)
    checkedRules: List[StrategyRuleCheck] = Field(default_factory=list)
    failedRules: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
