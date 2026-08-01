from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.core.engines.market_state_engine import MarketStateEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.validation_engine import ValidationEngine
from app.core.engines.risk_engine import RiskEngine
from app.schemas.risk_assessment import (
    RiskAssessment, RiskAssessmentListResponse, RiskSummary, RiskLevel
)

router = APIRouter()

market_state_engine = MarketStateEngine()
strategy_engine = StrategyEngine()
signal_generation_engine = SignalGenerationEngine()
validation_engine = ValidationEngine()
risk_engine = RiskEngine()

@router.get("/risk-assessments", response_model=RiskAssessmentListResponse)
def get_risk_assessments():
    """
    Runs the pipeline through the Risk Engine. Returns the immutable RiskAssessment artifacts
    with a pre-calculated RiskSummary. Downstream engines consume this output directly.
    """
    market_state = market_state_engine.get_market_state()
    strategies = strategy_engine.get_strategies()
    candidates = signal_generation_engine.generate_candidates(market_state, strategies)
    validations = validation_engine.validate_candidates(candidates, strategies, market_state)
    assessments = risk_engine.assess_all(validations, candidates, strategies, market_state)

    # Backend-calculated summary — Flutter must not recalculate these
    total = len(assessments)
    low = sum(1 for a in assessments if a.riskLevel == RiskLevel.LOW)
    medium = sum(1 for a in assessments if a.riskLevel == RiskLevel.MEDIUM)
    high = sum(1 for a in assessments if a.riskLevel == RiskLevel.HIGH)
    extreme = sum(1 for a in assessments if a.riskLevel == RiskLevel.EXTREME)
    avg_score = int(sum(a.overallRiskScore for a in assessments) / total) if total > 0 else 0

    summary = RiskSummary(
        totalAssessments=total,
        lowRisk=low,
        mediumRisk=medium,
        highRisk=high,
        extremeRisk=extreme,
        averageRiskScore=avg_score
    )

    return RiskAssessmentListResponse(
        assessments=assessments,
        summary=summary,
        lastUpdated=datetime.now(timezone.utc)
    )

@router.get("/risk-assessments/{assessment_id}", response_model=RiskAssessment)
def get_risk_assessment(assessment_id: str):
    """
    Returns a single RiskAssessment artifact by its deterministic ID (e.g. risk-001).
    Returns 404 if no assessment with the given ID exists.
    """
    market_state = market_state_engine.get_market_state()
    strategies = strategy_engine.get_strategies()
    candidates = signal_generation_engine.generate_candidates(market_state, strategies)
    validations = validation_engine.validate_candidates(candidates, strategies, market_state)
    assessments = risk_engine.assess_all(validations, candidates, strategies, market_state)
    for assessment in assessments:
        if assessment.id == assessment_id:
            return assessment
    raise HTTPException(status_code=404, detail=f"Risk assessment '{assessment_id}' not found.")
