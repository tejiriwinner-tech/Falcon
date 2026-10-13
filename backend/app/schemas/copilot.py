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


class ChatMessage(BaseModel):
    """Single message in a conversational thread."""
    role: str = Field(..., description="'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message text content")


class ActionChip(BaseModel):
    """Interactive action chip returned to the mobile app."""
    label: str = Field(..., description="Chip display label, e.g. 'View XAUUSD Chart'")
    action: str = Field(..., description="Action identifier: OPEN_CHART, VIEW_SIGNAL, AUDIT_RISK, VIEW_CALENDAR, QUERY")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Action payload parameters")


class CopilotQueryRequest(BaseModel):
    """User natural language query to Falcon AI Co-Pilot."""
    model_config = ConfigDict(from_attributes=True)

    query: str = Field(..., description="Natural language question or command")
    symbol: Optional[str] = Field(default=None, description="Optional target symbol (e.g. XAU/USD, EUR/USD)")
    session_context: Optional[Dict[str, Any]] = Field(default=None, description="Optional runtime or UI context")
    conversation_history: Optional[List[ChatMessage]] = Field(default=None, description="Optional previous messages in the session for multi-turn reasoning")


class CopilotQueryResponse(BaseModel):
    """AI Co-Pilot structured response."""
    model_config = ConfigDict(from_attributes=True)

    query: str = Field(..., description="Original user query")
    intent: str = Field(..., description="Classified intent (e.g. TRADE_RATIONALE, STREAK_AND_RISK, FORENSIC_LEARNING, SYSTEM_AND_STRATEGY, TECHNICAL_ANALYSIS, GENERAL_INQUIRY)")
    response: str = Field(..., description="Markdown-formatted natural language answer")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence of the intent detection and rationale")
    technical_context: Optional[Dict[str, Any]] = Field(default=None, description="Structured technical indicators, levels, and pattern data")
    risk_context: Optional[Dict[str, Any]] = Field(default=None, description="Risk parameters, streak status, multiplier, headroom")
    suggested_actions: Optional[List[ActionChip]] = Field(default_factory=list, description="Interactive action chips for client UI")
    provider_used: Optional[str] = Field(default="falcon_expert", description="LLM provider or engine that generated the answer")
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
