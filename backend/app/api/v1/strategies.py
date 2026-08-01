from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.schemas.strategy import StrategyListResponse, StrategyItem
from app.core.engines.strategy_engine import StrategyEngine

router = APIRouter()
strategy_engine = StrategyEngine()

@router.get("/strategies", response_model=StrategyListResponse)
def get_strategies():
    """
    Get all trading strategies.
    """
    strategies = strategy_engine.get_strategies()
    return StrategyListResponse(
        strategies=strategies,
        lastUpdated=datetime.now(timezone.utc)
    )

@router.get("/strategies/{strategy_id}", response_model=StrategyItem)
def get_strategy(strategy_id: str):
    """
    Get a specific strategy by ID.
    """
    strategy = strategy_engine.get_strategy_by_id(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy
