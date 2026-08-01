from fastapi import APIRouter
from datetime import datetime
from app.schemas.market import MarketListResponse, MarketItem

router = APIRouter()

@router.get("", response_model=MarketListResponse)
async def get_markets():
    # Mock data for markets
    markets = [
        MarketItem(
            symbol="XAU/USD",
            name="Gold",
            price=2348.42,
            change=0.72,
            changePercent=0.72,
            isPositive=True,
            marketStatus="OPEN"
        ),
        MarketItem(
            symbol="GBP/USD",
            name="British Pound",
            price=1.2651,
            change=-0.09,
            changePercent=-0.09,
            isPositive=False,
            marketStatus="OPEN"
        ),
        MarketItem(
            symbol="EUR/USD",
            name="Euro",
            price=1.1743,
            change=0.15,
            changePercent=0.15,
            isPositive=True,
            marketStatus="OPEN"
        )
    ]
    
    return MarketListResponse(
        markets=markets,
        lastUpdated=datetime.utcnow().isoformat() + "Z"
    )
