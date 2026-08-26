"""
Falcon Phase 7 — Generated Decision Schema (M7)
"""
from pydantic import BaseModel
from typing import List

from app.schemas.decision_enums import DecisionRecommendation
from app.schemas.confidence_score import ConfidenceScore


class GeneratedDecision(BaseModel):
    """
    The final output of the DecisionGenerator.
    """
    recommendation: DecisionRecommendation
    confidence: ConfidenceScore
    reasoning: str
    warnings: List[str]
