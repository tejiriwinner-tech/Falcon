from fastapi import APIRouter
from datetime import datetime, timezone
from app.schemas.signal import SignalListResponse, SignalItem

router = APIRouter()

@router.get("/signals", response_model=SignalListResponse, tags=["signals"])
async def get_signals():
    """
    Get mock trading signals with strategy definitions and age.
    """
    now = datetime.now(timezone.utc)
    mock_signals = [
        SignalItem(
            id=1,
            symbol="XAU/USD",
            action="BUY",
            entry=2350.50,
            takeProfit=2400.00,
            stopLoss=2300.00,
            confidence=88,
            timeframe="M15",
            status="ACTIVE",
            analysis="Strong momentum on the M15 chart indicating breakout continuation.",
            timestamp=now,
            strategyId="strat-001",
            strategyName="London Breakout",
            strategyVersion="2.3",
            dataAgeSeconds=2
        ),
        SignalItem(
            id=2,
            symbol="GBP/USD",
            action="SELL",
            entry=1.2750,
            takeProfit=1.2600,
            stopLoss=1.2820,
            confidence=75,
            timeframe="M5",
            status="PENDING",
            analysis="Rejection at major resistance level during momentum run.",
            timestamp=now,
            strategyId="strat-004",
            strategyName="London Momentum",
            strategyVersion="2.0",
            dataAgeSeconds=4
        ),
        SignalItem(
            id=3,
            symbol="EUR/USD",
            action="BUY",
            entry=1.0820,
            takeProfit=1.0950,
            stopLoss=1.0750,
            confidence=82,
            timeframe="M15",
            status="ACTIVE",
            analysis="Bullish breakout of Frankfurt range.",
            timestamp=now,
            strategyId="strat-006",
            strategyName="European Breakout",
            strategyVersion="3.1",
            dataAgeSeconds=1
        )
    ]
    
    return SignalListResponse(
        signals=mock_signals,
        lastUpdated=now,
        dataAgeSeconds=2
    )
