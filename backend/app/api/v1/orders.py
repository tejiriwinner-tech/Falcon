"""
Falcon Order Execution API Router
Endpoints for mobile app 1-Tap execution and MT5 client synchronization.
"""
from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any

from app.schemas.execution_order import (
    ExecutionOrderCreate,
    ExecutionOrderItem,
    ExecutionOrderConfirm,
    ExecutionOrderFail,
    ExecutionSettings,
)
from app.services.execution.order_execution_service import order_execution_service

router = APIRouter(prefix="/execution/orders", tags=["order_execution"])


@router.post("", response_model=ExecutionOrderItem, status_code=status.HTTP_201_CREATED)
async def submit_order(order_in: ExecutionOrderCreate) -> ExecutionOrderItem:
    """Submit a new trade order for execution on MetaTrader 5."""
    return order_execution_service.create_order(order_in)


@router.get("", response_model=List[ExecutionOrderItem])
async def list_orders(limit: int = 50) -> List[ExecutionOrderItem]:
    """List recent trade orders."""
    return order_execution_service.list_orders(limit=limit)


@router.get("/pending", response_model=List[ExecutionOrderItem])
async def get_pending_orders() -> List[ExecutionOrderItem]:
    """Queried by MT5 EA or Python Bridge to fetch orders waiting to be executed."""
    return order_execution_service.get_pending_orders()


@router.get("/settings", response_model=ExecutionSettings)
async def get_execution_settings() -> ExecutionSettings:
    """Get current execution parameters, lot sizes, and safety limits."""
    return order_execution_service.settings


@router.post("/settings", response_model=ExecutionSettings)
async def update_execution_settings(new_settings: ExecutionSettings) -> ExecutionSettings:
    """Update execution settings."""
    order_execution_service.settings = new_settings
    return order_execution_service.settings


@router.get("/{order_id}", response_model=ExecutionOrderItem)
async def get_order(order_id: str) -> ExecutionOrderItem:
    order = order_execution_service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")
    return order


@router.post("/{order_id}/confirm", response_model=ExecutionOrderItem)
async def confirm_order(order_id: str, confirm_in: ExecutionOrderConfirm) -> ExecutionOrderItem:
    """Called by MT5 EA or Bridge upon filling the trade."""
    order = order_execution_service.confirm_execution(order_id, confirm_in)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")
    return order


@router.post("/{order_id}/fail", response_model=ExecutionOrderItem)
async def fail_order(order_id: str, fail_in: ExecutionOrderFail) -> ExecutionOrderItem:
    """Called by MT5 if the broker rejected the order."""
    order = order_execution_service.fail_order(order_id, fail_in.reason)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")
    return order


@router.get("/cloud-broker/status")
async def get_cloud_broker_status() -> Dict[str, Any]:
    """Check 24/7 Zero-PC Cloud MT5 Broker connection status."""
    from app.services.execution.cloud_mt5_service import cloud_mt5_service
    return cloud_mt5_service.get_status()


@router.post("/cloud-broker/connect")
async def connect_cloud_broker(payload: Dict[str, str]) -> Dict[str, Any]:
    """Connect Exness MT5 account via MetaApi Cloud Token and Account ID (Zero-PC/VPS)."""
    from app.services.execution.cloud_mt5_service import cloud_mt5_service
    token = payload.get("token", "").strip()
    account_id = payload.get("account_id", "").strip()
    if not token or not account_id:
        raise HTTPException(status_code=400, detail="Both 'token' and 'account_id' are required.")
    cloud_mt5_service.configure(token, account_id)
    return cloud_mt5_service.get_status()

