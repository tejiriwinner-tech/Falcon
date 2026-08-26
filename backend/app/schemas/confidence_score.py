"""
Falcon Phase 7 — Confidence Score Schema (M5)

Structured output of ConfidenceEngine.calculate() with full breakdown,
bonuses, penalties and a letter grade.
"""
from typing import Dict, Optional
from pydantic import BaseModel, Field


class ConfidenceScore(BaseModel):
    """
    Rich confidence result attached to every GeneratedDecision.

    Fields:
        overall:               Final clamped [0–100] confidence score.
        evaluatorContribution: Weighted sum from technical evaluators.
        riskPenalty:           Downward adjustment from risk exposure.
        validationBonus:       Upward adjustment from validation score.
        readinessBonus:        Upward adjustment from execution readiness.
        regimeModifier:        Fractional modifier from market regime (e.g. +0.075).
        breakdown:             Per-evaluator name → contribution score.
        grade:                 Letter grade: A+ / A / B / C / D / F
    """
    overall: float = Field(ge=0.0, le=100.0, description="Final confidence [0–100]")
    evaluatorContribution: float = Field(ge=0.0, le=100.0)
    riskPenalty: float = Field(ge=0.0, le=100.0)
    validationBonus: float = Field(ge=0.0, le=100.0)
    readinessBonus: float = Field(ge=0.0, le=100.0)
    regimeModifier: float = 0.0
    breakdown: Dict[str, float] = Field(default_factory=dict)
    grade: str = "F"

    @classmethod
    def grade_from_score(cls, score: float) -> str:
        if score >= 92:
            return "A+"
        elif score >= 82:
            return "A"
        elif score >= 72:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 45:
            return "D"
        else:
            return "F"
