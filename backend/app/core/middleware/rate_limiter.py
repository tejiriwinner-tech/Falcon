from fastapi import Request, HTTPException, status
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple
import asyncio
from app.core.config.settings import settings

class RateLimiter:
    """Simple in-memory rate limiter using token bucket algorithm."""
    
    def __init__(self):
        # Store request counts per IP: {ip: (count, window_start)}
        self._requests: Dict[str, Tuple[int, datetime]] = defaultdict(lambda: (0, datetime.now()))
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        # Rate limit settings from config
        self._max_requests = settings.RATE_LIMIT_PER_MINUTE
        self._window = timedelta(minutes=1)
    
    async def check_rate_limit(self, request: Request) -> None:
        """Check if the request should be rate limited."""
        client_ip = self._get_client_ip(request)
        
        async with self._lock:
            now = datetime.now()
            count, window_start = self._requests[client_ip]
            
            # Reset if window expired
            if now - window_start > self._window:
                self._requests[client_ip] = (1, now)
                return
            
            # Check if exceeded limit
            if count >= self._max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please try again later."
                )
            
            # Increment count
            self._requests[client_ip] = (count + 1, window_start)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check for forwarded headers (proxy/load balancer)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        if request.client:
            return request.client.host
        
        return "unknown"

# Global rate limiter instance
rate_limiter = RateLimiter()