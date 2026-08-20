from fastapi import APIRouter

from app.core.services.trade_intelligence_service import build_trade_intelligence
from app.schemas.trade_intelligence import TradeIntelligenceResponse

router = APIRouter()


@router.get("/trade-intelligence", response_model=TradeIntelligenceResponse)
def get_trade_intelligence():
    """Pair, session and timeframe intelligence derived from the trade journal."""
    return build_trade_intelligence()
