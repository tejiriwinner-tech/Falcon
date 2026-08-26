"""
Falcon Rate Limiting Middleware (Phase 7.4 M2)

Lightweight IP-based rate limiting using an in-memory sliding window.

Returns HTTP 429 Too Many Requests when a client exceeds the
configured request limit within a one-minute window.

Public endpoints (/health, /docs, /openapi.json) are exempt.
"""
import asyncio
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request

from app.core.config import settings

# Public paths exempt from rate limiting. Documentation and OpenAPI can be
# mounted at either their FastAPI defaults or under the configured API prefix.
_PUBLIC_PATHS = {
    "/health",
    f"{settings.API_V1_STR}/health",
    "/docs",
    f"{settings.API_V1_STR}/docs",
    "/openapi.json",
    f"{settings.API_V1_STR}/openapi.json",
}

# Window size in seconds
_WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """IP-based sliding-window rate limiter."""

    def __init__(self, app, limit_per_minute: int = None):
        super().__init__(app)
        # Store None when not explicitly provided so the limit is read
        # dynamically from settings at request time (supports runtime
        # configuration changes and test-time patching).
        self._limit_per_minute = limit_per_minute
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        # Exempt public paths
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        async with self._lock:
            # Prune timestamps outside the window and update the client bucket
            # atomically so concurrent requests cannot bypass the limit.
            window = self._requests[client_ip]
            while window and window[0] <= now - _WINDOW_SECONDS:
                window.popleft()

            limit = (
                self._limit_per_minute
                if self._limit_per_minute is not None
                else settings.RATE_LIMIT_PER_MINUTE
            )
            is_limited = len(window) >= limit
            if not is_limited:
                window.append(now)

        if is_limited:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "status_code": 429,
                },
                headers={"Retry-After": str(_WINDOW_SECONDS)},
            )

        return await call_next(request)