from fastapi import FastAPI
from app.core.config import settings
from app.logging.logger import setup_logging
from app.middleware.logging_middleware import LoggingMiddleware
from app.core.exceptions import add_exception_handlers
from app.api.v1.api import api_router
from app.core.providers.provider_recovery_manager import provider_recovery_manager
from fastapi.middleware.cors import CORSMiddleware

# Initialize centralized logging
setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Add logging middleware first so CORS middleware wraps around it
app.add_middleware(LoggingMiddleware)

# DEVELOPMENT CORS configuration: allow all origins via regex for Flutter Web, mobile emulators, etc.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add global exception handlers
add_exception_handlers(app)

# Include main API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.on_event("startup")
async def startup_event():
    """Initialize recovery manager on startup."""
    provider_recovery_manager.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Stop recovery manager on shutdown."""
    provider_recovery_manager.stop()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
