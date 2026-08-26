from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, UUID4

class Recommendation(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"

class DecisionEvidence(BaseModel):
    """
    Strongly typed evidence object explaining why a decision was made.
    Allows UI to build structured visual explanations instead of parsing text.
    """
    indicator: str
    value: Any
    status: str
    weight: int
    impact: str

class DecisionContext(BaseModel):
    """
    Internal-only context aggregating all inputs before a decision is evaluated.
    Never exposed via the API.
    """
    decisionId: UUID4
    instrument: str
    timeframe: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Market Data
    trend: Optional[str] = None
    marketRegime: Optional[str] = None
    atr: Optional[float] = None
    rsi: Optional[float] = None
    macd_signal: Optional[str] = None
    ema_alignment: Optional[str] = None
    volatility: Optional[float] = None
    spread: Optional[float] = None
    liquidity: Optional[float] = None
    
    # Meta Data
    providerHealth: Optional[str] = None
    providerConsensus: Optional[float] = None
    newsScore: Optional[float] = None
    historicalScore: Optional[float] = None
    strategyScore: Optional[float] = None
    
    # Dynamic storage for future extensibility
    additional_data: Dict[str, Any] = Field(default_factory=dict)

class DecisionResult(BaseModel):
    """
    The strictly typed public contract returned to the Flutter UI.
    Contains no internal scoring mechanics.
    """
    decisionId: UUID4
    engineVersion: str
    generatedAt: datetime
    processingTimeMs: int
    
    decision: Recommendation
    confidence: int  # 0-100
    signalStrength: str
    
    entry: Optional[float] = None
    stopLoss: Optional[float] = None
    takeProfits: List[float] = Field(default_factory=list)
    riskRewardRatio: Optional[float] = None
    
    trend: str
    volatility: str
    marketRegime: str
    
    strategyUsed: Optional[str] = None
    providerUsed: str
    
    reasoning: List[str]
    decisionEvidence: List[DecisionEvidence]
    warnings: List[str]
    confirmationChecklist: List[str]
    
    riskLevel: RiskLevel
    dataFreshness: str
