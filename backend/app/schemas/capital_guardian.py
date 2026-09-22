"""
Falcon Capital Guardian Schemas (V10 Phase 3)
Pydantic models for capital guardian decisions, proposed trade inputs, and safety states.
"""

from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class GuardianState(str, Enum):
    """Safety state of the Capital Guardian."""
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    PROTECTED = "PROTECTED"
    COOLDOWN = "COOLDOWN"
    HALTED = "HALTED"


class ProposedTradeInput(BaseModel):
    """Proposed trade input to be evaluated by the Capital Guardian."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    symbol: str = Field(..., description="Asset symbol, e.g. 'EURUSD', 'XAUUSD'")
    direction: str = Field(..., description="Trade direction, 'BUY' or 'SELL'")
    entryPrice: Decimal = Field(..., description="Proposed entry price")
    stopLoss: Decimal = Field(..., description="Proposed stop loss price")
    takeProfit: Optional[Decimal] = Field(default=None, description="Proposed take profit price")
    quantity: Optional[Decimal] = Field(default=None, description="Position size in units")
    lotSize: Optional[Decimal] = Field(default=None, description="Position size in lots (e.g. 0.01)")
    monetaryRisk: Optional[Decimal] = Field(
        default=None,
        description="Caller-provided monetary risk (never trusted to bypass safety unless isVerifiedRisk is True)",
    )
    isVerifiedRisk: bool = Field(
        default=False,
        description="True if monetaryRisk was produced by an authoritative, audited risk validator",
    )
    signalId: Optional[int] = Field(default=None, description="Associated signal ID if available")
    strategyId: Optional[str] = Field(default=None, description="Originating strategy ID")
    timeframe: Optional[str] = Field(default=None, description="Execution timeframe")
    riskReward: Optional[Decimal] = Field(default=None, description="Proposed risk-reward ratio")


class CapitalGuardianDecision(BaseModel):
    """Deterministic evaluation outcome from CapitalGuardianService."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    allowed: bool = Field(..., description="True if proposed trade is strictly authorized")
    reason: str = Field(..., description="Deterministic rationale for authorization or rejection")
    state: GuardianState = Field(..., description="Current safety state of Capital Guardian")
    activeTradingCapital: Decimal = Field(..., description="Active capital available for trading in active cycle")
    protectedProfit: Decimal = Field(..., description="Protected banked profit retained from previous cycles")
    currentLiveTradeCount: int = Field(..., description="Number of currently capital-reserving trades")
    maxLiveTradeCount: int = Field(default=3, description="Maximum permitted simultaneous capital-reserving trades")
    currentAggregateWorstCaseLoss: Decimal = Field(..., description="Aggregate monetary worst-case loss of all active trades")
    proposedWorstCaseLoss: Decimal = Field(..., description="Monetary worst-case loss of the proposed trade")
    aggregateWorstCaseLossAfter: Decimal = Field(..., description="Projected aggregate loss if proposed trade is authorized")
    remainingLossCapacity: Decimal = Field(..., description="Remaining risk loss capacity before hitting active capital")
    cycleId: Optional[str] = Field(default=None, description="Active cycle ID if available")

    # Snake-case property aliases for compatibility
    @property
    def active_trading_capital(self) -> Decimal:
        return self.activeTradingCapital

    @property
    def protected_profit(self) -> Decimal:
        return self.protectedProfit

    @property
    def current_live_trade_count(self) -> int:
        return self.currentLiveTradeCount

    @property
    def max_live_trade_count(self) -> int:
        return self.maxLiveTradeCount

    @property
    def current_aggregate_worst_case_loss(self) -> Decimal:
        return self.currentAggregateWorstCaseLoss

    @property
    def proposed_worst_case_loss(self) -> Decimal:
        return self.proposedWorstCaseLoss

    @property
    def aggregate_worst_case_loss_after(self) -> Decimal:
        return self.aggregateWorstCaseLossAfter

    @property
    def remaining_loss_capacity(self) -> Decimal:
        return self.remainingLossCapacity

    @property
    def cycle_id(self) -> Optional[str]:
        return self.cycleId
