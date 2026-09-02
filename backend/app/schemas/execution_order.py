"""
Falcon Order Execution Schemas
Models for MT5 order routing, execution status, and safety limits.
"""
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class OrderAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionOrderCreate(BaseModel):
    symbol: str
    action: OrderAction
    lot_size: float = Field(default=0.01, ge=0.01, le=1.0)
    order_type: OrderType = OrderType.MARKET
    entry_price: float
    stop_loss: float
    take_profit: float
    strategy_name: Optional[str] = "Falcon Core Strategy"
    confidence: Optional[int] = 80
    comment: Optional[str] = "Falcon AI v4.2"


class ExecutionOrderConfirm(BaseModel):
    ticket_number: int
    fill_price: float
    slippage_pips: Optional[float] = 0.0
    broker_name: Optional[str] = None


class ExecutionOrderFail(BaseModel):
    reason: str


class ExecutionOrderItem(BaseModel):
    order_id: str
    symbol: str
    action: OrderAction
    lot_size: float
    order_type: OrderType
    entry_price: float
    stop_loss: float
    take_profit: float
    strategy_name: str
    confidence: int
    magic_number: int = 777888
    comment: str
    status: OrderStatus
    ticket_number: Optional[int] = None
    fill_price: Optional[float] = None
    slippage_pips: Optional[float] = None
    broker_name: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: datetime
    executed_at: Optional[datetime] = None


class ExecutionSettings(BaseModel):
    auto_execute_enabled: bool = False
    is_demo_mode: bool = True
    default_lot_size: float = 0.01
    max_lot_size: float = 0.05
    min_confidence_for_auto: int = 80
    allowed_symbols: List[str] = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY"]
