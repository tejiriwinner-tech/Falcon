"""
Falcon Phase 7 — Decision Enums

Standalone enums shared by decision_artifact, generated_decision, and the
Decision Intelligence pipeline to avoid circular imports.
"""
from enum import Enum


class DecisionRecommendation(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"
    MONITOR = "MONITOR"
    NO_TRADE = "NO_TRADE"
    AVOID = "AVOID"
