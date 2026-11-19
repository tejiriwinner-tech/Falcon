from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timedelta, timezone

class CacheMiddleware(BaseHTTPMiddleware):
    """Middleware to add caching headers to API responses."""
    
    CACHE_DURATIONS = {
        '/health': 0,  # Never cache health checks
        '/signals': 30,  # 30 seconds for signals
        '/intelligence': 60,  # 1 minute for intelligence
        '/market': 0,  # Never cache real-time market data
        '/news': 300,  # 5 minutes for news
        '/dashboard': 0,  # Never cache dashboard; stream live updates
        '/market-quotes': 0,  # Never cache live quotes
        '/execution-readiness': 0,  # Real-time pre-flight readiness
        '/runtime': 0,  # Real-time telemetry
    }
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path

        # Only cache successful GET/HEAD responses and never cache /resolve endpoints
        if (
            request.method in ("GET", "HEAD")
            and 200 <= response.status_code < 300
            and "/resolve" not in path
        ):
            cache_duration = self._get_cache_duration(path)
        else:
            cache_duration = 0
        
        if cache_duration > 0:
            # Add cache headers
            response.headers["Cache-Control"] = f"public, max-age={cache_duration}"
            response.headers["Expires"] = (datetime.now(timezone.utc) + timedelta(seconds=cache_duration)).strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )
        else:
            # Disable caching for sensitive or real-time data
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response
    
    def _get_cache_duration(self, path: str) -> int:
        """Get cache duration for a given path."""
        if "/resolve" in path:
            return 0
        for endpoint, duration in self.CACHE_DURATIONS.items():
            if endpoint in path:
                return duration
        return 0  # Default: no caching