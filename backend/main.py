from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.core.config import settings
from app.logging.logger import setup_logging
from app.middleware.logging_middleware import LoggingMiddleware
from app.core.middleware.rate_limit_middleware import RateLimitMiddleware
from app.core.middleware.cache_middleware import CacheMiddleware
from app.core.exceptions import add_exception_handlers
from app.api.v1.api import api_router
from app.core.providers.provider_recovery_manager import provider_recovery_manager
from app.core.repository.mission_repository import mission_repository
from app.core.services.market_data_scheduler import market_data_scheduler
from app.services.scheduler.scheduler_service import scheduler_service
from app.services.scheduler.learning_scheduler_service import learning_scheduler_service
from app.core.services.briefing_service import briefing_service
from app.core.services.watchlist_poller_service import watchlist_poller_service
from fastapi.middleware.cors import CORSMiddleware
import logging

# Initialize centralized logging
setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Add logging middleware first so CORS middleware wraps around it
app.add_middleware(LoggingMiddleware)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Add cache middleware for response caching headers
app.add_middleware(CacheMiddleware)

# CORS configuration with environment-based origins
# For development: allow all origins via "*"
# For production: restrict to specific origins via CORS_ORIGINS env var (comma-separated)
cors_origins = settings.CORS_ORIGINS
if cors_origins == "*":
    cors_origins = ["*"]
else:
    cors_origins = [origin.strip() for origin in cors_origins.split(",")]

allow_credentials = settings.CORS_ALLOW_CREDENTIALS

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add global exception handlers
add_exception_handlers(app)

# Include main API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
def get_dashboard_root():
    """Serve the Falcon Visual Audit Web UI."""
    from pathlib import Path
    template_path = Path(__file__).resolve().parent / "app" / "templates" / "dashboard.html"
    if template_path.exists():
        return HTMLResponse(content=template_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Falcon Dashboard Template Not Found</h1>", status_code=404)


@app.on_event("startup")
async def startup_event():
    """Initialize recovery manager, market data scheduler, signal scheduler, and watchlist poller on startup."""
    storage = "Postgres (Supabase)" if mission_repository.persistent else "in-memory (no DATABASE_URL)"
    logging.getLogger(__name__).info("Mission repository storage: %s", storage)
    
    # Start provider recovery manager
    provider_recovery_manager.start()
    
    # Start market data scheduler
    await market_data_scheduler.start()
    logging.getLogger(__name__).info("Market data scheduler started")

    # Start automated signal market scheduler
    try:
        await scheduler_service.start()
        logging.getLogger(__name__).info("Signal market scheduler started")
    except Exception as e:
        logging.getLogger(__name__).warning("Signal market scheduler start error: %s", e)

    # Start automated learning cycle scheduler
    try:
        await learning_scheduler_service.start()
        logging.getLogger(__name__).info("Autonomous learning scheduler started")
    except Exception as e:
        logging.getLogger(__name__).warning("Autonomous learning scheduler start error: %s", e)

    # Start background watchlist price poller
    try:
        await watchlist_poller_service.start()
        logging.getLogger(__name__).info("Watchlist price poller started")
    except Exception as e:
        logging.getLogger(__name__).warning("Watchlist price poller start error: %s", e)

    # Warm Falcon AI Co-Pilot & scheduled briefings cache
    try:
        briefing_service.warm_cache()
        logging.getLogger(__name__).info("Falcon Intelligence briefing cache warmed")
    except Exception as e:
        logging.getLogger(__name__).warning("Briefing cache warming error: %s", e)


@app.on_event("shutdown")
async def shutdown_event():
    """Stop all background schedulers, pollers, and managers on shutdown."""
    try:
        await watchlist_poller_service.stop()
    except Exception:
        pass
    try:
        await learning_scheduler_service.stop()
    except Exception:
        pass
    try:
        await scheduler_service.stop()
    except Exception:
        pass
    await market_data_scheduler.stop()
    provider_recovery_manager.stop()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
