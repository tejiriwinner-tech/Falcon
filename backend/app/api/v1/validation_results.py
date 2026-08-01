from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.core.engines.market_state_engine import MarketStateEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.validation_engine import ValidationEngine
from app.schemas.validation_result import ValidationResult, ValidationResultListResponse

router = APIRouter()

market_state_engine = MarketStateEngine()
strategy_engine = StrategyEngine()
signal_generation_engine = SignalGenerationEngine()
validation_engine = ValidationEngine()

@router.get("/validation-results", response_model=ValidationResultListResponse)
def get_validation_results():
    """
    Runs the validation pipeline. Fetches current market state and strategies,
    generates signal candidates, performs validation checks on each candidate,
    and returns the validation results list.
    """
    market_state = market_state_engine.get_market_state()
    strategies = strategy_engine.get_strategies()
    candidates = signal_generation_engine.generate_candidates(market_state, strategies)
    results = validation_engine.validate_candidates(candidates, strategies, market_state)
    return ValidationResultListResponse(
        results=results,
        lastUpdated=datetime.now(timezone.utc)
    )

@router.get("/validation-results/{validation_id}", response_model=ValidationResult)
def get_validation_result(validation_id: str):
    """
    Returns a single ValidationResult artifact by its deterministic ID (e.g. validation-001).
    Returns 404 if no result with the given ID exists.
    """
    market_state = market_state_engine.get_market_state()
    strategies = strategy_engine.get_strategies()
    candidates = signal_generation_engine.generate_candidates(market_state, strategies)
    results = validation_engine.validate_candidates(candidates, strategies, market_state)
    for result in results:
        if result.id == validation_id:
            return result
    raise HTTPException(status_code=404, detail=f"Validation result '{validation_id}' not found.")
