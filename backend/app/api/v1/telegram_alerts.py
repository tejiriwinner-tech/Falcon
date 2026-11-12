"""
Falcon Telegram Alert API Router — Disconnected
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/alerts/telegram", tags=["telegram_alerts"])


class TelegramTestRequest(BaseModel):
    chat_id: Optional[str] = None


class TelegramConfigRequest(BaseModel):
    chat_id: Optional[str] = None
    min_confidence: Optional[int] = None
    enabled: Optional[bool] = None


@router.get("/status")
async def get_telegram_status() -> Dict[str, Any]:
    """Check the status of the Telegram alert service."""
    return {
        "enabled": False,
        "is_configured": False,
        "has_token": False,
        "chat_id": None,
        "min_confidence": 100,
        "bot_info": None,
        "message": "Telegram is permanently disconnected from Falcon.",
    }


@router.get("/detect-chat-id")
async def detect_chat_id() -> Dict[str, Any]:
    return {
        "status": "disabled",
        "detected_chat_id": None,
        "message": "Telegram is permanently disconnected from Falcon.",
    }


@router.post("/test")
async def test_telegram_alert(req: TelegramTestRequest = TelegramTestRequest()) -> Dict[str, Any]:
    return {
        "status": "disabled",
        "chat_id": None,
        "message": "Telegram is permanently disconnected from Falcon.",
    }


@router.post("/configure")
async def configure_telegram(req: TelegramConfigRequest) -> Dict[str, Any]:
    return {
        "status": "disabled",
        "chat_id": None,
        "min_confidence": 100,
        "enabled": False,
        "message": "Telegram is permanently disconnected from Falcon.",
    }
