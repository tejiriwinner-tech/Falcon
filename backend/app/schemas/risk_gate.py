"""
Falcon Phase 7 — Risk Gate Schema (M4)

Defines the structured veto / warning result produced by RiskGate.evaluate().
"""
from enum import Enum
from typing import List
from pydantic import BaseModel, Field

from app.schemas.evaluator_result import DecisionEvidence


class RiskGateDecision(str, Enum):
    PASS = "PASS"   # All risk conditions acceptable
    WARN = "WARN"   # Non-blocking concerns present
    VETO = "VETO"   # Trade MUST NOT proceed


class RiskGateResult(BaseModel):
    """
    Immutable result of the RiskGate evaluation.

    Fields:
        decision:  PASS | WARN | VETO
        score:     Residual risk exposure [0–100]. Lower is safer.
        vetoes:    Blocking reasons as structured DecisionEvidence.
        warnings:  Non-blocking concerns as structured DecisionEvidence.
        summary:   Plain-text summary of the gate decision.
    """
    decision: RiskGateDecision
    score: float = Field(ge=0.0, le=100.0, description="Residual risk score (0=safe, 100=extreme)")
    vetoes: List[DecisionEvidence] = Field(default_factory=list)
    warnings: List[DecisionEvidence] = Field(default_factory=list)
    summary: str = ""
