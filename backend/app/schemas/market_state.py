from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict


class MarketPrice(BaseModel):
    symbol: str
    currentPrice: float
    bid: float
    ask: float
    spread: float
    timestamp: datetime
    provider: str


class Indicator(BaseModel):
    name: str
    value: float
    signal: str
    provider: str


class MarketNews(BaseModel):
    title: str
    currency: str
    impact: str
    sentiment: str
    publishedAt: datetime
    expiresAt: datetime
    provider: str


class EconomicEvent(BaseModel):
    title: str
    currency: str
    impact: str
    eventTime: datetime
    countdownMinutes: int
    forecast: str
    previous: str
    actual: Optional[str] = None
    provider: str


class MarketSentiment(BaseModel):
    sentiment: str
    fearGreedIndex: int
    institutionalBias: str
    retailPositioning: str
    volumeProfileSummary: str
    provider: str


class MarketState(BaseModel):
    prices: Dict[str, MarketPrice] = Field(default_factory=dict)
    indicators: Dict[str, List[Indicator]] = Field(default_factory=dict)
    news: List[MarketNews] = Field(default_factory=list)
    calendar: List[EconomicEvent] = Field(default_factory=list)
    sentiment: Optional[MarketSentiment] = None

    # Existing / Derived fields (for backward compatibility where possible)
    trend: str = "Neutral"
    volatility: str = "Moderate"
    liquidity: str = "Good"
    spread: float = 0.0
    session: str = "Closed"
    marketOpen: bool = False
    upcomingHighImpactNews: bool = False
    currentNewsImpact: str = "None"
    marketSentimentLabel: str = "Neutral"
    fearGreedIndex: Optional[int] = None

    # Metadata
    timestamp: datetime
    dataAgeSeconds: int
    overallMarketConfidence: int = 50
    dataSource: str = "Falcon Intelligence Layer"

    # Phase 4.3 — Live market data metadata (additive, all Optional with defaults)
    # quoteStatus reflects what the provider reported for the primary quote:
    # LIVE / DELAYED / STALE / EXPIRED / INSUFFICIENT_DATA
    quoteStatus: str = "INSUFFICIENT_DATA"
    primaryProviderId: Optional[str] = None
    primaryProviderName: Optional[str] = None
    # freshnessSeconds: age of the primary quote in seconds (from cache or live)
    freshnessSeconds: Optional[float] = None
    # watchlistSymbols: all symbols attempted in this snapshot
    watchlistSymbols: List[str] = Field(default_factory=list)
