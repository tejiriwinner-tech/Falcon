"""
Falcon Phase 7 — Decision Context Schema

The DecisionContext is a single immutable snapshot that aggregates all upstream
pipeline artifacts for a single candidate. Every evaluator consumes this context.
No evaluator communicates directly with another evaluator.

Design rules:
  - All fields are Optional to support graceful degradation when data is missing.
  - Cached derived values are computed ONCE by the ContextBuilder and shared.
  - Immutable after construction (no evaluator may mutate it).
  - context_version allows future schema evolution without breaking existing decisions.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

from app.schemas.signal_candidate import SignalCandidate
from app.schemas.validation_result import ValidationResult
from app.schemas.risk_assessment import RiskAssessment
from app.schemas.execution_readiness import ExecutionReadiness
from app.schemas.strategy import StrategyItem
from app.schemas.market_state import MarketState
from app.schemas.market_regime import MarketRegimeReport


class DecisionContext(BaseModel):
    """
    Single immutable context object for one candidate evaluation cycle.

    Built exactly once by the ContextBuilder at the start of Stage 6.
    Passed to every evaluator, the risk gate, confidence engine, strategy
    evaluator, and decision generator without modification.

    Cached fields (trend, session, spread, etc.) are derived from
    upstream artifacts and stored here to avoid recomputation across evaluators.

    Attributes:
        candidateId:    Unique ID of the signal candidate being evaluated
        missionId:      Parent mission ID
        candidate:      The signal candidate artifact
        validation:     Validation result for this candidate
        risk:           Risk assessment for this candidate
        readiness:      Execution readiness evaluation for this candidate
        strategy:       The strategy this candidate was generated from
        marketState:    Full live market state at evaluation time
        regimeReport:   Most relevant market regime report (Optional — M3 wires this)
        -- Cached derived values (computed once, never recomputed) --
        spread:         Spread in pips/points at evaluation time
        session:        Trading session name (e.g. 'London', 'New York')
        trend:          Trend label from market state (e.g. 'Bullish', 'Bearish')
        volatility:     Volatility label (e.g. 'Low', 'Moderate', 'High')
        newsImpact:     Current news impact level (e.g. 'Low', 'High')
        marketOpen:     Whether the market is open at evaluation time
        dataAgeSeconds: Age of the primary quote data in seconds
        -- Metadata --
        builtAt:        UTC timestamp when this context was constructed
        contextVersion: Schema version string for replay compatibility
    """
    # Identifiers
    candidateId: str = Field(..., description="Signal candidate ID")
    missionId: str = Field(..., description="Parent mission ID")

    # Core upstream artifacts (all Optional for graceful degradation)
    candidate: Optional[SignalCandidate] = Field(None, description="Signal candidate artifact")
    validation: Optional[ValidationResult] = Field(None, description="Validation result")
    risk: Optional[RiskAssessment] = Field(None, description="Risk assessment")
    readiness: Optional[ExecutionReadiness] = Field(None, description="Execution readiness")
    strategy: Optional[StrategyItem] = Field(None, description="Strategy definition")
    marketState: Optional[MarketState] = Field(None, description="Live market state")
    regimeReport: Optional[MarketRegimeReport] = Field(None, description="Market regime report")

    # Cached derived values — computed ONCE by ContextBuilder
    spread: float = Field(default=0.0, description="Current spread")
    session: str = Field(default="Unknown", description="Current trading session")
    trend: str = Field(default="Neutral", description="Current trend direction")
    volatility: str = Field(default="Moderate", description="Current volatility level")
    newsImpact: str = Field(default="Low", description="Current news impact level")
    marketOpen: bool = Field(default=False, description="Whether market is open")
    dataAgeSeconds: int = Field(default=0, description="Age of market data in seconds")
    candidateDirection: str = Field(default="WAIT", description="Candidate trade direction")
    candidateConfidence: float = Field(default=0.0, description="Candidate confidence 0–100")
    candidateRiskReward: float = Field(default=0.0, description="Candidate risk/reward ratio")

    # Strategy context (cached from strategy for quick evaluator access)
    strategyId: str = Field(default="", description="Strategy ID")
    strategyName: str = Field(default="Unknown", description="Strategy name")
    preferredSessions: List[str] = Field(default_factory=list, description="Strategy preferred sessions")
    minimumConfidence: float = Field(default=70.0, description="Strategy minimum confidence")
    minimumRiskReward: float = Field(default=1.5, description="Strategy minimum R:R")
    avoidConditions: List[str] = Field(default_factory=list, description="Strategy avoid conditions")
    marketCompatibility: List[str] = Field(default_factory=list, description="Compatible market types")

    # Metadata
    builtAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when context was built"
    )
    contextVersion: str = Field(
        default="1.0",
        description="Schema version for replay compatibility"
    )

    model_config = {
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "candidateId": "cand-001",
                "missionId": "mission-001",
                "spread": 0.35,
                "session": "London",
                "trend": "Bullish",
                "volatility": "Moderate",
                "newsImpact": "Low",
                "marketOpen": True,
                "dataAgeSeconds": 4,
                "candidateDirection": "BUY",
                "candidateConfidence": 88.0,
                "candidateRiskReward": 2.4,
                "strategyId": "strat-001",
                "strategyName": "London Breakout",
                "preferredSessions": ["London", "New York"],
                "minimumConfidence": 85.0,
                "minimumRiskReward": 2.0,
                "avoidConditions": ["High Impact News", "Low Liquidity"],
                "marketCompatibility": ["Trending", "Volatile"],
                "contextVersion": "1.0"
            }
        }
    }
