from fastapi import APIRouter
from datetime import datetime, timezone
from app.core.config import settings
from app.schemas.health import HealthResponse
from app.core.engines.health_engine import HealthEngine

router = APIRouter()
health_engine = HealthEngine()

@router.get("/health", response_model=HealthResponse, tags=["health"])
def health_check():
    """
    Health check endpoint returning system status and engine diagnostic details.
    """
    health_data = health_engine.get_health()
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        systemHealth=health_data
    )
