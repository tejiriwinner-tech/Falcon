from fastapi import APIRouter
from datetime import datetime, timezone
from app.schemas.trade_intelligence import (
    TradeIntelligenceResponse,
    PairPerformance,
    SessionPerformance,
    TimeframePerformance
)

router = APIRouter()

def _now():
    return datetime.now(timezone.utc)

@router.get("/trade-intelligence", response_model=TradeIntelligenceResponse)
def get_trade_intelligence():
    # Mock data that logically maps to a user having traded a bit
    now = _now()
    return TradeIntelligenceResponse(
        totalTrades=45,
        winningTrades=25,
        losingTrades=15,
        breakEvenTrades=3,
        openTrades=2,
        winRate=0.555,
        winningDays=12,
        losingDays=8,
        currentWinStreak=3,
        currentLossStreak=0,
        bestPair="XAU/USD",
        worstPair="GBP/USD",
        bestSession="New York",
        bestTimeframe="H1",
        averageRiskReward=1.85,
        averageConfidence=82.5,
        mostCommonLossReason="Revenge trading / Overleveraging",
        lastUpdated=now,
        pairPerformance=[
            PairPerformance(symbol="XAU/USD", totalTrades=15, winRate=0.65, profitLoss=450.0),
            PairPerformance(symbol="EUR/USD", totalTrades=20, winRate=0.55, profitLoss=120.0),
            PairPerformance(symbol="GBP/USD", totalTrades=10, winRate=0.40, profitLoss=-80.0),
        ],
        sessionPerformance=[
            SessionPerformance(session="New York", totalTrades=25, winRate=0.60, profitLoss=300.0),
            SessionPerformance(session="London", totalTrades=15, winRate=0.53, profitLoss=150.0),
            SessionPerformance(session="Asian", totalTrades=5, winRate=0.40, profitLoss=40.0),
        ],
        timeframePerformance=[
            TimeframePerformance(timeframe="H1", totalTrades=20, winRate=0.65, profitLoss=320.0),
            TimeframePerformance(timeframe="M15", totalTrades=15, winRate=0.45, profitLoss=-50.0),
            TimeframePerformance(timeframe="H4", totalTrades=10, winRate=0.60, profitLoss=220.0),
        ]
    )
