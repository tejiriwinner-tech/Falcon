from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import Any, Dict
from pydantic import BaseModel
from app.schemas.strategy import StrategyListResponse, StrategyItem, StrategyStatus
from app.core.engines.strategy_engine import StrategyEngine, strategy_engine

router = APIRouter()

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

@router.get("/strategies/pause-state")
def get_strategy_pause_state() -> Dict[str, Any]:
    """
    Get active vs paused state across all strategies and symbols.
    """
    return strategy_engine.get_pause_state()

@router.post("/strategies/{strategy_id}/pause", response_model=StrategyItem)
def pause_strategy(strategy_id: str):
    """
    Pause a specific strategy by ID (e.g. strat-013).
    """
    strategy = strategy_engine.pause_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy

@router.post("/strategies/{strategy_id}/resume", response_model=StrategyItem)
def resume_strategy(strategy_id: str):
    """
    Resume a paused strategy by ID.
    """
    strategy = strategy_engine.resume_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy

@router.post("/strategies/symbol/{symbol:path}/pause")
def pause_symbol_strategies(symbol: str) -> Dict[str, Any]:
    """
    Pause all strategies for a symbol (e.g. GBPJPY, AUDUSD, USDJPY).
    """
    affected = strategy_engine.pause_symbol(symbol)
    return {
        "action": "PAUSE_SYMBOL",
        "symbol": symbol,
        "paused_strategy_ids": affected,
        "state": strategy_engine.get_pause_state(),
    }

@router.post("/strategies/symbol/{symbol:path}/resume")
def resume_symbol_strategies(symbol: str) -> Dict[str, Any]:
    """
    Resume all strategies for a symbol.
    """
    affected = strategy_engine.resume_symbol(symbol)
    return {
        "action": "RESUME_SYMBOL",
        "symbol": symbol,
        "resumed_strategy_ids": affected,
        "state": strategy_engine.get_pause_state(),
    }

@router.post("/strategies/expansion/pause")
def pause_expansion_strategies() -> Dict[str, Any]:
    """
    Pause all 6 multi-pair expansion strategies (strat-013 through strat-018).
    """
    affected = strategy_engine.pause_expansion_strategies()
    return {
        "action": "PAUSE_EXPANSION",
        "paused_strategy_ids": affected,
        "state": strategy_engine.get_pause_state(),
    }

@router.post("/strategies/expansion/resume")
def resume_expansion_strategies() -> Dict[str, Any]:
    """
    Resume all 6 multi-pair expansion strategies (strat-013 through strat-018).
    """
    affected = strategy_engine.resume_expansion_strategies()
    return {
        "action": "RESUME_EXPANSION",
        "resumed_strategy_ids": affected,
        "state": strategy_engine.get_pause_state(),
    }

@router.get("/strategies/{strategy_id}", response_model=StrategyItem)
def get_strategy(strategy_id: str):
    """
    Get a specific strategy by ID.
    """
    strategy = strategy_engine.get_enriched_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


class StrategyStatusUpdateRequest(BaseModel):
    status: StrategyStatus


@router.post("/strategies/{strategy_id}/toggle", response_model=StrategyItem)
def toggle_strategy(strategy_id: str):
    """
    Toggle a strategy between ACTIVE and INCUBATION status.
    """
    strategy = strategy_engine.toggle_strategy_status(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@router.post("/strategies/{strategy_id}/status", response_model=StrategyItem)
def update_strategy_status(strategy_id: str, payload: StrategyStatusUpdateRequest):
    """
    Explicitly set a strategy's status (ACTIVE or INCUBATION).
    """
    strategy = strategy_engine.set_strategy_status(strategy_id, payload.status)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy
