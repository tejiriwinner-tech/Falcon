"""
Falcon Telegram Alert API Router
Endpoints to check status, test connectivity, and auto-detect user chat ID.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import httpx

from app.core.config.settings import settings
from app.services.alerts.telegram_alert_service import telegram_alert_service

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
    bot_info = None
    if settings.TELEGRAM_BOT_TOKEN:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe")
                if res.status_code == 200:
                    bot_info = res.json().get("result", {})
        except Exception:
            pass

    return {
        "enabled": settings.TELEGRAM_ALERTS_ENABLED,
        "is_configured": telegram_alert_service.is_configured,
        "has_token": bool(settings.TELEGRAM_BOT_TOKEN),
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "min_confidence": settings.TELEGRAM_MIN_CONFIDENCE,
        "bot_info": bot_info,
    }


@router.get("/detect-chat-id")
async def detect_chat_id() -> Dict[str, Any]:
    """Query Telegram getUpdates to auto-detect the user's Chat ID from recent messages."""
    detected_id = await telegram_alert_service.detect_chat_id()
    if detected_id:
        return {
            "status": "success",
            "detected_chat_id": detected_id,
            "message": f"Successfully detected chat ID {detected_id}. You can use this ID for alerts.",
        }
    return {
        "status": "not_found",
        "detected_chat_id": None,
        "message": "No recent messages found. Please open your bot in Telegram and send /start or any message first.",
    }


@router.post("/test")
async def test_telegram_alert(req: TelegramTestRequest = TelegramTestRequest()) -> Dict[str, Any]:
    """Send an immediate test alert to verify Telegram connectivity."""
    target_chat = req.chat_id or settings.TELEGRAM_CHAT_ID
    if not target_chat:
        # Try to auto-detect
        target_chat = await telegram_alert_service.detect_chat_id()
        if target_chat:
            settings.TELEGRAM_CHAT_ID = target_chat

    if not target_chat:
        raise HTTPException(
            status_code=400,
            detail="Chat ID not found. Please send a message to the bot on Telegram first, or specify chat_id.",
        )

    success = await telegram_alert_service.send_test_alert(custom_chat_id=target_chat)
    if success:
        return {
            "status": "success",
            "chat_id": target_chat,
            "message": "Test alert delivered successfully to your Telegram!",
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send test alert to Telegram. Please check token and chat ID.",
        )


@router.post("/configure")
async def configure_telegram(req: TelegramConfigRequest) -> Dict[str, Any]:
    """Dynamically update Telegram alert parameters."""
    if req.chat_id is not None:
        settings.TELEGRAM_CHAT_ID = req.chat_id
    if req.min_confidence is not None:
        settings.TELEGRAM_MIN_CONFIDENCE = max(50, min(100, req.min_confidence))
    if req.enabled is not None:
        settings.TELEGRAM_ALERTS_ENABLED = req.enabled

    return {
        "status": "success",
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "min_confidence": settings.TELEGRAM_MIN_CONFIDENCE,
        "enabled": settings.TELEGRAM_ALERTS_ENABLED,
    }
