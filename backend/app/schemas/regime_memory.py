"""
Falcon V10 Regime Memory Schemas (Pillar 2: Cognitive Learning & Self-Reflection).

Defines data models for post-mortem diagnostics, root-cause forensics,
strategy health classification, and dynamic adaptation rules.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class RootCauseType(str, Enum):
    """Forensic root cause classifications for trade outcomes."""
    INSTITUTIONAL_LIQUIDITY_SWEEP = "INSTITUTIONAL_LIQUIDITY_SWEEP"
    OFF_PEAK_MOMENTUM_STALL = "OFF_PEAK_MOMENTUM_STALL"
    MACRO_NEWS_VOLATILITY = "MACRO_NEWS_VOLATILITY"
    NORMAL_STOP_OUT = "NORMAL_STOP_OUT"
    TAKE_PROFIT_HIT = "TAKE_PROFIT_HIT"


class StrategyHealthStatus(str, Enum):
    """Operational health status of a trading strategy."""
    HEALTHY = "HEALTHY"
    CAUTION = "CAUTION"
    QUARANTINED_PAPER = "QUARANTINED_PAPER"
    BOOSTED = "BOOSTED"


class DynamicAdaptation(BaseModel):
    """Prescribed dynamic adaptation to adjust strategy execution rules."""
    model_config = ConfigDict(extra="allow")

    atr_stop_multiplier_delta: float = Field(
        default=0.0,
        description="Stop buffer expansion adjustment (e.g., +0.35 for +35% ATR expansion)",
    )
    restrict_to_major_sessions: bool = Field(
        default=False,
        description="Whether to restrict execution strictly to London/NY sessions",
    )
    widen_news_blackout_minutes: int = Field(
        default=0,
        description="Minutes to expand news blackout window before and after macro releases",
    )
    action: Optional[str] = Field(
        default=None,
        description="Standardized action code (e.g., EXPAND_ATR_STOP_BUFFER, RESTRICT_SESSION_WINDOW)",
    )
    recommended_weight: Optional[float] = Field(
        default=None,
        description="Adjusted capital sizing or allocation weight multiplier",
    )
    reinforce_strategy: bool = Field(
        default=False,
        description="Indicates successful strategy reinforcement",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional technical notes regarding the adaptation",
    )


class PostMortemDiagnostic(BaseModel):
    """Forensic post-mortem analysis of a closed trade."""
    model_config = ConfigDict(extra="allow")

    trade_id: str = Field(description="Unique identifier of the trade or signal")
    symbol: str = Field(description="Financial instrument symbol, e.g. EURUSD, XAUUSD")
    strategy_id: str = Field(description="Identifier of the executing strategy")
    outcome: str = Field(description="Outcome of the trade, e.g. WIN, LOSS, BREAKEVEN")
    pnl: float = Field(description="Realized profit or loss in quote currency / dollars")
    root_cause: RootCauseType = Field(description="Diagnosed root cause")
    rationale: str = Field(description="Forensic rationale supporting the root cause diagnosis")
    lesson_learned: str = Field(description="Cognitive learning insight derived from outcome")
    prescribed_adaptation: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dynamic parameter adaptations prescribed by memory engine",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Diagnostic generation timestamp (UTC)",
    )


class StrategyHealthScore(BaseModel):
    """Evaluated rolling health scorecard for a strategy."""
    model_config = ConfigDict(extra="allow")

    strategy_id: str = Field(description="Identifier of the trading strategy")
    win_rate: float = Field(description="Rolling win rate (0.0 to 1.0)")
    profit_factor: float = Field(description="Gross profit divided by gross loss")
    total_trades: int = Field(description="Number of closed trades evaluated")
    consecutive_losses: int = Field(description="Current unbroken losing streak")
    health_status: StrategyHealthStatus = Field(description="Health classification")
    recommended_weight: float = Field(
        description="Recommended capital allocation multiplier (e.g. 0.0, 0.5, 1.0, 1.5)"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="Explanation of health status determination",
    )
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Scorecard evaluation timestamp (UTC)",
    )


class RegimeMemorySummary(BaseModel):
    """Aggregated memory snapshot across all strategies and diagnostics."""
    model_config = ConfigDict(extra="allow")

    total_diagnostics: int = Field(description="Total count of post-mortem diagnostics recorded")
    root_cause_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of diagnosed root causes",
    )
    strategy_scorecards: Dict[str, StrategyHealthScore] = Field(
        default_factory=dict,
        description="Current health scorecards mapped by strategy_id",
    )
    recent_lessons: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Chronological ledger of recent lessons learned",
    )
    quarantined_strategies: List[str] = Field(
        default_factory=list,
        description="Strategies currently in paper quarantine",
    )
    boosted_strategies: List[str] = Field(
        default_factory=list,
        description="Strategies currently receiving boosted capital allocation",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Summary generation timestamp (UTC)",
    )
