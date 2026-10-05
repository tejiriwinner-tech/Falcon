from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timedelta

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
        
        # Determine cache duration based on endpoint
        cache_duration = self._get_cache_duration(request.url.path)
        
        if cache_duration > 0:
            # Add cache headers
            response.headers["Cache-Control"] = f"public, max-age={cache_duration}"
            response.headers["Expires"] = (datetime.utcnow() + timedelta(seconds=cache_duration)).strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )
        else:
            # Disable caching for sensitive or real-time data
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        # Add ETag for conditional requests
        if cache_duration > 0:
            response.headers["ETag"] = self._generate_etag(response)
        
        return response
    
    def _get_cache_duration(self, path: str) -> int:
        """Get cache duration for a given path."""
        for endpoint, duration in self.CACHE_DURATIONS.items():
            if endpoint in path:
                return duration
        return 0  # Default: no caching
    
    def _generate_etag(self, response: Response) -> str:
        """Generate a simple ETag based on response body."""
        import hashlib
        body = getattr(response, "body", b"")
        if body:
            return hashlib.md5(body).hexdigest()
        return "0"