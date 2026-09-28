"""
Falcon AI Co-Pilot & Scheduled Briefing Schemas (Pillar 3)
Defines request/response contracts for conversational queries and intelligence briefings.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BriefingType(str, Enum):
    """Types of scheduled intelligence briefings."""
    LONDON_OPEN = "LONDON_OPEN"
    DAILY_REVIEW = "DAILY_REVIEW"
    MID_SESSION = "MID_SESSION"


class CopilotQueryRequest(BaseModel):
    """User natural language query to Falcon AI Co-Pilot."""
    model_config = ConfigDict(from_attributes=True)

    query: str = Field(..., description="Natural language question or command")
    symbol: Optional[str] = Field(default=None, description="Optional target symbol (e.g. XAU/USD, EUR/USD)")
    session_context: Optional[Dict[str, Any]] = Field(default=None, description="Optional runtime or UI context")


class CopilotQueryResponse(BaseModel):
    """AI Co-Pilot structured response."""
    model_config = ConfigDict(from_attributes=True)

    query: str = Field(..., description="Original user query")
    intent: str = Field(..., description="Classified intent (e.g. TRADE_RATIONALE, STREAK_AND_RISK, FORENSIC_LEARNING, SYSTEM_AND_STRATEGY, GENERAL_INQUIRY)")
    response: str = Field(..., description="Markdown-formatted natural language answer")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence of the intent detection and rationale")
    technical_context: Optional[Dict[str, Any]] = Field(default=None, description="Structured technical indicators, levels, and pattern data")
    risk_context: Optional[Dict[str, Any]] = Field(default=None, description="Risk parameters, streak status, multiplier, headroom")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of response generation")


class IntelligenceBriefing(BaseModel):
    """Structured scheduled intelligence briefing."""
    model_config = ConfigDict(from_attributes=True)

    briefing_type: BriefingType = Field(..., description="Type of briefing (LONDON_OPEN, DAILY_REVIEW, MID_SESSION)")
    title: str = Field(..., description="Briefing title")
    summary: str = Field(..., description="Executive summary of market state or daily performance")
    market_levels: Dict[str, Any] = Field(default_factory=dict, description="Key levels by symbol: Asian ranges, OB, FVG, liquidity pools")
    key_insights: List[str] = Field(default_factory=list, description="Top watchpoints, takeaways, or tactical advice")
    risk_state: Dict[str, Any] = Field(default_factory=dict, description="Streak, multiplier, risk headroom, ceiling margin")
    formatted_text: str = Field(..., description="Telegram/mobile-ready markdown formatted text")
    generated_at: str = Field(..., description="ISO 8601 UTC timestamp of briefing creation")
