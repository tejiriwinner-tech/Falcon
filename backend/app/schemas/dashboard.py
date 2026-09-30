"""
Falcon Dashboard — Immutable Dashboard Schemas
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.market_quote import MarketQuote
from app.schemas.provider_models import ProviderSummary, ProviderHealthDetail
from app.schemas.mission_report import MissionSummary
from app.schemas.health import HealthResponse
from app.schemas.market_state import MarketState
from app.schemas.signal import SignalListResponse
from app.schemas.news import NewsListResponse
from app.schemas.decision_engine import DecisionEngineResponse
from app.schemas.runtime import RuntimeMetrics


class DashboardSummary(BaseModel):
    providerStatus: str          # ONLINE / DEGRADED / OFFLINE
    pipelineHealth: float        # 0-100
    repositoryHealth: float      # 0-100
    activeProviders: int
    connectedProvider: str       # e.g. "Twelve Data"
    watchedSymbols: List[str]
    totalStrategies: int
    totalSignals: int
    totalMissions: int
    totalArchivedArtifacts: int
    latestDecision: Optional[str] = None  # e.g. "WAIT" / "NO_TRADE"
    lastRefresh: datetime
    engineVersion: str


class AnalyticsSummary(BaseModel):
    tradingScore: int
    winRate: float
    totalTrades: int
    netProfit: float
    lastUpdated: datetime


class DashboardInstrumentContext(BaseModel):
    symbol: str
    canonicalSymbol: str
    instrumentType: str
    assetClass: str
    exchange: str
    displayName: str
    pipSize: float
    precision: int


class DashboardResponse(BaseModel):
    summary: DashboardSummary
    marketQuotes: List[MarketQuote]
    providerSummary: ProviderSummary
    missionSummary: MissionSummary
    analyticsSummary: AnalyticsSummary
    
    # Aggregated sub-responses for a single-flight dashboard payload
    systemHealth: Optional[HealthResponse] = None
    marketState: Optional[MarketState] = None
    signals: Optional[SignalListResponse] = None
    news: Optional[NewsListResponse] = None
    decision: Optional[DecisionEngineResponse] = None

    # Phase 4.3.8 — per-provider health detail (no keys, no internal URLs)
    providerHealth: List[ProviderHealthDetail] = []

    # Phase 4.3.9 — runtime observability metrics
    runtimeMetrics: Optional[RuntimeMetrics] = None

    # Requirement 11 & 12 — Instrument contexts and validation warnings
    instrumentContexts: List[DashboardInstrumentContext] = Field(default=[])
    instrumentValidationWarnings: List[str] = Field(default=[])

    generatedAt: datetime = Field(default_factory=lambda: __import__('datetime').datetime.now(__import__('datetime').timezone.utc))
