"""
Falcon Remote Push Notification Router (Firebase Cloud Messaging)
Endpoints to check FCM status, test connectivity, and push diagnostic alerts.
"""
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.services.fcm_service import fcm_service

logger = logging.getLogger("falcon.api.notifications")

router = APIRouter(prefix="/notifications", tags=["notifications"])

class TestNotificationRequest(BaseModel):
    title: Optional[str] = "Falcon AI Signal Alert"
    body: Optional[str] = "Test Push Notification: Real-time background alert working!"
    topic: Optional[str] = "falcon_signals"
    symbol: Optional[str] = "EUR/USD"
    direction: Optional[str] = "BUY"

@router.get("/status")
def get_notification_status() -> Dict[str, Any]:
    """Check whether Firebase Cloud Messaging (FCM) is initialized and active."""
    return {
        "fcm_ready": fcm_service._ready,
        "topic": fcm_service.FALCON_SIGNALS_TOPIC,
        "message": "FCM active and ready to deliver background push alerts" if fcm_service._ready else "FCM inactive: Check Firebase service account credentials",
    }

@router.post("/test")
def test_notification(request: TestNotificationRequest) -> Dict[str, Any]:
    """Sends a test high-priority push notification to topic subscribers (even when app is closed)."""
    success = fcm_service.send_signal_alert(
        title=request.title or "Falcon AI Signal Alert",
        body=request.body or "Test Push Notification: Real-time background alert working!",
        data={
            "symbol": request.symbol or "EUR/USD",
            "direction": request.direction or "BUY",
            "is_test": "true",
        },
        topic=request.topic or fcm_service.FALCON_SIGNALS_TOPIC,
    )

    return {
        "success": success,
        "topic": request.topic or fcm_service.FALCON_SIGNALS_TOPIC,
        "delivered": success,
        "detail": "Notification dispatched to Firebase" if success else "Failed to dispatch notification to Firebase",
    }
