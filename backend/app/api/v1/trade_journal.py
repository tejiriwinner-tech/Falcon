from fastapi import APIRouter
from typing import List
from datetime import datetime, timedelta, timezone
from app.schemas.trade_journal import TradeJournalItem, TradeJournalListResponse

router = APIRouter()

def _now():
    return datetime.now(timezone.utc)

@router.get("/trade-journal", response_model=TradeJournalListResponse)
def get_trade_journal():
    now = _now()
    mock_trades = [
        TradeJournalItem(
            id=1,
            symbol="XAU/USD",
            direction="BUY",
            entryPrice=2000.50,
            exitPrice=2020.50,
            stopLoss=1990.00,
            takeProfit=2030.00,
            timeframe="H1",
            marketSession="New York",
            tradeDate=now - timedelta(days=2),
            closeDate=now - timedelta(days=1),
            status="CLOSED",
            result="WIN",
            profitLoss=200.0,
            riskReward=2.0,
            confidence=85,
            reasonForEntry="Strong support bounce with bullish engulfing",
            lessonLearned="Patience paid off, let the trade hit TP.",
            createdAt=now - timedelta(days=2),
            updatedAt=now - timedelta(days=1),
        ),
        TradeJournalItem(
            id=2,
            symbol="GBP/USD",
            direction="SELL",
            entryPrice=1.2650,
            exitPrice=1.2680,
            stopLoss=1.2680,
            takeProfit=1.2550,
            timeframe="M15",
            marketSession="London",
            tradeDate=now - timedelta(days=3),
            closeDate=now - timedelta(days=3, hours=-4),
            status="CLOSED",
            result="LOSS",
            profitLoss=-30.0,
            riskReward=1.5,
            confidence=70,
            reasonForEntry="Break of structure on lower timeframe",
            reasonForExit="Hit stop loss during sudden news spike",
            lessonLearned="Always check economic calendar before entering.",
            createdAt=now - timedelta(days=3),
            updatedAt=now - timedelta(days=3, hours=-4),
        ),
        TradeJournalItem(
            id=3,
            symbol="EUR/USD",
            direction="BUY",
            entryPrice=1.0900,
            exitPrice=1.0900,
            stopLoss=1.0850,
            takeProfit=1.1000,
            timeframe="H4",
            marketSession="London",
            tradeDate=now - timedelta(days=1),
            closeDate=now - timedelta(hours=5),
            status="CLOSED",
            result="BREAKEVEN",
            profitLoss=0.0,
            riskReward=2.0,
            confidence=80,
            reasonForEntry="Trend continuation setup",
            reasonForExit="Moved SL to breakeven after 1R, price reversed",
            lessonLearned="Good risk management, no loss taken.",
            createdAt=now - timedelta(days=1),
            updatedAt=now - timedelta(hours=5),
        ),
        TradeJournalItem(
            id=4,
            symbol="XAU/USD",
            direction="SELL",
            entryPrice=2015.00,
            stopLoss=2025.00,
            takeProfit=1995.00,
            timeframe="M30",
            marketSession="New York",
            tradeDate=now - timedelta(hours=2),
            status="OPEN",
            result="OPEN",
            profitLoss=-15.0,
            riskReward=2.0,
            confidence=90,
            reasonForEntry="Rejection at major resistance level",
            notes="Monitoring closely, price consolidating.",
            createdAt=now - timedelta(hours=2),
            updatedAt=now - timedelta(hours=2),
        ),
    ]
    return TradeJournalListResponse(
        trades=mock_trades,
        lastUpdated=now
    )

@router.post("/trade-journal", response_model=TradeJournalItem)
def create_trade_journal(trade: TradeJournalItem):
    # Simply return the submitted object as requested
    return trade
