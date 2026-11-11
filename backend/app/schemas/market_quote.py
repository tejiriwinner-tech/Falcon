"""
Falcon Intelligence Pipeline — Immutable Market Quote Schemas
"""
from enum import Enum
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class QuoteStatus(str, Enum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    STALE = "STALE"


class MarketStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PRE_MARKET = "PRE_MARKET"
    AFTER_HOURS = "AFTER_HOURS"


class BidAsk(BaseModel):
    bid: float
    ask: float
    spread: float
    bidLiquidity: Optional[float] = None
    askLiquidity: Optional[float] = None
    domImbalance: Optional[float] = None
    depthTiers: Optional[int] = None


class MarketQuote(BaseModel):
    symbol: str
    bidAsk: BidAsk
    lastPrice: float
    change: float = 0.0
    changePercent: float = 0.0
    timestamp: datetime
    providerId: str
    providerName: str
    quoteStatus: QuoteStatus = QuoteStatus.LIVE
    marketStatus: MarketStatus = MarketStatus.OPEN
    freshnessSeconds: float = 0.0
    bidLiquidity: Optional[float] = None
    askLiquidity: Optional[float] = None
    domImbalance: Optional[float] = None
    depthTiers: Optional[int] = None


class MarketQuoteResponse(BaseModel):
    quote: MarketQuote
    receivedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
