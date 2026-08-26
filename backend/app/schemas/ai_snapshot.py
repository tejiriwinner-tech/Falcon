"""
Falcon AI Snapshot Schema

Complete AI analysis snapshot stored with each signal.
Includes trend, confluence, decision, and risk assessment data.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class TrendSnapshot(BaseModel):
    """Trend analysis snapshot."""
    trend_direction: str = Field(..., description="Trend direction (UP, DOWN, SIDEWAYS)")
    trend_strength: float = Field(..., description="Trend strength (0-100)")
    ma_alignment: str = Field(..., description="Moving average alignment")
    higher_highs: bool = Field(..., description="Higher highs pattern")
    higher_lows: bool = Field(..., description="Higher lows pattern")
    adx_value: Optional[float] = Field(None, description="ADX value")
    rsi_value: Optional[float] = Field(None, description="RSI value")


class StructureSnapshot(BaseModel):
    """Market structure analysis snapshot."""
    structure_type: str = Field(..., description="Structure type (HHHL, LHLL, RANGE)")
    swing_high: Optional[float] = Field(None, description="Swing high price")
    swing_low: Optional[float] = Field(None, description="Swing low price")
    key_level_type: Optional[str] = Field(None, description="Key level type (SUPPORT, RESISTANCE)")
    key_level_price: Optional[float] = Field(None, description="Key level price")
    break_of_structure: bool = Field(..., description="Break of structure detected")
    bos_price: Optional[float] = Field(None, description="Break of structure price")


class ConfluenceSnapshot(BaseModel):
    """Confluence analysis snapshot."""
    confluence_score: float = Field(..., description="Overall confluence score (0-100)")
    factors: List[str] = Field(default_factory=list, description="Confluence factors present")
    alignment_score: float = Field(..., description="Alignment score (0-100)")
    multi_timeframe_alignment: str = Field(..., description="Multi-timeframe alignment")
    liquidity_zone: Optional[str] = Field(None, description="Liquidity zone detected")
    institutional_level: bool = Field(..., description="Institutional level detected")


class IndicatorSnapshot(BaseModel):
    """Technical indicators snapshot."""
    rsi: Optional[float] = Field(None, description="RSI value")
    macd_signal: Optional[str] = Field(None, description="MACD signal")
    bb_position: Optional[str] = Field(None, description="Bollinger Band position")
    ema_trend: Optional[str] = Field(None, description="EMA trend")
    atr_value: Optional[float] = Field(None, description="ATR value")
    volume_spike: bool = Field(..., description="Volume spike detected")


class DecisionSnapshot(BaseModel):
    """AI decision snapshot."""
    decision: str = Field(..., description="AI decision (BUY, SELL, WAIT, NONE)")
    confidence: float = Field(..., description="Decision confidence (0-100)")
    primary_reason: str = Field(..., description="Primary reason for decision")
    secondary_reasons: List[str] = Field(default_factory=list, description="Secondary reasons")
    risk_reward: float = Field(..., description="Risk/reward ratio")
    expected_outcome: str = Field(..., description="Expected outcome")


class RiskAssessmentSnapshot(BaseModel):
    """Risk assessment snapshot."""
    risk_level: str = Field(..., description="Risk level (LOW, MEDIUM, HIGH)")
    account_risk_percent: float = Field(..., description="Account risk percentage")
    position_size: float = Field(..., description="Position size")
    max_drawdown: float = Field(..., description="Maximum drawdown")
    risk_factors: List[str] = Field(default_factory=list, description="Risk factors identified")
    blocking_conditions: List[str] = Field(default_factory=list, description="Blocking conditions")
    is_approved: bool = Field(..., description="Risk approval status")


class AISnapshot(BaseModel):
    """Complete AI analysis snapshot for a signal."""
    
    # Metadata
    snapshot_id: str = Field(..., description="Unique snapshot ID")
    signal_id: str = Field(..., description="Associated signal ID")
    generated_at: datetime = Field(..., description="Snapshot generation time")
    
    # Analysis components
    trend: TrendSnapshot = Field(..., description="Trend analysis")
    structure: StructureSnapshot = Field(..., description="Market structure")
    confluence: ConfluenceSnapshot = Field(..., description="Confluence analysis")
    indicators: IndicatorSnapshot = Field(..., description="Technical indicators")
    decision: DecisionSnapshot = Field(..., description="AI decision")
    risk_assessment: RiskAssessmentSnapshot = Field(..., description="Risk assessment")
    
    # Additional context
    market_session: str = Field(..., description="Market session (LONDON, NEW_YORK, ASIAN)")
    volatility_regime: str = Field(..., description="Volatility regime (LOW, NORMAL, HIGH)")
    liquidity_status: str = Field(..., description="Liquidity status")
    news_impact: Optional[str] = Field(None, description="News impact level")
    
    class Config:
        json_schema_extra = {
            "example": {
                "snapshot_id": "snap-123",
                "signal_id": "sig-456",
                "generated_at": "2026-08-02T12:00:00Z",
                "trend": {
                    "trend_direction": "UP",
                    "trend_strength": 85,
                    "ma_alignment": "BULLISH",
                    "higher_highs": True,
                    "higher_lows": True,
                    "adx_value": 35.5,
                    "rsi_value": 62.0
                },
                "structure": {
                    "structure_type": "HHHL",
                    "swing_high": 2360.0,
                    "swing_low": 2340.0,
                    "key_level_type": "RESISTANCE",
                    "key_level_price": 2360.0,
                    "break_of_structure": True,
                    "bos_price": 2361.0
                },
                "confluence": {
                    "confluence_score": 92,
                    "factors": ["Trend alignment", "Key level", "Liquidity zone"],
                    "alignment_score": 88,
                    "multi_timeframe_alignment": "BULLISH",
                    "liquidity_zone": "BUY SIDE LIQUIDITY",
                    "institutional_level": True
                },
                "indicators": {
                    "rsi": 62.0,
                    "macd_signal": "BULLISH",
                    "bb_position": "MIDDLE",
                    "ema_trend": "UP",
                    "atr_value": 15.5,
                    "volume_spike": False
                },
                "decision": {
                    "decision": "BUY",
                    "confidence": 88,
                    "primary_reason": "Strong bullish trend with break of structure",
                    "secondary_reasons": ["Confluence at key level", "Low risk"],
                    "risk_reward": 1.5,
                    "expected_outcome": "TP1 hit within 4 hours"
                },
                "risk_assessment": {
                    "risk_level": "LOW",
                    "account_risk_percent": 1.0,
                    "position_size": 0.10,
                    "max_drawdown": 0.5,
                    "risk_factors": ["Market volatility"],
                    "blocking_conditions": [],
                    "is_approved": True
                },
                "market_session": "LONDON",
                "volatility_regime": "NORMAL",
                "liquidity_status": "HIGH",
                "news_impact": "MEDIUM"
            }
        }
