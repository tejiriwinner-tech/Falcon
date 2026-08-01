from fastapi import APIRouter
from app.core.engines.market_state_engine import MarketStateEngine
from app.schemas.market_state import MarketState

router = APIRouter()
_engine = MarketStateEngine()

@router.get("/market-state", response_model=MarketState, tags=["market_state"])
async def get_market_state():
    """
    Returns the unified MarketState aggregated from all registered providers.
    """
    return _engine.get_market_state()
