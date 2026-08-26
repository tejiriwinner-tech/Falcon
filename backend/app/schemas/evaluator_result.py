"""
Falcon Phase 7 — Evaluator Result & Decision Evidence Schemas

Shared schemas used by all technical evaluators and the Decision Intelligence Engine.
Every recommendation produced by Falcon must be traceable via DecisionEvidence objects.

Flutter must be able to render explanations without parsing English text.
"""
from enum import Enum
from typing import List
from pydantic import BaseModel, Field


class EvidenceImpact(str, Enum):
    """Impact direction of a piece of evidence on a decision."""
    SUPPORTING = "SUPPORTING"        # Strengthens the recommendation
    NEUTRAL = "NEUTRAL"              # Neither supports nor contradicts
    CONTRADICTING = "CONTRADICTING"  # Weakens or opposes the recommendation


class EvidenceStatus(str, Enum):
    """Pass/warn/fail status of an evidence check."""
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class DecisionEvidence(BaseModel):
    """
    A single structured piece of evidence contributing to a decision.

    Designed for Flutter rendering — no English parsing required.
    Every field is typed and machine-readable.

    Attributes:
        indicator:     Name of the indicator or factor (e.g. 'RSI_14', 'TREND_EMA200')
        observedValue: The actual measured value as a string (e.g. '67.3', 'BULLISH')
        weight:        Relative contribution of this evidence to overall confidence (0.0–1.0)
        impact:        Whether this evidence SUPPORTS, is NEUTRAL to, or CONTRADICTS the decision
        status:        PASS / WARN / FAIL
        explanation:   Human-readable sentence for UI display (English, for Flutter text widget)
        category:      Grouping category (e.g. 'TREND', 'STRUCTURE', 'RISK', 'SESSION')
    """
    indicator: str = Field(..., description="Indicator or factor name")
    observedValue: str = Field(..., description="Observed value as string")
    weight: float = Field(default=0.0, ge=0.0, le=1.0, description="Contribution weight 0–1")
    impact: EvidenceImpact = Field(..., description="Evidence impact on decision")
    status: EvidenceStatus = Field(..., description="Pass/warn/fail status")
    explanation: str = Field(..., description="Human-readable explanation for UI display")
    category: str = Field(default="GENERAL", description="Evidence category group")

    class Config:
        json_schema_extra = {
            "example": {
                "indicator": "TREND_DIRECTION",
                "observedValue": "BULLISH",
                "weight": 0.25,
                "impact": "SUPPORTING",
                "status": "PASS",
                "explanation": "Price is trending bullish above the 200 EMA, aligned with the BUY candidate direction.",
                "category": "TREND"
            }
        }


class EvaluatorResult(BaseModel):
    """
    Result produced by a single technical evaluator.

    Each evaluator is stateless, single-responsibility, and produces
    evidence only — no BUY/SELL decisions are made at the evaluator level.

    Attributes:
        name:     Evaluator name (e.g. 'TrendEvaluator')
        passed:   Whether this evaluator's primary condition was satisfied
        score:    Score 0–100 representing evaluation quality/alignment
        weight:   This evaluator's contribution weight to overall confidence
        evidence: Structured evidence items produced by this evaluator
        warnings: Non-blocking warnings (human-readable strings)
    """
    name: str = Field(..., description="Evaluator name")
    passed: bool = Field(..., description="Whether primary condition was satisfied")
    score: float = Field(..., ge=0.0, le=100.0, description="Evaluation score 0–100")
    weight: float = Field(..., ge=0.0, le=1.0, description="Contribution weight to confidence")
    evidence: List[DecisionEvidence] = Field(
        default_factory=list,
        description="Structured evidence items"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-blocking warnings"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "TrendEvaluator",
                "passed": True,
                "score": 85.0,
                "weight": 0.25,
                "evidence": [
                    {
                        "indicator": "TREND_DIRECTION",
                        "observedValue": "BULLISH",
                        "weight": 0.25,
                        "impact": "SUPPORTING",
                        "status": "PASS",
                        "explanation": "Bullish trend confirmed above 200 EMA.",
                        "category": "TREND"
                    }
                ],
                "warnings": []
            }
        }
