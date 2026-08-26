from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.middleware.rate_limiter import rate_limiter

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to apply rate limiting to all requests."""
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check endpoint
        if request.url.path == "/api/v1/health":
            return await call_next(request)
        
        # Check rate limit
        await rate_limiter.check_rate_limit(request)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = "100"
        response.headers["X-RateLimit-Window"] = "60"
        
        return response